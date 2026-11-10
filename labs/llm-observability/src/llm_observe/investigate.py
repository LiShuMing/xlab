"""Validate linked host traces before comparing matched diagnostic requests."""

import hashlib
import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from prometheus_client.parser import text_string_to_metric_families

from llm_observe.client import probe
from llm_observe.manager import STATE, get
from llm_observe.paths import LOCAL, write_json
from llm_observe.smoke import query_trace

PROMPT = "只用两句中文解释数据库索引：第一句说明作用，第二句给出一个适用场景。"


def tags(values) -> dict:
    return {value["key"]: value["value"] for value in values}


def metric(text: str, name: str, **labels) -> float:
    values = [
        sample.value
        for family in text_string_to_metric_families(text)
        for sample in family.samples
        if sample.name == name
        and all(sample.labels.get(key) == value for key, value in labels.items())
    ]
    if not values:
        raise ValueError(f"Missing investigation metric: {name}")
    return sum(values)


def elapsed(span) -> float:
    return span["duration"] / 1000


def covered_ms(spans: list[dict], start_us: int, end_us: int) -> float:
    """Clip overlapping host intervals to the measured request window."""
    intervals = sorted(
        (max(start_us, span["startTime"]), min(end_us, span["startTime"] + span["duration"]))
        for span in spans
    )
    covered = 0
    end = start_us
    for left, right in intervals:
        if right > max(left, end):
            covered += right - max(left, end)
            end = right
    return covered / 1000


