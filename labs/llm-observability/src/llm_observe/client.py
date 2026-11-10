"""Explicit, single-attempt streaming probe with private raw artifacts."""

import json
import time
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from opentelemetry import propagate
from opentelemetry.trace import SpanKind, Status, StatusCode

from llm_observe.manager import STATE
from llm_observe.paths import LOCAL, write_json
from llm_observe.smoke import query_trace
from llm_observe.stream import SSE, event_flags
from llm_observe.telemetry import provider


def probe(
    model: str,
    prompt: str,
    max_tokens: int,
    require_server_traces: bool = False,
    minimal_trace: bool = False,
    quiet: bool = False,
    barrier=None,
    trace_mode: str = "full",
) -> dict:
    if max_tokens < 1:
        raise ValueError("max-tokens must be positive")
    if trace_mode not in {"full", "compact", "off"}:
        raise ValueError("Unknown trace mode")
    if minimal_trace:
        trace_mode = "off"
    state = json.loads(STATE.read_text())
    ports = state["ports"]
    request_id = uuid4().hex
    artifact = LOCAL / "artifacts" / f"request-{request_id}"
    artifact.mkdir()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "return_token_ids": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    write_json(artifact / "request.json", payload)
    telemetry = provider("llm-observe-client", f"http://127.0.0.1:{ports['otlp_http']}")
    tracer = telemetry.get_tracer("llm_observe.client")
    summary = {
        "request_id": request_id,
        "generation_attempts": 0,
        "done": False,
        "usage": None,
        "finish_reason": None,
        "output_token_ids": [],
        "trace_mode": trace_mode,
    }
    parser = SSE()
    opener = build_opener(ProxyHandler({}))
    try:
        with tracer.start_as_current_span("client.request", kind=SpanKind.CLIENT) as span:
            summary["trace_id"] = f"{span.get_span_context().trace_id:032x}"
            span.set_attribute("llm.request_id", request_id)
            headers = {"Content-Type": "application/json", "X-Request-Id": request_id}
            propagate.inject(headers)
            headers["tracestate"] = "llmobs=" + trace_mode
            request = Request(
                state["model_url"] + "/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers=headers,
            )
            if barrier is not None:
                barrier.wait(timeout=15)
            started = time.perf_counter_ns()
            summary["started_ns"] = started
            summary["generation_attempts"] = 1
            with (
                opener.open(request, timeout=120) as response,
                (artifact / "response.sse").open("wb") as raw,
                (artifact / "events.jsonl").open("w") as events,
            ):
                span.add_event("client.headers", {"monotonic_ns": time.perf_counter_ns()})
                if "text/event-stream" not in response.headers.get("Content-Type", ""):
                    raise ValueError("Expected an SSE response")
                while line := response.readline():
                    raw.write(line)
                    for data in parser.feed(line):
                        stamp = time.perf_counter_ns()
                        flags = event_flags(data)
                        events.write(json.dumps({"monotonic_ns": stamp, "data": data}) + "\n")
                        for field, present in (
                            ("first_token_ns", bool(flags.get("token_ids"))),
                            ("first_visible_ns", flags.get("visible")),
                        ):
                            if present and field not in summary:
                                summary[field] = stamp
                                span.add_event("client." + field, {"monotonic_ns": stamp})
                        summary["output_token_ids"].extend(flags.get("token_ids", []))
                        if flags.get("finish_reason"):
                            summary["finish_reason"] = flags["finish_reason"]
                        if flags.get("usage"):
                            summary["usage"] = flags["usage"]
                        if flags.get("error"):
                            raise ValueError("Service returned an SSE error; raw stream retained")
                        if flags["done"]:
                            summary.update({"done": True, "done_ns": stamp})
                            span.add_event("client.done", {"monotonic_ns": stamp})
                    if summary["done"]:
                        break
            usage = summary["usage"] or {}
            summary["checks"] = {
                "done": summary["done"],
                "usage_and_ids": usage.get("completion_tokens") == len(summary["output_token_ids"]),
                "natural_stop": summary["finish_reason"] == "stop",
                "framing": not parser.buffer and not parser.data,
            }
            if not all(summary["checks"].values()):
                span.set_status(Status(StatusCode.ERROR, "Probe validation failed"))
                raise ValueError("Probe validation failed; no generation retry")
    finally:
        summary["read_end_ns"] = time.perf_counter_ns()
        write_json(artifact / "summary.json", summary)
        telemetry.force_flush(timeout_millis=5000)
        telemetry.shutdown()
    required = {"client.request", "http.server", "llm_request"} if require_server_traces else None
    trace = query_trace(ports["jaeger_ui"], summary["trace_id"], required_names=required)
    write_json(artifact / "trace.json", trace)
    names = {s["operationName"] for s in trace["data"][0]["spans"]}
    if require_server_traces:
        by_name = {s["operationName"]: s for s in trace["data"][0]["spans"]}
        for child, parent in (("http.server", "client.request"), ("llm_request", "http.server")):
            if not any(
                ref["refType"] == "CHILD_OF" and ref["spanID"] == by_name[parent]["spanID"]
                for ref in by_name[child]["references"]
            ):
                raise RuntimeError("Client/API/llm_request parent relationship is incomplete")
    result = {
        "artifact_dir": str(artifact),
        "trace_id": summary["trace_id"],
        "checks": summary["checks"],
        "usage": summary["usage"],
        "api_trace_present": "http.server" in names,
        "llm_request_present": "llm_request" in names,
    }
    if not quiet:
        print(json.dumps(result, indent=2))
    return result
