import asyncio
import random
import time
from types import SimpleNamespace as Obj

import pytest
from opentelemetry import propagate, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_observe import instrumentation as bridge
from llm_observe.telemetry import IndependentTracerProvider


@pytest.fixture
def runtime(monkeypatch):
    output = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(output))
    runtime = bridge.Runtime(provider.get_tracer("test.bridge"))
    monkeypatch.setattr(bridge, "runtime", runtime)
    yield runtime, output, provider.get_tracer("test.request")
    provider.shutdown()


def request(tracer, key):
    span = tracer.start_span(key, context=propagate.extract({}))
    headers = {}
    propagate.inject(headers, context=trace.set_span_in_context(span))
    queued = Obj(type=Obj(name="QUEUED"), timestamp=time.monotonic())
    scheduled = Obj(type=Obj(name="SCHEDULED"), timestamp=time.monotonic())
    return Obj(
        request_id=key,
        trace_headers=headers,
        prompt_token_ids=[1, 2, 3],
        events=[queued, scheduled],
        num_computed_tokens=0,
    ), span


@pytest.mark.parametrize("compact", [False, True])
def test_shared_batch_links_requests_without_duplicating_execution(runtime, compact):
    runtime, output, tracer = runtime
    first, a = request(tracer, "one")
    second, b = request(tracer, "two")
    if compact:
        first.trace_headers["tracestate"] = "llmobs=compact"
        second.trace_headers["tracestate"] = "llmobs=compact"
    runtime.ensure_request(first)
    runtime.ensure_request(second)
    scheduled = Obj(num_scheduled_tokens={"one": 3, "two": 3}, total_num_scheduled_tokens=6)
    scheduler = Obj(requests={"one": first, "two": second})
    started = time.monotonic_ns()
    batch = runtime.scheduled(scheduler, scheduled, started, started + 100)
    with runtime.phase("runner.execute.host", batch=batch):
        pass
    original_headers = dict(first.trace_headers)
    result = Obj(
        request_id="one",
        trace_headers=first.trace_headers,
        new_token_ids=[9],
        prefill_stats=None,
        finish_reason="stop",
    )
    other = Obj(
        request_id="two",
        trace_headers=second.trace_headers,
        new_token_ids=[8],
        prefill_stats=None,
        finish_reason="stop",
    )
    runtime.finish_batch(batch, {0: Obj(outputs=[result, other], timestamp=time.monotonic())})
    a.end()
    b.end()
    spans = output.get_finished_spans()
    batches = [span for span in spans if span.name == "batch.execution"]
    assert len(batches) == 1 and len(batches[0].links) == 2
    assert len({link.context.trace_id for link in batches[0].links}) == 2
    assert result.new_token_ids == [9] and other.new_token_ids == [8]
    assert first.trace_headers == original_headers
    assert "x-llm-observe-batch-trace" in result.trace_headers
    assert not runtime.requests and not runtime.batches


def test_deferred_resolve_uses_pending_batch_not_current_batch(runtime):
    runtime, output, tracer = runtime
    req, root = request(tracer, "one")
    runtime.ensure_request(req)
    scheduler = Obj(requests={"one": req})
    first = Obj(num_scheduled_tokens={"one": 1}, total_num_scheduled_tokens=1)
    second = Obj(num_scheduled_tokens={"one": 1}, total_num_scheduled_tokens=1)
    before = runtime.scheduled(scheduler, first, time.monotonic_ns(), time.monotonic_ns())
    after = runtime.scheduled(scheduler, second, time.monotonic_ns(), time.monotonic_ns())
    pipeline = Obj(_pending=Obj(scheduler_output=first))
    observed = []

    def original(self):
        observed.append(bridge._batch.get().index)
        return "tokens unchanged"

    wrapped = bridge.runner_phase(
        "mlx.deferred.resolve.host", lambda self, _: self._pending.scheduler_output
    )(original)
    token = bridge._batch.set(after)
    try:
        assert wrapped(pipeline) == "tokens unchanged"
        assert bridge._batch.get() is after
    finally:
        bridge._batch.reset(token)
    assert observed == [before.index]
    resolved = [s for s in output.get_finished_spans() if s.name == "mlx.deferred.resolve.host"][0]
    assert resolved.parent.span_id == before.span.get_span_context().span_id
    before.span.end()
    after.span.end()
    runtime.requests["one"].span.end()
    root.end()


def test_minimal_trace_does_not_register_core_requests(runtime):
    runtime, output, tracer = runtime
    req, root = request(tracer, "minimal")
    req.trace_headers["tracestate"] = "llmobs=off"
    assert runtime.ensure_request(req) is None
    assert not runtime.requests
    root.end()
    assert not any(span.name == "core.request" for span in output.get_finished_spans())


