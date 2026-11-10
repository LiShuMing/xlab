"""Matched cache/KV diagnostics on one already-running model process."""

import hashlib
import itertools
import json
import statistics
import threading
import time
from pathlib import Path
from uuid import uuid4

from llm_observe.client import probe
from llm_observe.investigate import PROMPT, metric, tags, validate_host_samples
from llm_observe.manager import STATE, get
from llm_observe.paths import LOCAL, write_json
from llm_observe.smoke import query_trace


def timing(result: dict, mode: str, port: int, blocks: int, queue_depth: int) -> dict:
    artifact = Path(result["artifact_dir"])
    summary = json.loads((artifact / "summary.json").read_text())
    required = {"client.request", "http.server", "llm_request"}
    if mode != "off":
        required.add("core.request")
    data = query_trace(port, result["trace_id"], required_names=required)
    write_json(artifact / "trace.json", data)
    spans = data["data"][0]["spans"]
    if any(tags(span["tags"]).get("error") is True for span in spans):
        raise RuntimeError("Successful diagnostic has an error span")
    prompt_ids = None
    for line in (artifact / "events.jsonl").read_text().splitlines():
        event = json.loads(line)["data"]
        if event != "[DONE]":
            prompt_ids = json.loads(event).get("prompt_token_ids") or prompt_ids
    if prompt_ids is None:
        raise RuntimeError("Diagnostic prompt IDs missing")
    row = {
        **result,
        "mode": mode,
        "ttft_ms": (summary["first_token_ns"] - summary["started_ns"]) / 1e6,
        "e2e_ms": (summary["done_ns"] - summary["started_ns"]) / 1e6,
        "prompt_hash": hashlib.sha256(json.dumps(prompt_ids).encode()).hexdigest(),
        "output_hash": hashlib.sha256(json.dumps(summary["output_token_ids"]).encode()).hexdigest(),
        "request_trace_span_count": len(spans),
    }
    client_span = next(span for span in spans if span["operationName"] == "client.request")
    row["wall_clock_span_ms"] = client_span["duration"] / 1000
    row["wall_monotonic_difference_ms"] = row["wall_clock_span_ms"] - row["e2e_ms"]
    if abs(row["wall_monotonic_difference_ms"]) > 50:
        write_json(artifact / "clock-divergence.json", row)
        raise RuntimeError(
            "Wall/monotonic clocks diverged; suspend or clock step contaminated the run"
        )
    if mode == "off":
        if any(s["operationName"] == "core.request" for s in spans):
            raise RuntimeError("Detailed spans unexpectedly present in off control")
        return row
    core = next(span for span in spans if span["operationName"] == "core.request")
    attrs = tags(core["tags"])
    expected = {
        "llm.kv_blocks": blocks,
        "llm.queue_depth": queue_depth,
        "llm.prefix_caching": False,
        "llm.prompt_cached_tokens": 0,
        "llm.prompt_local_computed_tokens": len(prompt_ids),
    }
    if any(attrs.get(k) != v for k, v in expected.items()):
        raise RuntimeError("Actual core cache/KV/queue differs from controlled condition")
    row["core_attributes"] = attrs
    events = [{**tags(event["fields"]), "epoch_us": event["timestamp"]} for event in core["logs"]]
    by_name = {event["event"]: event for event in events}
    required_events = {
        "request.queued",
        "request.first_scheduled",
        "core.first_output.ready",
        "request.finished",
        "kv.references_released",
        "core.last_output.ready",
    }
    if not required_events <= by_name.keys():
        raise RuntimeError("Core lifecycle is incomplete")
    first = by_name["core.first_output.ready"]["monotonic_ns"]
    scheduled = by_name["request.first_scheduled"]["monotonic_ns"]
    row["prefill_ms"] = (first - scheduled) / 1e6
    batches = sorted(
        [e for e in events if e["event"] == "batch.scheduled"],
        key=lambda event: event["llm.batch_id"],
    )
    row["batch_roots"] = len(batches)
    if mode == "compact" and len(batches) > queue_depth:
        raise RuntimeError("Compact tracing continued beyond the first-output window")
    phases = []
    for index, event in enumerate(batches[:2]):
        batch = query_trace(port, event["llm.batch_trace_id"], required_names={"batch.execution"})
        write_json(artifact / f"batch-{event['llm.batch_trace_id']}.json", batch)
        group = batch["data"][0]["spans"]
        root = next(span for span in group if span["operationName"] == "batch.execution")
        if not any(
            ref["traceID"] == result["trace_id"] and ref["spanID"] == core["spanID"]
            for ref in root["references"]
        ):
            raise RuntimeError("Batch/request link is incorrect")
        for span in group:
            values = tags(span["tags"])
            if any(
                values.get(k) != attrs[k]
                for k in ("llm.run_id", "llm.process_instance_id", "process.pid")
            ):
                raise RuntimeError("Batch provenance differs from the active core")
        if mode == "compact":
            for log in root.get("logs", []):
                values = tags(log["fields"])
                if "host.duration_ns" in values:
                    phases.append({"batch": index, "name": values.pop("event"), **values})
        else:
            for span in group:
                values = tags(span["tags"])
                if "host.start_monotonic_ns" in values:
                    phases.append(
                        {
                            "batch": index,
                            "name": span["operationName"],
                            **values,
                            "host.duration_ns": values["host.end_monotonic_ns"]
                            - values["host.start_monotonic_ns"],
                        }
                    )
    row["phases"] = phases
    sample = next(p for p in phases if p["batch"] == 0 and p["name"] == "runner.sample.host")
    row["sample_to_core_output_ms"] = (first - sample["host.end_monotonic_ns"]) / 1e6
    intervals = [
        (
            max(sample["host.end_monotonic_ns"], p["host.start_monotonic_ns"]),
            min(first, p["host.end_monotonic_ns"]),
        )
        for p in phases
        if p["batch"] == 1
        and p["name"] in {"scheduler.schedule", "runner.execute.host", "runner.sample.host"}
    ]
    row["lookahead_host_ms"] = sum(max(0, end - start) for start, end in intervals) / 1e6
    if mode == "compact" and not any(p["name"] == "mlx.async_eval.call.host" for p in phases):
        raise RuntimeError("Native async_eval boundary is missing")
    write_json(artifact / "controlled-timing.json", row)
    return row


