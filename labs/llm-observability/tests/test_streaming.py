import asyncio
import json

import pytest
from opentelemetry import propagate, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from llm_observe.middleware import TracingMiddleware
from llm_observe.stream import SSE


@pytest.fixture
def tracing():
    output = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(output))
    yield provider.get_tracer("test"), output
    provider.shutdown()


def test_sse_preserves_utf8_across_network_chunks():
    parser = SSE()
    payload = 'data: {"text":"中文"}\r\n\r\ndata: [DONE]\n\n'.encode()
    events = []
    for byte in payload:
        events.extend(parser.feed(bytes([byte])))
    assert events == ['{"text":"中文"}', "[DONE]"]
    assert not parser.buffer and not parser.data


@pytest.mark.parametrize("mode", [None, "off", "full", "compact"])
def test_stream_span_waits_for_final_body_and_forwards_server_parent(tracing, mode):
    tracer, output = tracing
    forwarded = {}

    async def app(scope, _receive, send):
        forwarded.update({k.decode(): v.decode() for k, v in scope["headers"]})
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        assert not output.get_finished_spans()
        await send({"type": "http.response.body", "body": b"data: [DONE]\n\n", "more_body": True})
        assert not output.get_finished_spans()
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def send(_message):
        pass

    async def receive():
        return {"type": "http.request"}

    parent = {"traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01"}
    if mode is not None:
        parent["tracestate"] = "vendor=retained,llmobs=" + mode
    with tracer.start_as_current_span("client", context=propagate.extract(parent)) as client:
        headers = {}
        propagate.inject(headers)
        scope = {
            "type": "http",
            "path": "/v1/chat/completions",
            "method": "POST",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        }
        asyncio.run(TracingMiddleware(app, tracer)(scope, receive, send))
        server = output.get_finished_spans()[0]
        assert server.parent.span_id == client.get_span_context().span_id
        downstream = trace.get_current_span(propagate.extract(forwarded)).get_span_context()
        assert downstream.span_id == server.context.span_id
        assert downstream.trace_state.get("llmobs") == (mode or "compact")
        if mode is not None:
            assert downstream.trace_state.get("vendor") == "retained"
    assert server.attributes["llm.response_body_complete"] is True
    assert {e.name for e in server.events} >= {"sse.done_sent", "http.final_body_sent"}


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_error_and_cancellation_end_span_without_exception_text(tracing, failure):
    tracer, output = tracing

    async def app(*_args):
        raise failure("private request text")

    async def noop(*_args):
        pass

    scope = {"type": "http", "path": "/v1/chat/completions", "method": "POST", "headers": []}
    with pytest.raises(failure):
        asyncio.run(TracingMiddleware(app, tracer)(scope, noop, noop))
    span = output.get_finished_spans()[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["llm.response_body_complete"] is False
    assert "private request text" not in span.to_json()


def test_concurrent_requests_do_not_share_context(tracing):
    tracer, output = tracing

    async def app(scope, _receive, send):
        await asyncio.sleep(0)
        context = propagate.extract({k.decode(): v.decode() for k, v in scope["headers"]})
        with tracer.start_as_current_span("engine", context=context):
            await asyncio.sleep(0)
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def noop(*_args):
        pass

    async def request(name):
        with tracer.start_as_current_span(name):
            headers = {}
            propagate.inject(headers)
            scope = {
                "type": "http",
                "path": "/v1/completions",
                "method": "POST",
                "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
            }
            await TracingMiddleware(app, tracer)(scope, noop, noop)

    async def run():
        await asyncio.gather(request("one"), request("two"))

    asyncio.run(run())
    spans = output.get_finished_spans()
    roots = [s for s in spans if s.name in {"one", "two"}]
    assert len({s.context.trace_id for s in roots}) == 2
    for root in roots:
        group = [s for s in spans if s.context.trace_id == root.context.trace_id]
        assert {s.name for s in group} == {root.name, "http.server", "engine"}


def test_stream_missing_done_is_error(tracing):
    tracer, output = tracing

    async def app(_scope, _receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        payload = {"choices": [{"delta": {"content": "hi"}, "token_ids": [1]}]}
        await send(
            {"type": "http.response.body", "body": f"data: {json.dumps(payload)}\n\n".encode()}
        )

    async def noop(*_args):
        pass

    scope = {"type": "http", "path": "/v1/completions", "method": "POST", "headers": []}
    asyncio.run(TracingMiddleware(app, tracer)(scope, noop, noop))
    span = output.get_finished_spans()[0]
    assert span.status.status_code == StatusCode.ERROR
    assert "sse.first_token_sent" in {e.name for e in span.events}


@pytest.mark.parametrize("complete", [False, True])
def test_disconnect_is_error_only_before_response_completion(tracing, complete):
    tracer, output = tracing

    async def app(_scope, receive, send):
        if complete:
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        await receive()

    async def receive():
        return {"type": "http.disconnect"}

    async def send(_message):
        pass

    scope = {"type": "http", "path": "/v1/chat/completions", "method": "POST", "headers": []}
    asyncio.run(TracingMiddleware(app, tracer)(scope, receive, send))
    span = output.get_finished_spans()[0]
    assert (span.status.status_code == StatusCode.ERROR) is not complete
    assert span.attributes["llm.response_body_complete"] is complete
