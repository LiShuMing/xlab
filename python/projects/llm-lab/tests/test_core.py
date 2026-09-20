from pathlib import Path

import pytest
import torch

from llm_lab import checkpoint
from llm_lab.data import prepare
from llm_lab.generate import generate
from llm_lab.model import LanguageModel, ModelConfig
from llm_lab.tokenizer import BOS, EOS, PAD, decode, encode
from llm_lab.train import train


@pytest.fixture(autouse=True)
def deterministic():
    torch.set_num_threads(2)
    torch.manual_seed(7)


def test_byte_roundtrip_and_validation():
    text = "你好，GPU! 🙂"
    assert decode([BOS] + encode(text) + [EOS, PAD]) == text
    assert encode("") == []
    with pytest.raises(ValueError):
        decode([259])


def test_causality_and_gradient():
    model = LanguageModel(ModelConfig(hidden_size=16, num_heads=2, ffn_size=32))
    ids = torch.tensor([[1, 2, 3, 4]])
    changed = torch.tensor([[1, 2, 9, 8]])
    torch.testing.assert_close(model(ids)[:, :2], model(changed)[:, :2])
    output = model(ids)
    assert output.shape == (1, 4, 259)
    output.sum().backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    with pytest.raises(ValueError):
        model(torch.ones(1, 65, dtype=torch.long))


def test_document_split_is_repeatable(tmp_path: Path):
    a, b, metadata = prepare(None, 16, 42)
    c, d, other = prepare(None, 16, 42)
    assert metadata == other
    assert metadata["train_documents"] + metadata["validation_documents"] == 64
    assert torch.equal(a[0], c[0]) and torch.equal(b[0], d[0])
    bad = tmp_path / "bad.txt"
    bad.write_text("same\nsame\n")
    with pytest.raises(ValueError):
        prepare(bad, 16, 42)


def config(steps: int) -> dict:
    return {
        "model": {
            "kind": "tiny",
            "hidden_size": 16,
            "num_heads": 2,
            "num_layers": 1,
            "ffn_size": 32,
            "context_length": 32,
        },
        "training": {
            "steps": steps,
            "batch_size": 4,
            "learning_rate": 0.01,
            "seed": 9,
            "threads": 2,
        },
    }


def test_training_reload_resume_and_generation(tmp_path: Path):
    full, part, resumed = (tmp_path / x for x in ("full", "part", "resumed"))
    report = train(config(12), full, "cpu")
    assert report["final_validation_loss"] < report["initial_validation_loss"]
    train(config(6), part, "cpu")
    train(config(12), resumed, "cpu", resume=part / "last.pt")
    model, payload = checkpoint.load(full / "last.pt", torch.device("cpu"))
    restored, resumed_payload = checkpoint.load(resumed / "last.pt", torch.device("cpu"))
    assert payload["step"] == resumed_payload["step"] == 12
    for key, value in model.state_dict().items():
        torch.testing.assert_close(value, restored.state_dict()[key], rtol=0, atol=0)
    x = torch.tensor([[BOS, 65, 100, 97]])
    torch.testing.assert_close(model(x), restored(x), rtol=0, atol=0)
    output = generate(full / "last.pt", "Ada", 4, "cpu")
    assert len(output["token_ids"]) <= 4
    assert generate(full / "last.pt", "", 0, "cpu")["token_ids"] == []
    with pytest.raises(ValueError):
        generate(full / "last.pt", "x" * 33, 1, "cpu")
    with pytest.raises(ValueError):
        train(config(6), resumed, "cpu", resume=part / "last.pt")


def test_tiny_can_overfit():
    model = LanguageModel(
        ModelConfig(num_layers=1, hidden_size=16, num_heads=2, ffn_size=32, context_length=8)
    )
    x, y = torch.tensor([[BOS, 65, 66, 67]]), torch.tensor([[65, 66, 67, EOS]])
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.03)
    for _ in range(100):
        loss = torch.nn.functional.cross_entropy(model(x).flatten(0, 1), y.flatten())
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    assert loss.item() < 0.05


def test_bigram_forward():
    model = LanguageModel(ModelConfig(kind="bigram"))
    logits = model(torch.tensor([[1, 2, 1]]))
    torch.testing.assert_close(logits[:, 0], logits[:, 2])


def test_resume_rejects_changed_data(tmp_path: Path):
    first = tmp_path / "a.txt"
    first.write_text("one\ntwo\nthree\nfour\n")
    out = tmp_path / "run"
    train(config(1), out, "cpu", data_path=first)
    first.write_text("one\ntwo\nthree\nfive\n")
    with pytest.raises(ValueError, match="data differs"):
        train(config(2), tmp_path / "next", "cpu", first, out / "last.pt")


def test_configuration_rejects_invalid_shapes():
    with pytest.raises(ValueError):
        ModelConfig(hidden_size=15, num_heads=4)
    with pytest.raises(ValueError):
        ModelConfig(num_layers=0)
    with pytest.raises(ValueError):
        ModelConfig(layer_norm_eps=float("nan"))


def test_generation_eos_and_capacity(tmp_path: Path):
    model = LanguageModel(ModelConfig(kind="bigram", context_length=4))
    with torch.no_grad():
        model.token_embedding.weight.zero_()
        model.token_embedding.weight[:, EOS] = 10
    path = tmp_path / "constant.pt"
    checkpoint.save(
        path,
        {"format_version": 1, "model_config": model.config.to_dict(), "model": model.state_dict()},
    )
    result = generate(path, "A", 3, "cpu")
    assert result["finish_reason"] == "eos" and result["token_ids"] == [EOS]
    with torch.no_grad():
        model.token_embedding.weight.zero_()
        model.token_embedding.weight[:, 65] = 10
    checkpoint.save(
        path,
        {"format_version": 1, "model_config": model.config.to_dict(), "model": model.state_dict()},
    )
    result = generate(path, "AAA", 3, "cpu")
    assert result["finish_reason"] == "context_limit"
    assert result["token_ids"] == [65]
