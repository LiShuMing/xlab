# LLM observability lab

Read the repository root AGENTS.md and RULES.md first. Keep this lab independent of other labs.

- All downloads, environments, rendered configuration, PID state, logs, TSDB and captures belong
  under ignored `.local/`. Never vendor upstream source or copy real traces into fixtures/docs.
- Download only fixed public release assets listed in `releases.json`; verify SHA256 before use.
- Lifecycle commands own only recorded PID identities. Never kill a listener or restart a model
  implicitly. Preserve unrelated processes and existing workspace changes.
- Keep per-request content out of exported spans by default. Do not put request/trace IDs in
  Prometheus labels. Missing/stale host probes are not zero usage.
- Run pytest, Ruff, native configuration validation and synthetic smoke when relevant.
  Exercise start/stop idempotence and verify Git exclusions; don't stage/commit automatically.
- Explicit model lifecycle commands use private `.local/run/vllm-profile.json` and PID identities.
  Adoption of an unmanaged listener requires its exact PID. Preflight and idle checks precede stop.
- Core/Scheduler/Metal host tracing supports reviewed vLLM 0.33.0 + UniProcExecutor only.
  Keep wrappers in this lab; never add GPU synchronization or edit upstream sources for tracing.
  Shared batches have one execution trace with request Links; pending resolve follows its own batch.
- B=1/B=4 success chains and a small warm detailed/minimal comparison are verified. Remaining:
  real-model error/cancellation, exporter-outage acceptance, broader overhead measurement and
  device-level profiling when justified. Keep cross-condition output differences visible.
  See DESIGN.md.
- Compact defaults to first-output-window batches; buffer numeric host phases until request end.
  Preserve explicit full/off modes. Full decode coverage remains a separate diagnostic mode.
- Fixed KV/cache interleaved controls and queue-policy restoration have been exercised. Reject
  wall/monotonic divergence or incomplete histogram windows; keep failed/superseded runs visible.
  macOS controlled runs use only a bounded caffeinate assertion, never change power settings.
