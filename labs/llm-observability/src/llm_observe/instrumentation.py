"""Opt-in vLLM 0.33 / Metal uniproc host tracing, without extra GPU synchronization."""

import functools
import hashlib
import importlib
import inspect
import json
import os
import resource
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import PathFinder
from pathlib import Path
from uuid import uuid4

from opentelemetry import propagate, trace
from opentelemetry.context import Context
from opentelemetry.trace import Link, Status, StatusCode

from llm_observe.paths import LOCAL, write_json
from llm_observe.telemetry import IndependentTracerProvider

TARGETS = {
    "vllm.tracing.otel": ["init_otel_tracer", "init_otel_worker_tracer"],
    "vllm.entrypoints.openai.chat_completion.serving": ["OpenAIServingChat.render_chat_request"],
    "vllm.v1.engine.async_llm": ["AsyncLLM.add_request"],
    "vllm.v1.engine.core_client": [
        "AsyncMPClient.add_request_async",
        "AsyncMPClient.get_output_async",
    ],
    "vllm.v1.engine.core": ["EngineCore.preprocess_add_request", "EngineCore.__init__"],
    "vllm.v1.core.sched.scheduler": [
        "Scheduler.add_request",
        "Scheduler.schedule",
        "Scheduler.update_from_output",
        "Scheduler._free_request",
        "Scheduler._free_request_blocks",
    ],
    "vllm.v1.engine.output_processor": ["OutputProcessor.process_outputs"],
    "vllm_metal.v1.model_runner": [
        "MetalModelRunner.execute_model",
        "MetalModelRunner.sample_tokens",
        "MetalModelRunner._start_paged_forward",
        "MetalModelRunner._target_forward",
        "MetalModelRunner._submit_paged_forward_outputs",
        "MetalModelRunner._sample_paged_batch",
        "MetalModelRunner._evaluate_pipeline_gate",
    ],
    "vllm_metal.v1.decode_pipeline": ["DecodePipeline.submit", "DecodePipeline._resolve_pending"],
    "vllm_metal.v1.sampling_batch": ["sample_from_logits"],
}
MANIFEST = LOCAL / "run" / "instrumentation-source.json"
_batch = ContextVar("llm_observe_batch", default=None)
_operation = ContextVar("llm_observe_operation", default=None)
_updating = ContextVar("llm_observe_updating", default=False)
_installed = False


def sampled(context) -> bool:
    value = trace.get_current_span(context).get_span_context()
    return value.is_valid and value.trace_flags.sampled and value.trace_state.get("llmobs") != "off"


def context(headers):
    if not headers or "traceparent" not in headers:
        return None
    result = propagate.extract(headers or {})
    return result if sampled(result) else None


@dataclass
class RequestTrace:
    span: object
    first_scheduled: bool = False
    first_output: bool = False
    compact: bool = False
    completed: list = field(default_factory=list)


@dataclass
class BatchTrace:
    output: object
    span: object
    request_ids: tuple[str, ...]
    index: int
    remaining: set[str] | None = None
    compact: bool = False
    phases: list = field(default_factory=list)
    ended_ns: int | None = None
    emitted: bool = False