def inspect_request(result: dict, ui_port: int, detailed: bool) -> dict:
    artifact = Path(result["artifact_dir"])
    summary = json.loads((artifact / "summary.json").read_text())
    required = {"client.request", "http.server", "llm_request"}
    if detailed:
        required |= {
            "core.request",
            "core.input.preprocess",
            "api.chat.render",
            "api.engine.ingress",
            "api.core.enqueue",
            "api.output.received",
        }
    trace = query_trace(ui_port, result["trace_id"], required_names=required)
    write_json(artifact / "trace.json", trace)
    spans = trace["data"][0]["spans"]
    if any(tags(span["tags"]).get("error") is True for span in spans):
        raise RuntimeError("Successful model request has an error span")
    server = next(span for span in spans if span["operationName"] == "http.server")
    if tags(server["tags"]).get("llm.response_body_complete") is not True:
        raise RuntimeError("Server trace did not cover the final response body")
    inputs = None
    for line in (artifact / "events.jsonl").read_text().splitlines():
        data = json.loads(line)["data"]
        if data != "[DONE]":
            ids = json.loads(data).get("prompt_token_ids")
            if ids is not None:
                inputs = ids
    if inputs is None:
        raise RuntimeError("Prompt IDs missing from diagnostic stream")
    observed = {
        "trace_id": result["trace_id"],
        "artifact_dir": str(artifact),
        "detailed": detailed,
        "usage": summary["usage"],
        "prompt_ids_sha256": hashlib.sha256(json.dumps(inputs).encode()).hexdigest(),
        "output_ids_sha256": hashlib.sha256(
            json.dumps(summary["output_token_ids"]).encode()
        ).hexdigest(),
        "client_ttft_ms": (summary["first_token_ns"] - summary["started_ns"]) / 1e6,
        "client_e2e_ms": (summary["done_ns"] - summary["started_ns"]) / 1e6,
        "batch_trace_ids": [],
        "api_batch_trace_ids": [],
        "phases": {},
        "max_shared_request_count": 0,
    }
    if not detailed:
        if any(span["operationName"] == "core.request" for span in spans):
            raise RuntimeError("Minimal-trace control unexpectedly contains detailed spans")
        return observed
    core = [span for span in spans if span["operationName"] == "core.request"]
    if len(core) != 1:
        raise RuntimeError("Expected one core request span")
    core = core[0]
    event_times = {}
    for event in core.get("logs", []):
        fields = tags(event["fields"])
        event_times[fields["event"]] = event["timestamp"]
        if fields["event"] == "batch.scheduled":
            observed["batch_trace_ids"].append(fields["llm.batch_trace_id"])
    events = {
        "core.input.received",
        "request.queued",
        "request.first_scheduled",
        "core.first_output.ready",
        "core.last_output.ready",
        "request.finished",
        "kv.references_released",
    }
    if not events <= event_times.keys():
        raise RuntimeError("Core request lifecycle is incomplete")
    observed["core_events_us"] = event_times
    observed["core_queue_ms"] = (
        event_times["request.first_scheduled"] - event_times["request.queued"]
    ) / 1000
    observed["core_prefill_ms"] = (
        event_times["core.first_output.ready"] - event_times["request.first_scheduled"]
    ) / 1000
    observed["core_ingress_to_queue_ms"] = (
        event_times["request.queued"] - event_times["core.input.received"]
    ) / 1000
    observed["core_span_id"] = core["spanID"]
    observed["core_attributes"] = tags(core["tags"])
    offsets = [
        int(tags(span["tags"])["clock.epoch_minus_monotonic_ns"])
        for span in spans
        if "clock.epoch_minus_monotonic_ns" in tags(span["tags"])
    ]
    observed["cross_process_clock_offset_spread_ns"] = max(offsets) - min(offsets)
    if observed["cross_process_clock_offset_spread_ns"] > 1_000_000:
        raise RuntimeError("Process clock offsets differ by more than 1 ms")
    observed["core_request_id"] = tags(core["tags"])["llm.request_id"]
    api_ids = {
        tags(span["tags"])["llm.api_batch_trace_id"]
        for span in spans
        if span["operationName"] == "api.output.received"
    }
    observed["api_batch_trace_ids"] = sorted(api_ids)
    observed["batch_trace_ids"] = sorted(set(observed["batch_trace_ids"]))
    combined = []
    for trace_id in observed["batch_trace_ids"]:
        batch = query_trace(
            ui_port,
            trace_id,
            required_names={
                "batch.execution",
                "scheduler.schedule",
                "runner.execute.host",
                "scheduler.update_output",
            },
        )
        write_json(artifact / f"batch-{trace_id}.json", batch)
        group = batch["data"][0]["spans"]
        root = next(span for span in group if span["operationName"] == "batch.execution")
        attributes = tags(root["tags"])
        expected = observed["core_attributes"]
        for span in group:
            actual = tags(span["tags"])
            if any(
                actual.get(key) != expected[key]
                for key in ("llm.run_id", "llm.process_instance_id", "process.pid")
            ):
                raise RuntimeError("Batch trace contains data from another model process/run")
        references = root["references"]
        if len(references) != attributes["llm.sampled_request_count"] or len(
            {(ref["traceID"], ref["spanID"]) for ref in references}
        ) != len(references):
            raise RuntimeError("Shared batch links are missing or duplicated")
        if not any(
            ref["traceID"] == result["trace_id"] and ref["spanID"] == core["spanID"]
            for ref in root["references"]
        ):
            raise RuntimeError("Shared batch is not linked to its actual core request")
        observed["max_shared_request_count"] = max(
            observed["max_shared_request_count"], attributes["llm.request_count"]
        )
        combined.extend(group)
    for trace_id in api_ids:
        api = query_trace(
            ui_port, trace_id, required_names={"api.output.batch", "api.output.process_batch"}
        )
        write_json(artifact / f"api-batch-{trace_id}.json", api)
        combined.extend(api["data"][0]["spans"])
    phase_names = {
        "runner.prepare_submit.host",
        "mlx.forward.graph.host",
        "mlx.async_submit.host",
        "runner.sample.host",
        "mlx.sample_materialize.host",
        "mlx.sampling_eval.host",
        "mlx.deferred.resolve.host",
        "api.output.process_batch",
    }
    if not phase_names <= {span["operationName"] for span in combined}:
        raise RuntimeError("Metal/MLX or API host phases are incomplete")
    first_time = event_times["core.first_output.ready"]
    for name in phase_names | {"api.chat.render", "api.engine.ingress", "api.core.enqueue"}:
        values = [span for span in spans + combined if span["operationName"] == name]
        observed["phases"][name] = {
            "count": len(values),
            "median_ms": statistics.median(map(elapsed, values)),
            "before_first_output_covered_ms": covered_ms(
                values, event_times["request.first_scheduled"], first_time
            ),
        }
    first_api = min(
        (span for span in spans if span["operationName"] == "api.output.received"),
        key=lambda span: span["startTime"],
    )
    enqueue = next(span for span in spans if span["operationName"] == "api.core.enqueue")
    observed["core_to_api_first_output_ms"] = (first_api["startTime"] - first_time) / 1000
    observed["enqueue_to_core_receive_ms"] = (
        event_times["core.input.received"] - enqueue["startTime"]
    ) / 1000
    write_json(artifact / "host-analysis.json", observed)
    return observed


