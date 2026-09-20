"""CLI entry points for environment inspection, training and inference."""

import argparse
import json
import tomllib
from pathlib import Path

from .checkpoint import load
from .data import prepare
from .generate import generate
from .runtime import device_for, environment
from .train import evaluate, train


def main() -> None:
    parser = argparse.ArgumentParser(prog="llm-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    trainer = commands.add_parser("train")
    trainer.add_argument("--config", type=Path, default=Path("configs/tiny.toml"))
    trainer.add_argument("--out", type=Path, default=Path("runs/tiny"))
    trainer.add_argument("--device", choices=["cpu", "mps", "auto"], default="cpu")
    trainer.add_argument("--data", type=Path)
    trainer.add_argument("--resume", type=Path)
    trainer.add_argument("--steps", type=int)
    for name in ("generate", "evaluate"):
        sub = commands.add_parser(name)
        sub.add_argument("--checkpoint", type=Path, required=True)
        sub.add_argument("--device", choices=["cpu", "mps", "auto"], default="cpu")
        if name == "generate":
            sub.add_argument("--prompt", default="Ada likes ")
            sub.add_argument("--max-new-tokens", type=int, default=40)
            sub.add_argument("--temperature", type=float, default=0.0)
            sub.add_argument("--seed", type=int, default=42)
        else:
            sub.add_argument("--data", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            result = environment()
        elif args.command == "train":
            config = tomllib.loads(args.config.read_text())
            if args.steps is not None:
                config["training"]["steps"] = args.steps
            result = train(config, args.out, args.device, args.data, args.resume)
            (args.out / "report.json").write_text(json.dumps(result, indent=2) + "\n")
        elif args.command == "generate":
            result = generate(
                args.checkpoint,
                args.prompt,
                args.max_new_tokens,
                args.device,
                args.temperature,
                args.seed,
            )
        else:
            device = device_for(args.device)
            model, payload = load(args.checkpoint, device)
            _, valid, metadata = prepare(
                args.data, model.config.context_length, payload["training"]["seed"]
            )
            if metadata != payload["data"]:
                raise ValueError("Evaluation data differs; supply original --data")
            result = {
                "validation_loss": evaluate(
                    model, valid, device, payload["training"]["batch_size"]
                ),
                "device": str(device),
            }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