class Runtime:
    def __init__(self, tracer=None) -> None:
        self.tracer = tracer or trace.get_tracer("llm_observe.bridge")
        self.requests: dict[str, RequestTrace] = {}
        self.batches: dict[int, BatchTrace] = {}
        self.api_batches: dict[str, BatchTrace] = {}
        self.sequence = 0
        self.config = {}
        self.instance_id = uuid4().hex
        self.offset_ns = time.time_ns() - time.monotonic_ns()

    def attributes(self, **extra) -> dict:
        return {
            "llm.run_id": os.environ.get("LLM_OBSERVE_RUN_ID", "foreground"),
            "llm.process_instance_id": self.instance_id,
            "process.pid": os.getpid(),
            "clock.epoch_minus_monotonic_ns": self.offset_ns,
            "llm.instrumentation": "vllm033-metal-uniproc",
            **self.config,
            **extra,
        }

    def refresh_clock(self) -> None:
        # macOS monotonic excludes system sleep; rebase only between active records.
        if not self.requests and not self.batches and not self.api_batches:
            self.offset_ns = time.time_ns() - time.monotonic_ns()

    def ensure_request(self, request) -> RequestTrace | None:
        key = request.request_id
        if key in self.requests:
            return self.requests[key]
        self.refresh_clock()
        parent = context(request.trace_headers)
        if parent is None:
            return None
        if len(self.requests) >= 2048:
            raise RuntimeError("Diagnostic request registry capacity exceeded")
        span = self.tracer.start_span(
            "core.request",
            context=parent,
            attributes=self.attributes(
                **{"llm.request_id": key, "llm.prompt_tokens": len(request.prompt_token_ids or [])}
            ),
        )
        record = RequestTrace(
            span,
            compact=(
                trace.get_current_span(parent).get_span_context().trace_state.get("llmobs")
                == "compact"
            ),
        )
        span.set_attribute("llm.trace_mode", "compact" if record.compact else "full")
        self.requests[key] = record
        self.event(span, "core.input.received")
        return record

    def event(self, span, name: str, stamp_ns: int | None = None, **attributes) -> None:
        stamp = time.monotonic_ns() if stamp_ns is None else stamp_ns
        span.add_event(
            name, {"monotonic_ns": stamp, **attributes}, timestamp=self.offset_ns + stamp
        )

    @contextmanager
    def phase(self, name: str, batch=None, parent=None, **attributes):
        record = batch if batch is not None else _batch.get()
        if record is not None:
            parent = trace.set_span_in_context(record.span)
            attributes.update({"llm.batch_id": record.index})
        if parent is None:
            yield None
            return
        started = time.monotonic_ns()
        offset = self.offset_ns if record is not None else time.time_ns() - started
        if record is not None and record.compact:
            cpu_started = time.thread_time_ns()
            usage = (
                resource.getrusage(resource.RUSAGE_SELF)
                if name == "mlx.async_eval.call.host"
                else None
            )
            try:
                yield record.span
            except BaseException as error:
                record.span.set_status(Status(StatusCode.ERROR, type(error).__name__))
                raise
            finally:
                ended = time.monotonic_ns()
                values = {
                    **attributes,
                    "host.start_monotonic_ns": started,
                    "host.end_monotonic_ns": ended,
                    "host.duration_ns": ended - started,
                    "host.thread_cpu_ns": time.thread_time_ns() - cpu_started,
                }
                if usage is not None:
                    after = resource.getrusage(resource.RUSAGE_SELF)
                    values.update(
                        {
                            "process.minor_faults_delta": after.ru_minflt - usage.ru_minflt,
                            "process.major_faults_delta": after.ru_majflt - usage.ru_majflt,
                            "process.voluntary_switches_delta": after.ru_nvcsw - usage.ru_nvcsw,
                            "process.involuntary_switches_delta": after.ru_nivcsw - usage.ru_nivcsw,
                        }
                    )
                record.phases.append((name, started, values))
            return
        span = self.tracer.start_span(
            name,
            context=parent,
            start_time=offset + started,
            attributes=self.attributes(**{"clock.epoch_minus_monotonic_ns": offset, **attributes}),
        )
        span.set_attribute("host.start_monotonic_ns", started)
        try:
            with trace.use_span(span, end_on_exit=False, record_exception=False):
                yield span
        except BaseException as error:
            span.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise
        finally:
            ended = time.monotonic_ns()
            span.set_attribute("host.end_monotonic_ns", ended)
            span.end(end_time=offset + ended)

    def scheduled(self, scheduler, output, started: int, ended: int) -> BatchTrace | None:
        request_ids = tuple(
            key
            for key in output.num_scheduled_tokens
            if key in self.requests
            and (not self.requests[key].compact or not self.requests[key].first_output)
        )
        if not request_ids:
            return None
        if len(self.batches) >= 128:
            raise RuntimeError("Diagnostic batch registry capacity exceeded")
        self.sequence += 1
        links = [Link(self.requests[key].span.get_span_context()) for key in request_ids]
        span = self.tracer.start_span(
            "batch.execution",
            context=Context(),
            links=links,
            start_time=self.offset_ns + started,
            attributes=self.attributes(
                **{
                    "llm.batch_id": self.sequence,
                    "llm.request_ids": request_ids,
                    "llm.scheduled_tokens": output.total_num_scheduled_tokens,
                    "llm.request_count": len(output.num_scheduled_tokens),
                    "llm.sampled_request_count": len(request_ids),
                }
            ),
        )
        record = BatchTrace(output, span, request_ids, self.sequence)
        record.compact = all(self.requests[key].compact for key in request_ids)
        span.set_attribute("llm.trace_mode", "compact" if record.compact else "full")
        self.batches[id(output)] = record
        if record.compact:
            record.phases.append(
                (
                    "scheduler.schedule",
                    started,
                    {
                        "host.start_monotonic_ns": started,
                        "host.end_monotonic_ns": ended,
                        "host.duration_ns": ended - started,
                    },
                )
            )
        else:
            self.schedule_span(record, started, ended)
        for key in request_ids:
            request = self.requests[key]
            batch_context = span.get_span_context()
            self.event(
                request.span,
                "batch.scheduled",
                **{
                    "llm.batch_trace_id": f"{batch_context.trace_id:032x}",
                    "llm.batch_id": self.sequence,
                },
            )
            if not request.first_scheduled:
                request.first_scheduled = True
                source = scheduler.requests[key]
                events = [event for event in source.events if event.type.name == "SCHEDULED"]
                if not events:
                    raise RuntimeError("Full instrumentation requires scheduler log_stats events")
                self.event(
                    request.span, "request.first_scheduled", stamp_ns=int(events[0].timestamp * 1e9)
                )
                span.set_attribute("llm.after_schedule_computed_tokens", source.num_computed_tokens)
        return record

    def schedule_span(self, record, started, ended):
        scheduling = self.tracer.start_span(
            "scheduler.schedule",
            context=trace.set_span_in_context(record.span),
            start_time=self.offset_ns + started,
            attributes=self.attributes(
                **{
                    "host.start_monotonic_ns": started,
                    "host.end_monotonic_ns": ended,
                    "llm.batch_id": record.index,
                }
            ),
        )
        scheduling.end(end_time=self.offset_ns + ended)

    def emit_batch(self, record: BatchTrace) -> None:
        if record.emitted:
            return
        for name, started, values in record.phases:
            self.event(record.span, name, stamp_ns=started, **values)
        record.span.end(end_time=self.offset_ns + record.ended_ns)
        record.emitted = True

    def finish_batch(self, record: BatchTrace | None, outputs) -> None:
        if record is not None and record.compact:
            for key in record.request_ids:
                if key in self.requests:
                    self.requests[key].completed.append(record)
        finished = []
        for group in outputs.values():
            for output in group.outputs:
                request = self.requests.get(output.request_id)
                if request is None:
                    continue
                if output.new_token_ids and not request.first_output:
                    request.first_output = True
                    self.event(
                        request.span, "core.first_output.ready", stamp_ns=int(group.timestamp * 1e9)
                    )
                    if output.prefill_stats is not None:
                        request.span.set_attribute(
                            "llm.prompt_cached_tokens", output.prefill_stats.num_cached_tokens
                        )
                        request.span.set_attribute(
                            "llm.prompt_local_computed_tokens",
                            output.prefill_stats.num_computed_tokens,
                        )
                if record is not None:
                    # Copy diagnostic headers; keep the request's carrier unchanged.
                    output.trace_headers = dict(output.trace_headers or {})
                    span_context = record.span.get_span_context()
                    output.trace_headers["x-llm-observe-batch-trace"] = (
                        f"{span_context.trace_id:032x}"
                    )
                    output.trace_headers["x-llm-observe-batch-span"] = (
                        f"{span_context.span_id:016x}"
                    )
                if output.finish_reason is not None:
                    self.event(request.span, "core.last_output.ready")
                    request.span.set_attribute("llm.finish_reason", str(output.finish_reason))
                    finished.append(request)
                    self.requests.pop(output.request_id)
        if record is not None:
            self.event(record.span, "core.output.ready")
            record.ended_ns = time.monotonic_ns()
            if not record.compact:
                self.emit_batch(record)
            self.batches.pop(id(record.output))
        for request in finished:
            for batch in request.completed:
                self.emit_batch(batch)
            request.span.end(end_time=self.offset_ns + time.monotonic_ns())


