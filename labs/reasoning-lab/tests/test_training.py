import copy

import pytest
import torch

from reasoning_lab.experiments import tiny_model
from reasoning_lab.generation import sft_loss_sum
from reasoning_lab.runs import load_checkpoint, save_checkpoint
from reasoning_lab.training import grpo_loss, normalized_advantages


def test_grpo_same_reward_no_task_gradient_and_initial_ratio_one():
    model = tiny_model()
    from reasoning_lab.generation import response_log_probs

    probabilities = response_log_probs(model, [8, 9], [10, 11, 2], 0.7)
    old = probabilities.detach().clone()
    advantage = normalized_advantages(torch.tensor([1.0, 1.0, 1.0, 1.0]))[0]
    loss, metrics = grpo_loss(probabilities, old, old, advantage, 0.02, 0.2)
    assert loss.item() == 0
    assert metrics["ratio_min"] == metrics["ratio_max"] == 1
    loss.backward()
    assert all(p.grad is None or torch.count_nonzero(p.grad) == 0 for p in model.parameters())
    torch.testing.assert_close(
        normalized_advantages(torch.tensor([0.0, 1.0])), torch.tensor([-1.0, 1.0])
    )


def test_reference_swap_restores_and_anchor_changes_kl():
    model = tiny_model()
    starting = model.adapter_state()
    changed = {name: value + 0.1 for name, value in starting.items()}
    model.load_adapter(changed)
    with model.adapters_as(starting):
        for name, value in model.adapter_state().items():
            torch.testing.assert_close(value, starting[name])
    for name, value in model.adapter_state().items():
        torch.testing.assert_close(value, changed[name])


def test_resume_optimizer_rng_and_protocol(tmp_path):
    model = tiny_model()
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-3)

    def update(m, opt):
        opt.zero_grad()
        loss, _ = sft_loss_sum(m, [8, 9], [10, 11, 2])
        loss.backward()
        opt.step()

    update(model, optimizer)
    protocol = {"model": "tiny", "data": "fixed", "training": {"seed": 42}}
    path = tmp_path / "checkpoint.pt"
    save_checkpoint(path, model, optimizer, 1, 2, protocol, "cpu", 1.5, None, 0.5)
    expected_random = torch.rand(4)
    update(model, optimizer)
    expected = copy.deepcopy(model.adapter_state())
    restored = tiny_model(seed=99)
    # Base weights are immutable external inputs, so use the same base as the original run.
    base = tiny_model(seed=42).state_dict()
    restored.load_state_dict(base)
    opt = torch.optim.AdamW([p for p in restored.parameters() if p.requires_grad], lr=1e-3)
    saved = load_checkpoint(path, restored, protocol, opt)
    assert saved["step"] == 1 and saved["cursor"] == 2
    torch.testing.assert_close(torch.rand(4), expected_random)
    update(restored, opt)
    for name, value in restored.adapter_state().items():
        torch.testing.assert_close(value, expected[name], atol=0, rtol=0)
    with pytest.raises(ValueError, match="protocol mismatch"):
        load_checkpoint(path, restored, {**protocol, "model": "other"}, opt)


def test_loop_resume_matches_continuous_and_final_keeps_optimizer_policy(tmp_path):
    import time
    from dataclasses import replace

    from reasoning_lab.config import Config
    from reasoning_lab.experiments import ByteTokenizer
    from reasoning_lab.runs import Run
    from reasoning_lab.runtime import Monitor
    from reasoning_lab.training import train

    task = {
        "task_id": "f" * 64,
        "task": "countdown",
        "difficulty": "L1",
        "prompt": "1, 2 -> 3",
        "answer": "1+2",
        "payload": {"numbers": [1, 2], "target": 3, "ops": "+"},
    }
    cfg = Config(
        stage="sft",
        steps=4,
        samples=1,
        max_length=128,
        max_new_tokens=2,
        eval_every=99,
        save_every=99,
        output=str(tmp_path / "runs"),
        rank=4,
        alpha=4,
        max_seconds=120,
    )

    def execute(model, config):
        run = Run(config, "cpu", {"hash": "tiny"}, {"fixed": True})
        with Monitor(run.path / "system.jsonl", "cpu") as monitor:
            result = train(
                model, ByteTokenizer(), [task], [task], config, run, monitor, time.monotonic()
            )
        return run, result

    continuous = tiny_model()
    execute(continuous, cfg)
    first = tiny_model()
    first_run, _ = execute(first, replace(cfg, steps=3))
    checkpoint = first_run.path / "checkpoints" / "final.pt"
    restored = tiny_model()
    resumed_run, result = execute(restored, replace(cfg, resume=str(checkpoint)))
    assert result["updates"] == 4 and result["cursor"] == 4
    final = torch.load(resumed_run.path / "checkpoints" / "final.pt", weights_only=True)
    for name, value in restored.adapter_state().items():
        torch.testing.assert_close(value, continuous.adapter_state()[name], atol=0, rtol=0)
        torch.testing.assert_close(value, final["adapter"][name], atol=0, rtol=0)


def test_mixed_rewards_push_success_probability_up():
    # A two-action policy with one successful action gives an analytic gradient direction.
    logits = torch.nn.Parameter(torch.zeros(2))
    old = logits.log_softmax(0).detach()
    advantages = normalized_advantages(torch.tensor([1.0, 0.0]))
    optimizer = torch.optim.SGD([logits], lr=0.1)
    loss = (
        sum(
            grpo_loss(
                logits.log_softmax(0)[i : i + 1],
                old[i : i + 1],
                old[i : i + 1],
                advantages[i],
                0.0,
                0.2,
            )[0]
            for i in range(2)
        )
        / 2
    )
    loss.backward()
    optimizer.step()
    assert logits.softmax(0)[0] > 0.5