def run(model: str) -> None:
    state = json.loads(STATE.read_text())
    artifact = LOCAL / "artifacts" / f"investigation-{uuid4().hex}"
    artifact.mkdir()
    print(f"Investigation artifacts: {artifact}", flush=True)
    initial = get(state["model_url"] + "/metrics").decode()
    if metric(initial, "vllm:request_success_total") != 0:
        raise RuntimeError("Cold observation requires an explicit fresh model restart")
    write_json(
        artifact / "experiment.json",
        {
            "model": model,
            "state": state,
            "started_epoch_ns": time.time_ns(),
            "model_process": json.loads((LOCAL / "run" / "vllm-process.json").read_text()),
            "source_manifest": json.loads(
                (LOCAL / "run" / "instrumentation-source.json").read_text()
            ),
            "control_scope": "detailed spans off; base client/API/vLLM tracing remains on",
        },
    )
    stop = threading.Event()
    sample_errors = []

    def sample():
        try:
            with (artifact / "host-window.jsonl").open("w") as output:
                while not stop.is_set():
                    started = time.time_ns()
                    text = get(f"http://127.0.0.1:{state['ports']['exporter']}/metrics").decode()
                    output.write(json.dumps({"epoch_ns": started, "metrics": text}) + "\n")
                    output.flush()
                    stop.wait(1)
        except Exception as error:
            sample_errors.append(error)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    rows = []
    captured_requests = []
    try:
        # First request is explicitly kept as cold-after-restart, not pooled with warm controls.
        cases = (
            [("cold", True, 1)]
            + [
                (label, detail, 1)
                for label, detail in [
                    ("full", True),
                    ("minimal", False),
                    ("minimal", False),
                    ("full", True),
                ]
                * 2
            ]
            + [("batch4", True, 4)]
        )
        for index, (label, detailed, concurrency) in enumerate(cases):
            print(f"Collecting {index + 1}/{len(cases)}: {label}, B={concurrency}", flush=True)
            before = get(state["model_url"] + "/metrics").decode()
            (artifact / f"{index:02d}-metrics-before.txt").write_text(before)
            barrier = threading.Barrier(concurrency)
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = [
                    pool.submit(probe, model, PROMPT, 256, True, not detailed, True, barrier)
                    for _ in range(concurrency)
                ]
                requests = [future.result() for future in futures]
            captured_requests.extend(
                {"case": label, "index": index, **request} for request in requests
            )
            write_json(artifact / "requests.json", captured_requests)
            after = get(state["model_url"] + "/metrics").decode()
            (artifact / f"{index:02d}-metrics-after.txt").write_text(after)
            deltas = {
                name: metric(after, name) - metric(before, name)
                for name in [
                    "vllm:request_success_total",
                    "vllm:prompt_tokens_total",
                    "vllm:generation_tokens_total",
                    "vllm:prefix_cache_hits_total",
                    "vllm:prefix_cache_queries_total",
                    "vllm:time_to_first_token_seconds_sum",
                    "vllm:request_prefill_time_seconds_sum",
                ]
            }
            if deltas["vllm:request_success_total"] != concurrency:
                raise RuntimeError("Request metric window is contaminated or unsettled")
            observations = [
                inspect_request(request, state["ports"]["jaeger_ui"], detailed)
                for request in requests
            ]
            for observed in observations:
                rows.append(
                    {
                        "case": label,
                        "index": index,
                        "concurrency": concurrency,
                        "metric_deltas": deltas,
                        **observed,
                    }
                )
            write_json(artifact / "observations.json", rows)
        if sample_errors:
            raise RuntimeError("Host observation failed") from sample_errors[0]
    except BaseException as error:
        write_json(
            artifact / "failure.json",
            {
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "captured_requests": len(captured_requests),
                "automatic_generation_retry": False,
            },
        )
        raise
    finally:
        stop.set()
        sampler.join(timeout=10)
    if sampler.is_alive() or sample_errors:
        raise RuntimeError("Host sampler did not complete successfully")
    report = validate(artifact)
    print(json.dumps({"artifact_dir": str(artifact), **report}, indent=2))