runtime = Runtime()


def wrap(owner, name: str, factory) -> None:
    original = getattr(owner, name)
    if getattr(original, "_llm_observe_wrapped", False):
        return
    replacement = factory(original)
    replacement._llm_observe_wrapped = True
    setattr(owner, name, functools.wraps(original)(replacement))


def async_phase(name):
    def factory(original):
        async def call(*args, **kwargs):
            runtime.refresh_clock()
            parent = trace.get_current_span()
            ctx = trace.set_span_in_context(parent)
            with runtime.phase(name, parent=ctx if sampled(ctx) else None):
                return await original(*args, **kwargs)

        return call

    return factory


def runner_phase(name, selector=None):
    def factory(original):
        def call(self, *args, **kwargs):
            output = selector(self, args) if selector is not None else None
            record = runtime.batches.get(id(output)) if output is not None else _batch.get()
            if record is None and _batch.get() is None:
                return original(self, *args, **kwargs)
            token = _batch.set(record)
            operation = _operation.set(name)
            try:
                with runtime.phase(name, batch=record) as span:
                    if span is not None and name == "runner.prepare_submit.host":
                        span.set_attribute("llm.prefill_rows", len(args[1]))
                        span.set_attribute("llm.decode_rows", len(args[2]))
                    return original(self, *args, **kwargs)
            finally:
                _operation.reset(operation)
                _batch.reset(token)

        return call

    return factory


