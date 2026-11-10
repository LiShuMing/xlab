# Reasoning Lab agent instructions

- Read the repository root AGENTS.md and RULES.md before work.
- This lab is self-contained. Do not import either reference checkout or other labs.
- Keep model weights, generated data, checkpoints, telemetry and machine paths in ignored `.local/`.
- Run `uv run pytest`, `uv run ruff check .`, and `uv run ruff format --check .`.
- Algorithm changes require tiny-model invariants before real-model runs.
- Preserve frozen test/OOD data; use train/dev only to select subsequent experiments.
- Never describe a random tiny-model smoke as evidence that pretrained Qwen3 has learned.
- No automatic commit, upload, external judge, unbounded training, or artifact deletion.
