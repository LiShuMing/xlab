"""Synthetic telemetry acceptance; never invokes the model."""

import json
import time
from urllib.error import URLError
from urllib.parse import urlencode
from uuid import uuid4

from opentelemetry.trace import Link

from llm_observe.manager import STATE, get, owned
from llm_observe.paths import LOCAL, write_json
from llm_observe.telemetry import provider


def query_trace(
    ui_port: int, trace_id: str, timeout: float = 15, required_names: set[str] | None = None
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = json.loads(get(f"http://127.0.0.1:{ui_port}/api/traces/{trace_id}"))
            if result.get("data"):
                names = {span["operationName"] for span in result["data"][0]["spans"]}
                if required_names is None or required_names <= names:
                    return result
        except (URLError, TimeoutError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f"Trace {trace_id} did not become queryable")


def smoke() -> None:
    state = json.loads(STATE.read_text())
    if not all(owned(record) for record in state["processes"].values()):
        raise RuntimeError("Monitoring process is not running")
    ports = state["ports"]
    telemetry = provider("llm-observe-smoke", f"http://127.0.0.1:{ports['otlp_http']}")
    tracer = telemetry.get_tracer("llm_observe.smoke")
    run_id = uuid4().hex
    with tracer.start_as_current_span(
        "synthetic.client", attributes={"test.run_id": run_id}
    ) as root:
        trace_id = f"{root.get_span_context().trace_id:032x}"
        root.add_event("synthetic.request.started")
        with tracer.start_as_current_span("synthetic.server") as server:
            with tracer.start_as_current_span("synthetic.prefill"):
                pass
            server.add_event("synthetic.done")
        context = root.get_span_context()
    # Shared work has one span, with links rather than duplicate child spans.
    with tracer.start_span("synthetic.shared_batch", links=[Link(context)]) as batch:
        batch_trace_id = f"{batch.get_span_context().trace_id:032x}"
    if not telemetry.force_flush(timeout_millis=5000):
        raise RuntimeError("OTLP exporter did not flush")
    telemetry.shutdown()
    result = query_trace(ports["jaeger_ui"], trace_id)
    spans = result["data"][0]["spans"]
    names = {span["operationName"] for span in spans}
    if not {"synthetic.client", "synthetic.server", "synthetic.prefill"} <= names:
        raise RuntimeError("Queried trace is missing expected synthetic spans")
    by_name = {span["operationName"]: span for span in spans}
    for child_name, parent_name in (
        ("synthetic.server", "synthetic.client"),
        ("synthetic.prefill", "synthetic.server"),
    ):
        if not any(
            reference["spanID"] == by_name[parent_name]["spanID"]
            and reference["refType"] == "CHILD_OF"
            for reference in by_name[child_name]["references"]
        ):
            raise RuntimeError("Synthetic trace parent relationships were not preserved")
    batch_result = query_trace(ports["jaeger_ui"], batch_trace_id)
    batch_spans = batch_result["data"][0]["spans"]
    if len(batch_spans) != 1 or not any(
        ref["traceID"] == trace_id for ref in batch_spans[0]["references"]
    ):
        raise RuntimeError("Shared batch link did not survive OTLP storage/query")
    deadline = time.monotonic() + 15
    while True:
        targets = json.loads(get(f"http://127.0.0.1:{ports['prometheus']}/api/v1/targets"))
        active = targets["data"]["activeTargets"]
        health = {target["labels"]["job"]: target["health"] for target in active}
        if all(health.get(job) == "up" for job in ("prometheus", "macos", "jaeger")):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Monitoring targets did not become healthy")
        time.sleep(0.5)
    query = urlencode({"query": 'metal_host_probe_success{probe="vm_stat"}'})
    sample = json.loads(get(f"http://127.0.0.1:{ports['prometheus']}/api/v1/query?{query}"))
    if not sample["data"]["result"] or sample["data"]["result"][0]["value"][1] != "1":
        raise RuntimeError("Host sample missing from Prometheus")
    artifact = LOCAL / "artifacts" / f"smoke-{run_id}"
    artifact.mkdir()
    write_json(artifact / "trace.json", result)
    write_json(artifact / "shared-batch-trace.json", batch_result)
    write_json(artifact / "targets.json", targets)
    report = {
        "status": "pass",
        "generation_requests": 0,
        "trace_id": trace_id,
        "shared_batch_trace_id": batch_trace_id,
        "parent_and_link_checks": True,
        "targets": health,
        "vllm_metrics_connected": health.get("vllm") == "up",
        "coverage": "platform and synthetic spans; not model/Metal end-to-end acceptance",
    }
    write_json(artifact / "report.json", report)
    print(json.dumps({**report, "artifact_dir": str(artifact)}, indent=2))