def patch_module(name: str, module) -> None:
    if name == "vllm.tracing.otel":
        module.TracerProvider = IndependentTracerProvider
    elif name.endswith("chat_completion.serving"):
        wrap(module.OpenAIServingChat, "render_chat_request", async_phase("api.chat.render"))
    elif name.endswith("engine.async_llm"):
        wrap(module.AsyncLLM, "add_request", async_phase("api.engine.ingress"))
    elif name.endswith("engine.core_client"):
        wrap(module.AsyncMPClient, "add_request_async", async_phase("api.core.enqueue"))

        def receive(original):
            async def call(self, *args, **kwargs):
                result = await original(self, *args, **kwargs)
                selected = [
                    output for output in result.outputs if observe_output(output.trace_headers)
                ]
                if not selected:
                    return result
                runtime.refresh_clock()
                links = [
                    Link(trace.get_current_span(context(out.trace_headers)).get_span_context())
                    for out in selected
                ]
                api_span = runtime.tracer.start_span(
                    "api.output.batch",
                    context=Context(),
                    links=links,
                    attributes=runtime.attributes(**{"llm.request_count": len(result.outputs)}),
                )
                api_trace_id = f"{api_span.get_span_context().trace_id:032x}"
                runtime.api_batches[api_trace_id] = BatchTrace(
                    result,
                    api_span,
                    tuple(out.request_id for out in selected),
                    0,
                    remaining={out.request_id for out in selected},
                )
                for output in selected:
                    parent = context(output.trace_headers)
                    with runtime.phase("api.output.received", parent=parent) as span:
                        if span is not None:
                            span.set_attribute("llm.request_id", output.request_id)
                            span.set_attribute(
                                "core.output_monotonic_ns", int(result.timestamp * 1e9)
                            )
                            span.set_attribute("llm.api_batch_trace_id", api_trace_id)
                            span.set_attribute(
                                "llm.batch_trace_id",
                                output.trace_headers.get("x-llm-observe-batch-trace", ""),
                            )
                            output.trace_headers = dict(output.trace_headers)
                            output.trace_headers["x-llm-observe-api-batch"] = api_trace_id
                return result

            return call

        wrap(module.AsyncMPClient, "get_output_async", receive)
    elif name.endswith("engine.core"):

        def initialize(original):
            def call(self, *args, **kwargs):
                result = original(self, *args, **kwargs)
                if type(self.model_executor).__name__ != "UniProcExecutor":
                    raise RuntimeError("Diagnostic bridge requires the reviewed UniProcExecutor")
                runtime.config = {
                    "llm.queue_depth": self.batch_queue_size,
                    "llm.kv_blocks": self.scheduler.kv_cache_config.num_blocks,
                    "llm.kv_block_size": self.vllm_config.cache_config.block_size,
                    "llm.prefix_caching": self.vllm_config.cache_config.enable_prefix_caching,
                    "llm.async_scheduling": self.vllm_config.scheduler_config.async_scheduling,
                }
                return result

            return call

        wrap(module.EngineCore, "__init__", initialize)

        def preprocess(original):
            def call(self, request, *args, **kwargs):
                record = runtime.ensure_request(request)
                with runtime.phase(
                    "core.input.preprocess",
                    parent=(trace.set_span_in_context(record.span) if record else None),
                ):
                    return original(self, request, *args, **kwargs)

            return call

        wrap(module.EngineCore, "preprocess_add_request", preprocess)
    elif name.endswith("sched.scheduler"):
        patch_scheduler(module.Scheduler)
    elif name.endswith("engine.output_processor"):

        def process(original):
            def call(self, outputs, *args, **kwargs):
                keys = {
                    out.trace_headers.get("x-llm-observe-api-batch")
                    for out in outputs
                    if observe_output(out.trace_headers)
                }
                if not keys:
                    return original(self, outputs, *args, **kwargs)
                if len(keys) != 1 or None in keys:
                    raise RuntimeError("API output batch association is incomplete")
                key = next(iter(keys))
                batch = runtime.api_batches[key]
                try:
                    with runtime.phase(
                        "api.output.process_batch", parent=trace.set_span_in_context(batch.span)
                    ):
                        result = original(self, outputs, *args, **kwargs)
                except BaseException as error:
                    batch.span.set_status(Status(StatusCode.ERROR, type(error).__name__))
                    batch.span.end()
                    runtime.api_batches.pop(key)
                    raise
                batch.remaining.difference_update(out.request_id for out in outputs)
                if not batch.remaining:
                    batch.span.end()
                    runtime.api_batches.pop(key)
                return result

            return call

        wrap(module.OutputProcessor, "process_outputs", process)
    elif name.endswith("model_runner"):
        owner = module.MetalModelRunner

        def async_eval(original):
            def call(*args, **kwargs):
                record = _batch.get()
                if (
                    record is None
                    or not record.compact
                    or _operation.get() != "mlx.async_submit.host"
                ):
                    return original(*args, **kwargs)
                memory = {
                    "mlx.memory_limit_bytes": module.mx.get_memory_limit(),
                    "mlx.active_before_bytes": module.mx.get_active_memory(),
                }
                with runtime.phase("mlx.async_eval.call.host", batch=record, **memory):
                    result = original(*args, **kwargs)
                record.phases[-1][2]["mlx.peak_after_bytes"] = module.mx.get_peak_memory()
                return result

            return call

        wrap(module.mx, "async_eval", async_eval)

        def gate(original):
            def call(self, *args, **kwargs):
                decision = original(self, *args, **kwargs)
                record = _batch.get()
                if record is not None:
                    record.span.set_attribute("llm.pipeline.eligible", decision.eligible)
                    record.span.set_attribute("llm.pipeline.reason", decision.reason)
                return decision

            return call

        wrap(owner, "_evaluate_pipeline_gate", gate)
        wrap(owner, "execute_model", runner_phase("runner.execute.host", lambda _, args: args[0]))

        def state_output(self, _):
            return getattr(self._execute_model_state, "scheduler_output", None)

        wrap(owner, "sample_tokens", runner_phase("runner.sample.host", state_output))
        for method, span in {
            "_start_paged_forward": "runner.prepare_submit.host",
            "_target_forward": "mlx.forward.graph.host",
            "_submit_paged_forward_outputs": "mlx.async_submit.host",
            "_sample_paged_batch": "mlx.sample_materialize.host",
        }.items():
            wrap(owner, method, runner_phase(span))
    elif name.endswith("decode_pipeline"):
        wrap(
            module.DecodePipeline,
            "submit",
            runner_phase("mlx.deferred.register.host", lambda _, args: args[0].scheduler_output),
        )
        wrap(
            module.DecodePipeline,
            "_resolve_pending",
            runner_phase(
                "mlx.deferred.resolve.host",
                lambda self, _: getattr(self._pending, "scheduler_output", None),
            ),
        )
    elif name.endswith("sampling_batch"):

        def sample(original):
            def call(*args, **kwargs):
                with runtime.phase("mlx.sampling_eval.host"):
                    return original(*args, **kwargs)

            return call

        wrap(module, "sample_from_logits", sample)


