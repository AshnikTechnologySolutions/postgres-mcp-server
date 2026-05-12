import os

from mcp_server.config import (
    OTEL_ENVIRONMENT,
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
    OTEL_SERVICE_NAME,
    OTEL_SERVICE_VERSION,
    logger,
)

_OTEL_INITIALIZED = False

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:  # pragma: no cover
    trace = None
    OTLPSpanExporter = None
    FastAPIInstrumentor = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None


def otel_enabled() -> bool:
    return os.getenv("OTEL_ENABLED", "false").strip().lower() == "true"


def init_otel(app=None) -> None:
    global _OTEL_INITIALIZED

    if _OTEL_INITIALIZED or not otel_enabled():
        return

    if not all((trace, OTLPSpanExporter, FastAPIInstrumentor, Resource, TracerProvider, BatchSpanProcessor)):
        logger.warning("OTEL_ENABLED=true but OpenTelemetry dependencies are not installed")
        return

    resource = Resource.create(
        {
            "service.name": OTEL_SERVICE_NAME,
            "service.version": OTEL_SERVICE_VERSION,
            "deployment.environment": OTEL_ENVIRONMENT,
        }
    )

    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_TRACES_ENDPOINT))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    if app is not None:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    _OTEL_INITIALIZED = True
    logger.info("OpenTelemetry tracing enabled")


def get_tracer(name: str):
    if not _OTEL_INITIALIZED or trace is None:
        return None
    return trace.get_tracer(name)


def set_current_span_attribute(name: str, value: str) -> None:
    if trace is None:
        return

    span = trace.get_current_span()
    span_context = span.get_span_context()
    if not span_context.is_valid:
        return

    span.set_attribute(name, value)


def current_trace_context() -> dict[str, str | None]:
    if trace is None or not _OTEL_INITIALIZED:
        return {"trace_id": None, "span_id": None}

    span = trace.get_current_span()
    span_context = span.get_span_context()
    if not span_context.is_valid:
        return {"trace_id": None, "span_id": None}

    return {
        "trace_id": f"{span_context.trace_id:032x}",
        "span_id": f"{span_context.span_id:016x}",
    }