def test_compact_buffers_first_output_phases_and_stops_tracing_decode(runtime):
    runtime, exported, tracer = runtime
    req, root = request(tracer, "compact")
    req.trace_headers["tracestate"] = "llmobs=compact"
    runtime.ensure_request(req)
    scheduled = Obj(num_scheduled_tokens={"compact": 3}, total_num_scheduled_tokens=3)
    batch = runtime.scheduled(
        Obj(requests={"compact": req}), scheduled, time.monotonic_ns(), time.monotonic_ns()
    )
    with runtime.phase("mlx.async_eval.call.host", batch=batch):
        sum(range(100))
    first = Obj(
        request_id="compact",
        trace_headers=req.trace_headers,
        new_token_ids=[9],
        prefill_stats=None,
        finish_reason=None,
    )
    runtime.finish_batch(batch, {0: Obj(outputs=[first], timestamp=time.monotonic())})
    assert not any(span.name == "batch.execution" for span in exported.get_finished_spans())
    assert bridge.observe_output(first.trace_headers)
    assert not bridge.observe_output(req.trace_headers)
    assert (
        runtime.scheduled(
            Obj(requests={"compact": req}), scheduled, time.monotonic_ns(), time.monotonic_ns()
        )
        is None
    )
    final = Obj(
        request_id="compact",
        trace_headers=req.trace_headers,
        new_token_ids=[10],
        prefill_stats=None,
        finish_reason="stop",
    )
    runtime.finish_batch(None, {0: Obj(outputs=[final], timestamp=time.monotonic())})
    assert not runtime.requests and not runtime.batches
    spans = exported.get_finished_spans()
    recorded = next(span for span in spans if span.name == "batch.execution")
    event = next(e for e in recorded.events if e.name == "mlx.async_eval.call.host")
    assert event.attributes["host.duration_ns"] > 0
    assert event.attributes["host.thread_cpu_ns"] > 0
    assert "process.major_faults_delta" in event.attributes
    assert not any(span.name == "mlx.async_eval.call.host" for span in spans)
    assert final.new_token_ids == [10]
    root.end()


def test_clock_rebase_only_between_active_requests(runtime, monkeypatch):
    runtime, _, tracer = runtime
    before = runtime.offset_ns
    monkeypatch.setattr(bridge.time, "time_ns", lambda: bridge.time.monotonic_ns() + before + 10**9)
    runtime.refresh_clock()
    assert runtime.offset_ns > before + 999_000_000
    req, root = request(tracer, "clock")
    runtime.ensure_request(req)
    held = runtime.offset_ns
    monkeypatch.setattr(
        bridge.time, "time_ns", lambda: bridge.time.monotonic_ns() + before + 2 * 10**9
    )
    runtime.refresh_clock()
    assert runtime.offset_ns == held
    runtime.requests["clock"].span.end()
    root.end()


def test_trace_ids_do_not_repeat_after_model_seed_or_consume_model_rng():
    original_state = random.getstate()
    provider = IndependentTracerProvider()
    try:
        tracer = provider.get_tracer("seed-regression")
        contexts = []
        for _ in range(2):
            random.seed(0)
            before = random.getstate()
            with tracer.start_as_current_span("batch", context=propagate.extract({})) as span:
                contexts.append(span.get_span_context())
            assert random.getstate() == before
        assert contexts[0].trace_id != contexts[1].trace_id
        assert contexts[0].span_id != contexts[1].span_id
    finally:
        provider.shutdown()
        random.setstate(original_state)


@pytest.mark.parametrize("fail", [False, True])
def test_api_shared_output_batch_closes_on_success_and_error(runtime, fail):
    runtime, exported, tracer = runtime
    first, a = request(tracer, "one")
    second, b = request(tracer, "two")
    outputs = [first, second]

    class Client:
        async def get_output_async(self):
            return Obj(outputs=outputs, timestamp=time.monotonic())

        async def add_request_async(self):
            pass

    class Processor:
        def process_outputs(self, values):
            if fail:
                raise ValueError("output processing failed")
            return [value.request_id for value in values]

    bridge.patch_module("vllm.v1.engine.core_client", Obj(AsyncMPClient=Client))
    bridge.patch_module("vllm.v1.engine.output_processor", Obj(OutputProcessor=Processor))
    result = asyncio.run(Client().get_output_async())
    assert result.outputs is outputs
    assert len(runtime.api_batches) == 1
    if fail:
        with pytest.raises(ValueError, match="output processing failed"):
            Processor().process_outputs(outputs)
    else:
        assert Processor().process_outputs(outputs[:1]) == ["one"]
        assert len(runtime.api_batches) == 1
        assert Processor().process_outputs(outputs[1:]) == ["two"]
    assert not runtime.api_batches
    spans = exported.get_finished_spans()
    batch = next(span for span in spans if span.name == "api.output.batch")
    assert len(batch.links) == 2
    assert batch.status.is_ok is not fail
    assert len([span for span in spans if span.name == "api.output.received"]) == 2
    a.end()
    b.end()
