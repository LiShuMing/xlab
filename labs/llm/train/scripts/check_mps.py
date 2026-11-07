"""Explicit GPU acceptance check, separate from CPU-only unit tests."""

import json
from pathlib import Path

import torch

from llm_lab.checkpoint import load
from llm_lab.generate import generate
from llm_lab.runtime import device_for, environment
from llm_lab.tokenizer import BOS, encode

mps = device_for("mps")
path = Path("runs/tiny-mps/last.pt")
cpu_model, _ = load(path, torch.device("cpu"))
gpu_model, _ = load(path, mps)
cpu_model.eval()
gpu_model.eval()
ids = torch.tensor([[BOS] + encode("Ada likes ")])
with torch.no_grad():
    cpu = cpu_model(ids)
    gpu = gpu_model(ids.to(mps)).cpu()
assert torch.isfinite(gpu).all()
torch.testing.assert_close(cpu, gpu, atol=1e-4, rtol=1e-4)
result = {
    "environment": environment(),
    "atol": 1e-4,
    "rtol": 1e-4,
    "max_absolute_error": float((cpu - gpu).abs().max()),
    "generation": generate(path, "Ada likes ", 40, "mps"),
}
Path("runs/mps-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