def patch_scheduler(owner) -> None:
    def add(original):
        def call(self, request, *args, **kwargs):
            record = runtime.ensure_request(request)
            result = original(self, request, *args, **kwargs)
            if record:
                events = [event for event in request.events if event.type.name == "QUEUED"]
                if not events:
                    raise RuntimeError("Full instrumentation requires QUEUED events")
                runtime.event(
                    record.span, "request.queued", stamp_ns=int(events[0].timestamp * 1e9)
                )
            return result

        return call

    wrap(owner, "add_request", add)

    def schedule(original):
        def call(self, *args, **kwargs):
            started = time.monotonic_ns()
            output = original(self, *args, **kwargs)
            ended = time.monotonic_ns()
            runtime.scheduled(self, output, started, ended)
            return output

        return call

    wrap(owner, "schedule", schedule)

    def update(original):
        def call(self, output, *args, **kwargs):
            record = runtime.batches.get(id(output))
            token = _batch.set(record)
            updating = _updating.set(True)
            try:
                with runtime.phase("scheduler.update_output", batch=record):
                    result = original(self, output, *args, **kwargs)
                if record is not None or runtime.requests:
                    runtime.finish_batch(record, result)
                return result
            finally:
                _updating.reset(updating)
                _batch.reset(token)

        return call

    wrap(owner, "update_from_output", update)
    for method, event in (
        ("_free_request", "request.finished"),
        ("_free_request_blocks", "kv.references_released"),
    ):

        def release(original, event=event):
            def call(self, request, *args, **kwargs):
                record = runtime.requests.get(request.request_id)
                result = original(self, request, *args, **kwargs)
                if record:
                    runtime.event(record.span, event)
                    if not _updating.get() and event == "request.finished":
                        record.span.set_attribute("llm.terminal_without_batch", True)
                        for batch in record.completed:
                            runtime.emit_batch(batch)
                        record.span.end()
                        runtime.requests.pop(request.request_id, None)
                return result

            return call

        wrap(owner, method, release)


