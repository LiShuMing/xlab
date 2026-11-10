"""Bounded OTLP export for standalone tools; serving reuses vLLM's provider."""

import secrets

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.id_generator import IdGenerator

from llm_observe.paths import local_origin


class IndependentIdGenerator(IdGenerator):
    """Keep trace identity independent of model PRNG reseeding and draws."""

    def generate_span_id(self) -> int:
        return secrets.randbits(64) or self.generate_span_id()

    def generate_trace_id(self) -> int:
        return secrets.randbits(128) or self.generate_trace_id()

    def is_trace_id_random(self) -> bool:
        return True


class IndependentTracerProvider(TracerProvider):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("id_generator", IndependentIdGenerator())
        super().__init__(*args, **kwargs)


def provider(service: str, endpoint: str) -> TracerProvider:
    local_origin(endpoint)
    result = IndependentTracerProvider(resource=Resource.create({"service.name": service}))
    result.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint + "/v1/traces", timeout=2),
            max_queue_size=512,
            max_export_batch_size=64,
            schedule_delay_millis=500,
        )
    )
    return result
