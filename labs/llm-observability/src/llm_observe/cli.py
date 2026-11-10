"""Commands are deliberately separate: download, lifecycle, and inference."""

import argparse
import subprocess
import sys

from llm_observe.paths import prepare_local


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download")
    start = sub.add_parser("start")
    start.add_argument("--model-url", default="http://127.0.0.1:8000")
    start.add_argument("--port-offset", type=int, default=0)
    for command in ("stop", "status", "check", "check-git", "doctor", "smoke"):
        sub.add_parser(command)
    for command in ("stop-vllm", "status-vllm"):
        sub.add_parser(command)
    restart = sub.add_parser("restart-vllm")
    restart.add_argument("--python")
    restart.add_argument("--working-directory")
    restart.add_argument("--adopt-pid", type=int)
    restart.add_argument("--offline", action=argparse.BooleanOptionalAction, default=None)
    restart.add_argument("--instrument", action=argparse.BooleanOptionalAction, default=None)
    restart.add_argument("--timeout", type=int, default=180)
    restart.add_argument("serve_args", nargs=argparse.REMAINDER)
    probe_parser = sub.add_parser("probe")
    probe_parser.add_argument("--model", required=True)
    probe_parser.add_argument("--prompt", required=True)
    probe_parser.add_argument("--max-tokens", type=int, default=256)
    probe_parser.add_argument("--require-server-traces", action="store_true")
    probe_parser.add_argument("--minimal-trace", action="store_true")
    probe_parser.add_argument("--trace-mode", choices=("full", "compact", "off"), default="compact")
    investigate = sub.add_parser("investigate")
    investigate.add_argument("--model", required=True)
    controlled = sub.add_parser("controlled")
    controlled.add_argument("--model", required=True)
    controlled.add_argument("--label", required=True)
    controlled.add_argument("--rounds", type=int, default=12)
    controlled.add_argument(
        "--modes", nargs="+", choices=("off", "compact", "full"), default=["off", "compact", "full"]
    )
    controlled.add_argument("--kv-blocks", type=int, required=True)
    controlled.add_argument("--queue-depth", type=int, required=True)
    args = parser.parse_args()
    prepare_local()
    try:
        from llm_observe import manager

        with manager.lock():
            if args.command == "download":
                from llm_observe.downloads import download

                download()
            elif args.command == "start":
                manager.start(args.model_url, args.port_offset)
            elif args.command == "stop":
                manager.stop()
            elif args.command == "status":
                return manager.status()
            elif args.command == "check":
                manager.check()
            elif args.command == "check-git":
                from llm_observe.safegit import check_git

                check_git()
            elif args.command == "doctor":
                from llm_observe.doctor import doctor

                doctor()
            elif args.command == "smoke":
                from llm_observe.smoke import smoke

                smoke()
            elif args.command == "probe":
                from llm_observe.client import probe

                probe(
                    args.model,
                    args.prompt,
                    args.max_tokens,
                    args.require_server_traces,
                    args.minimal_trace,
                    trace_mode=args.trace_mode,
                )
            elif args.command in {"restart-vllm", "stop-vllm", "status-vllm"}:
                from llm_observe import model

                if args.command == "restart-vllm":
                    if args.timeout < 1:
                        raise ValueError("timeout must be positive")
                    model.restart(args)
                elif args.command == "stop-vllm":
                    model.stop()
                else:
                    return model.status()
            elif args.command == "investigate":
                from llm_observe.investigate import run

                run(args.model)
            elif args.command == "controlled":
                from llm_observe.controlled import run

                run(
                    args.model,
                    args.label,
                    args.rounds,
                    args.modes,
                    args.kv_blocks,
                    args.queue_depth,
                )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
