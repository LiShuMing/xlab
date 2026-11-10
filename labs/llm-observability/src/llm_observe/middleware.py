"""Opt-in ASGI tracing through final body send, errors and cancellation."""

import asyncio
import time
from uuid import uuid4

from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind, Status, StatusCode, TraceState

from llm_observe.stream import SSE, event_flags


class TracingMiddleware:
    def __init__(self, app, tracer=None) -> None:
        self.app = app
        self.tracer = tracer or trace.get_tracer("llm_observe.asgi")

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["path"] not in {
            "/v1/chat/completions",
            "/v1/completions",
        }:
            await self.app(scope, receive, send)
            return
        carrier = {
            k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
        }
        request_id = carrier.get("x-request-id", uuid4().hex)
        started = time.perf_counter_ns()
        span = self.tracer.start_span(
            "http.server",
            context=propagate.extract(carrier),
            kind=SpanKind.SERVER,
            attributes={
                "http.request.method": scope["method"],
                "url.path": scope["path"],
                "llm.request_id": request_id,
            },
        )
        parser = SSE()
        seen = set()
        finished = False
        streaming = False

        def event(name: str, **attributes) -> None:
            span.add_event(name, {"monotonic_ns": time.perf_counter_ns(), **attributes})

        async def observed_receive():
            message = await receive()
            if message["type"] == "http.disconnect":
                event("client.disconnect", response_complete=finished)
                if not finished:
                    span.set_status(Status(StatusCode.ERROR, "client disconnected"))
            return message

        async def observed_send(message):
            nonlocal finished, streaming
            await send(message)
            if message["type"] == "http.response.start":
                status = message["status"]
                span.set_attribute("http.response.status_code", status)
                streaming = any(
                    key.lower() == b"content-type" and b"text/event-stream" in value
                    for key, value in message.get("headers", [])
                )
                if status >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {status}"))
                event("http.headers_sent")
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body and "sse.first_send" not in seen:
                    seen.add("sse.first_send")
                    event("sse.first_send")
                if streaming:
                    try:
                        flags = [event_flags(data) for data in parser.feed(body)]
                    except (ValueError, UnicodeError):
                        # Observability cannot break a response whose bytes were already sent.
                        event("observability.sse_parse_error")
                        span.set_attribute("llm.observability_complete", False)
                        parser.buffer = b""
                        parser.data.clear()
                        streaming = False
                        flags = []
                    for item in flags:
                        for name, present in (
                            ("sse.first_token_sent", bool(item.get("token_ids"))),
                            ("sse.first_visible_sent", item.get("visible")),
                            ("sse.done_sent", item["done"]),
                        ):
                            if present and name not in seen:
                                seen.add(name)
                                event(name)
                        if item.get("error"):
                            span.set_status(Status(StatusCode.ERROR, "SSE error"))
                        if item.get("finish_reason"):
                            span.set_attribute("llm.finish_reason", item["finish_reason"])
                        if item.get("usage"):
                            for key, value in item["usage"].items():
                                if isinstance(value, int):
                                    span.set_attribute("llm.usage." + key, value)
                if not message.get("more_body", False):
                    finished = True
                    event("http.final_body_sent")
                    if streaming and "sse.done_sent" not in seen:
                        span.set_status(Status(StatusCode.ERROR, "SSE ended without DONE"))

        try:
            with trace.use_span(span, end_on_exit=False, record_exception=False):
                # Forward the server span context, so vLLM's llm_request becomes its child.
                forwarded = {"x-request-id": request_id}
                propagate.inject(forwarded)
                state = TraceState.from_header([forwarded.get("tracestate", "")])
                if state.get("llmobs") is None:
                    forwarded["tracestate"] = state.add("llmobs", "compact").to_header()
                child_scope = dict(scope)
                child_scope["headers"] = [
                    (k, v)
                    for k, v in scope.get("headers", [])
                    if k.decode().lower() not in forwarded
                ] + [(k.encode(), v.encode()) for k, v in forwarded.items()]
                await self.app(child_scope, observed_receive, observed_send)
        except asyncio.CancelledError:
            event("request.cancelled")
            span.set_status(Status(StatusCode.ERROR, "request cancelled"))
            raise
        except Exception as error:
            # Record only the type: exception messages can contain request text.
            event("request.error", error_type=type(error).__name__)
            span.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise
        finally:
            span.set_attribute("llm.response_body_complete", finished)
            span.set_attribute("llm.host_duration_ns", time.perf_counter_ns() - started)
            span.end()
