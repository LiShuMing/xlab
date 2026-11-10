import json

import pytest
import torch
from safetensors.torch import save_file

from reasoning_lab.experiments import numerical_checks, tiny_model
from reasoning_lab.generation import generate, response_log_probs, sft_loss_sum
from reasoning_lab.model import load_model


@pytest.mark.parametrize("as_dict", [False, True])
def test_chat_template_return_compatibility(as_dict):
    from reasoning_lab.generation import encode_prompt

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["enable_thinking"] is False
            return {"input_ids": [1, 2, 3]} if as_dict else [1, 2, 3]

    assert encode_prompt(Tokenizer(), "question") == [1, 2, 3]


def test_cache_padding_sdpa_and_hf_config():
    model = tiny_model()
    ids = torch.tensor([[5, 6, 7, 8], [0, 0, 9, 10]])
    mask = torch.tensor([[1, 1, 1, 1], [0, 0, 1, 1]])
    report = numerical_checks(model, ids, mask)
    assert report["passed"], report
    assert model.lm_head.weight is model.model.embed_tokens.weight


def test_sft_only_answer_supervised_and_frozen():
    model = tiny_model()
    prompt, answer = [8, 9], [10, 11, 2]
    loss_sum, count = sft_loss_sum(model, prompt, answer)
    ids = torch.tensor([prompt + answer])
    logits, _ = model(ids[:, :-1])
    labels = ids[:, 1:].clone()
    labels[:, : len(prompt) - 1] = -100
    expected = torch.nn.functional.cross_entropy(
        logits.flatten(0, 1), labels.flatten(), ignore_index=-100, reduction="sum"
    )
    torch.testing.assert_close(loss_sum, expected)
    assert count == 3
    loss_sum.backward()
    assert any(
        p.grad is not None and p.grad.abs().sum() > 0
        for name, p in model.named_parameters()
        if name.endswith(".B")
    )
    assert all(p.grad is None for p in model.parameters() if not p.requires_grad)


def test_accumulation_is_token_normalized():
    a, b = tiny_model(), tiny_model()
    examples = [([8, 9], [10, 2]), ([9, 10, 11], [12, 13, 14, 2])]
    tokens = sum(len(answer) for _, answer in examples)
    for prompt, answer in examples:
        (sft_loss_sum(a, prompt, answer)[0] / tokens).backward()
    loss = sum(sft_loss_sum(b, p, r)[0] for p, r in examples) / tokens
    loss.backward()
    for p, q in zip(a.parameters(), b.parameters()):
        if p.grad is not None:
            torch.testing.assert_close(p.grad, q.grad)


def test_gradient_checkpointing_matches():
    a, b = tiny_model(), tiny_model()
    b.gradient_checkpointing = True
    for model in [a, b]:
        model.train()
        sft_loss_sum(model, [8, 9], [10, 11, 2])[0].backward()
    for p, q in zip(a.parameters(), b.parameters()):
        if p.grad is not None:
            torch.testing.assert_close(p.grad, q.grad)


def test_rollout_logprobs_match_full_scoring_and_eos_action():
    model = tiny_model()
    sample = generate(model, [9, 10], 5, 0.7, None)
    recomputed = response_log_probs(model, [9, 10], sample.token_ids, 0.7)
    torch.testing.assert_close(sample.log_probs, recomputed, atol=2e-5, rtol=2e-5)
    first = generate(model, [9, 10], 1, 0, None).token_ids[0]
    eos = generate(model, [9, 10], 5, 0, first)
    assert eos.token_ids == [first] and eos.finish_reason == "eos"
    assert eos.log_probs.numel() == 1


def test_strict_single_file_loading(tmp_path):
    from dataclasses import asdict

    model = tiny_model()
    state = {
        key: val.clone()
        for key, val in model.state_dict().items()
        if not key.endswith((".A", ".B")) and key != "lm_head.weight"
    }
    (tmp_path / "config.json").write_text(json.dumps(asdict(model.config)))
    save_file(state, tmp_path / "model.safetensors")
    loaded, report = load_model(tmp_path, "cpu", torch.float32, rank=4, alpha=4)
    assert report["tied_embeddings"]
    ids = torch.tensor([[9, 10]])
    torch.testing.assert_close(model(ids)[0], loaded(ids)[0])
    state.pop("model.layers.0.self_attn.q_norm.weight")
    save_file(state, tmp_path / "model.safetensors")
    with pytest.raises(ValueError, match="Base weight keys"):
        load_model(tmp_path, "cpu", torch.float32, rank=4, alpha=4)


def test_hf_tiny_parity():
    from transformers import Qwen3Config, Qwen3ForCausalLM

    cfg = Qwen3Config(
        vocab_size=259,
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        head_dim=8,
        rope_theta=1000000.0,
        tie_word_embeddings=True,
        attention_dropout=0,
    )
    cfg._attn_implementation = "eager"
    hf = Qwen3ForCausalLM(cfg).eval()
    model = tiny_model().eval()
    missing, unexpected = model.load_state_dict(hf.state_dict(), strict=False)
    assert not unexpected and all(name.endswith((".A", ".B")) for name in missing)
    model.attention_impl = "eager"
    ids = torch.tensor([[10, 11, 12], [0, 21, 22]])
    mask = torch.tensor([[1, 1, 1], [0, 1, 1]])
    with torch.no_grad():
        expected = hf(
            ids, attention_mask=mask, position_ids=(mask.cumsum(-1) - 1).clamp_min(0)
        ).logits
        actual = model(ids, attention_mask=mask)[0]
    torch.testing.assert_close(actual[mask.bool()], expected[mask.bool()], atol=1e-5, rtol=1e-5)
