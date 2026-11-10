"""Foreground opt-in launcher; never stops or rewrites an existing server."""

import importlib.metadata
import json
import os
import runpy
import socket
import sys

from llm_observe.paths import LOCAL, ROOT


def validate_arguments(args: list[str]) -> None:
    if not args or args[0].startswith("-"):
        raise ValueError("Supply MODEL followed by existing vllm serve options")
    reserved = ("--otlp-traces-endpoint", "--middleware", "--host", "--port")
    if any(arg.split("=")[0] in reserved for arg in args):
        raise ValueError("Host/port/tracing are managed by this launcher")


def check_environment() -> str:
    version = importlib.metadata.version("vllm")
    if version.split("+")[0] != "0.33.0":
        raise RuntimeError("Integration requires reviewed vLLM 0.33.0")
    from vllm.tracing import is_tracing_available

    from llm_observe.middleware import TracingMiddleware

    if not is_tracing_available() or TracingMiddleware is None:
        raise RuntimeError("vLLM tracing dependencies are unavailable")
    if os.environ.get("LLM_OBSERVE_INSTRUMENT") == "1":
        from llm_observe.instrumentation import verify_sources

        verify_sources()
    return version


def main() -> None:
    args = sys.argv[1:]
    check_only = bool(args and args[0] == "--check")
    if check_only:
        args = args[1:]
    validate_arguments(args)
    if os.environ.get("LLM_OBSERVE_INSTRUMENT") == "1" and "--disable-log-stats" in args:
        raise ValueError("Full instrumentation requires log stats")
    version = check_environment()
    if check_only:
        print(json.dumps({"vllm_version": version, "tracing_available": True}))
        return
    state = json.loads((LOCAL / "run" / "services.json").read_text())
    from urllib.parse import urlsplit

    model = urlsplit(state["model_url"])
    host, port = model.hostname, model.port or 80
    with socket.socket(socket.AF_INET6 if host == "::1" else socket.AF_INET) as sock:
        if sock.connect_ex((host, port)) == 0:
            raise SystemExit("Model port is occupied; existing server left untouched")
    os.environ.update(
        {
            "OTEL_SERVICE_NAME": "vllm-metal",
            "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf",
            "OTEL_TRACES_SAMPLER": "parentbased_always_on",
            "OTEL_BSP_MAX_QUEUE_SIZE": "8192",
            "OTEL_BSP_SCHEDULE_DELAY": "500",
            "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }
    )
    sys.argv = [
        "vllm",
        "serve",
        *args,
        "--host",
        host,
        "--port",
        str(port),
        "--otlp-traces-endpoint",
        f"http://127.0.0.1:{state['ports']['otlp_http']}/v1/traces",
        "--enable-request-id-headers",
        "--middleware",
        "llm_observe.middleware.TracingMiddleware",
    ]
    runpy.run_module("vllm.entrypoints.cli.main", run_name="__main__")


if __name__ == "__main__":
    main()