def run(
    model: str, label: str, rounds: int, modes: list[str], blocks: int, queue_depth: int
) -> None:
    if rounds < 2 or blocks < 1 or queue_depth not in {1, 2}:
        raise ValueError("Invalid controlled experiment size/configuration")
    if (
        len(modes) < 2
        or len(set(modes)) != len(modes)
        or not set(modes) <= {"off", "compact", "full"}
    ):
        raise ValueError("Supply distinct off/compact/full comparison modes")
    state = json.loads(STATE.read_text())
    process = json.loads((LOCAL / "run" / "vllm-process.json").read_text())
    profile = json.loads((LOCAL / "run" / "vllm-profile.json").read_text())
    if "--no-enable-prefix-caching" not in profile["args"]:
        raise RuntimeError("This controlled prefill experiment requires prefix caching disabled")
    artifact = LOCAL / "artifacts" / f"controlled-{uuid4().hex}"
    artifact.mkdir()
    print(f"Controlled artifacts: {artifact}", flush=True)
    write_json(
        artifact / "experiment.json",
        {
            "label": label,
            "model": model,
            "profile": profile,
            "process": process,
            "rounds": rounds,
            "modes": modes,
            "expected_kv_blocks": blocks,
            "expected_queue_depth": queue_depth,
            "source_manifest": json.loads(
                (LOCAL / "run" / "instrumentation-source.json").read_text()
            ),
        },
    )
    stop = threading.Event()
    errors = []

    def sample():
        try:
            with (artifact / "host-window.jsonl").open("w") as output:
                while not stop.is_set():
                    output.write(
                        json.dumps(
                            {
                                "epoch_ns": time.time_ns(),
                                "metrics": get(
                                    f"http://127.0.0.1:{state['ports']['exporter']}/metrics"
                                ).decode(),
                            }
                        )
                        + "\n"
                    )
                    output.flush()
                    stop.wait(1)
        except Exception as error:
            errors.append(error)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    rows = []
    try:
        # Warm compilation/allocator state with exactly the same uncached prompt shape.
        warmups = [probe(model, PROMPT, 256, True, quiet=True, trace_mode="off") for _ in range(3)]
        write_json(artifact / "warmups.json", warmups)
        orders = list(itertools.permutations(modes))
        for cycle in range(rounds):
            for mode in orders[cycle % len(orders)]:
                before = get(state["model_url"] + "/metrics").decode()
                result = probe(model, PROMPT, 256, True, quiet=True, trace_mode=mode)
                after = get(state["model_url"] + "/metrics").decode()
                index = len(rows)
                (artifact / f"{index:03d}-metrics-before.txt").write_text(before)
                (artifact / f"{index:03d}-metrics-after.txt").write_text(after)
                write_json(artifact / "latest-request.json", result)
                deltas = {
                    name: metric(after, name) - metric(before, name)
                    for name in (
                        "vllm:request_success_total",
                        "vllm:prompt_tokens_total",
                        "vllm:generation_tokens_total",
                        "vllm:prefix_cache_hits_total",
                        "vllm:request_prefill_time_seconds_sum",
                        "vllm:time_to_first_token_seconds_sum",
                        "vllm:time_to_first_token_seconds_count",
                        "vllm:request_prefill_time_seconds_count",
                        "vllm:request_decode_time_seconds_sum",
                    )
                }
                if (
                    deltas["vllm:request_success_total"] != 1
                    or deltas["vllm:prefix_cache_hits_total"] != 0
                ):
                    raise RuntimeError("Contaminated request/cache metrics")
                if any(
                    deltas[k] != 1
                    for k in (
                        "vllm:time_to_first_token_seconds_count",
                        "vllm:request_prefill_time_seconds_count",
                    )
                ):
                    raise RuntimeError("Latency metric window is incomplete")
                row = timing(result, mode, state["ports"]["jaeger_ui"], blocks, queue_depth)
                if (
                    mode != "off"
                    and abs(
                        row["prefill_ms"] - deltas["vllm:request_prefill_time_seconds_sum"] * 1000
                    )
                    > 0.01
                ):
                    raise RuntimeError("Trace/native prefill boundaries disagree")
                row.update({"cycle": cycle, "metrics": deltas})
                rows.append(row)
                write_json(artifact / "rows.json", rows)
            print(f"Completed {cycle + 1}/{rounds} matched rounds", flush=True)
        if len({r["prompt_hash"] for r in rows}) != 1 or len({r["output_hash"] for r in rows}) != 1:
            raise RuntimeError("Input/output token IDs differ within the matched controls")
        if (
            json.loads((LOCAL / "run" / "vllm-process.json").read_text())["run_id"]
            != process["run_id"]
        ):
            raise RuntimeError("Model process changed during the experiment")
    except BaseException as error:
        write_json(
            artifact / "failure.json",
            {
                "status": "failed",
                "error": str(error),
                "captured_requests": len(rows),
                "automatic_generation_retry": False,
            },
        )
        raise
    finally:
        stop.set()
        sampler.join(timeout=10)
    if sampler.is_alive() or errors:
        raise RuntimeError("Host sampler failed")
    validate_host_samples(artifact)
    summary = {}
    for mode in modes:
        keys = ["ttft_ms", "e2e_ms"]
        if mode != "off":
            keys.append("batch_roots")
        summary[mode] = {
            key: statistics.median(r[key] for r in rows if r["mode"] == mode) for key in keys
        }
    write_json(
        artifact / "acceptance.json",
        {
            "status": "pass",
            "requests": len(rows),
            "same_input_output_ids": True,
            "same_process_and_kv": True,
            "summary": summary,
        },
    )
    print(json.dumps({"artifact_dir": str(artifact), "summary": summary}, indent=2))