def observe_output(headers) -> bool:
    parent = context(headers)
    if parent is None:
        return False
    mode = trace.get_current_span(parent).get_span_context().trace_state.get("llmobs")
    return mode != "compact" or "x-llm-observe-batch-trace" in headers


def verify_sources() -> dict:
    records = {}
    for name, members in TARGETS.items():
        module = importlib.import_module(name)
        signatures = {}
        for member in members:
            value = module
            for part in member.split("."):
                value = getattr(value, part)
            signatures[member] = str(inspect.signature(value))
        path = Path(module.__file__).resolve()
        records[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "signatures": signatures,
        }
    write_json(MANIFEST, records)
    return records


class BridgeLoader(Loader):
    def __init__(self, original, name: str) -> None:
        self.original, self.name = original, name

    def create_module(self, spec):
        return self.original.create_module(spec)

    def exec_module(self, module) -> None:
        if os.environ.get("LLM_OBSERVE_PREFLIGHT") != "1":
            records = json.loads(MANIFEST.read_text())
            path = Path(module.__spec__.origin).resolve()
            if records[self.name]["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise RuntimeError(f"Instrumentation source changed: {self.name}; run preflight")
        self.original.exec_module(module)
        patch_module(self.name, module)


class BridgeFinder(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in TARGETS:
            return None
        spec = PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Diagnostic module unavailable: {fullname}")
        spec.loader = BridgeLoader(spec.loader, fullname)
        return spec


def install() -> None:
    global _installed
    if _installed:
        return
    sys.meta_path.insert(0, BridgeFinder())
    _installed = True
    for name in TARGETS:
        if name in sys.modules:
            patch_module(name, sys.modules[name])
