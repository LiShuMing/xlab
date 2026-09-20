"""Device selection and reproducible environment metadata."""

import platform
import subprocess

import torch


def device_for(name: str) -> torch.device:
    if name == "auto":
        name = "mps" if torch.backends.mps.is_available() else "cpu"
    if name not in {"cpu", "mps"}:
        raise ValueError("Device must be cpu, mps or auto")
    if name == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS requested but unavailable; choose cpu explicitly")
    return torch.device(name)


def synchronize(device: torch.device) -> None:
    if device.type == "mps":
        torch.mps.synchronize()


def environment() -> dict:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    )
    return {
        "python": platform.python_version(),
        "torch": str(torch.__version__),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "mps_built": torch.backends.mps.is_built(),
        "mps_available": torch.backends.mps.is_available(),
        "git_commit": result.stdout.strip() or "unknown",
        "git_dirty": bool(dirty.stdout.strip()),
    }