def validate(artifact: Path) -> dict:
    """Validate archived work without regenerating any model response."""
    rows = json.loads((artifact / "observations.json").read_text())
    warm = [row for row in rows if row["case"] in {"full", "minimal"}]
    if len(rows) != 13 or len(warm) != 8:
        raise RuntimeError("Investigation is incomplete")
    if len({row["prompt_ids_sha256"] for row in rows}) != 1:
        raise RuntimeError("Diagnostic input token IDs differ")
    if len({row["output_ids_sha256"] for row in warm}) != 1:
        raise RuntimeError("Matched warm observation controls produced different output IDs")
    for name in (
        "vllm:prefix_cache_hits_total",
        "vllm:prefix_cache_queries_total",
        "vllm:prompt_tokens_total",
        "vllm:generation_tokens_total",
    ):
        if len({row["metric_deltas"][name] for row in warm}) != 1:
            raise RuntimeError("Warm control cache/workload metrics differ")
    if metric((artifact / "00-metrics-before.txt").read_text(), "vllm:request_success_total") != 0:
        raise RuntimeError("Cold observation did not start on a fresh server")
    if max(row["max_shared_request_count"] for row in rows if row["case"] == "batch4") < 2:
        raise RuntimeError("Concurrent validation did not produce shared execution")
    validate_host_samples(artifact)
    report = {
        "status": "pass",
        "requests": len(rows),
        "same_input_ids": True,
        "matched_warm_same_output_ids": True,
        "shared_batches_verified": True,
        "cross_condition_output_variants": len({row["output_ids_sha256"] for row in rows}),
        "gpu_pure_execution_measured": False,
        "control_scope": "detailed spans only; base tracing stays enabled",
        "host_probe_freshness_verified": True,
        "limitations": [
            "Cold/cache and batch shapes can produce different greedy output IDs",
            "Small diagnostic sample; not a throughput or model parity benchmark",
            "Real-model cancellation and exporter-outage acceptance remain pending",
        ],
    }
    write_json(artifact / "acceptance.json", report)
    return report


def validate_host_samples(artifact: Path) -> None:
    samples = [
        json.loads(line) for line in (artifact / "host-window.jsonl").read_text().splitlines()
    ]
    if not samples:
        raise RuntimeError("Host observation is empty")
    for sample in samples:
        for probe_name in ("vm_stat", "ioreg", "process", "system"):
            age = sample["epoch_ns"] / 1e9 - metric(
                sample["metrics"],
                "metal_host_probe_last_success_timestamp_seconds",
                probe=probe_name,
            )
            if (
                metric(sample["metrics"], "metal_host_probe_success", probe=probe_name) != 1
                or age > 15
            ):
                raise RuntimeError("Host observation is missing or stale")
