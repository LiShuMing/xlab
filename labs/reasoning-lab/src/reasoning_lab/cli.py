"""Local-only commands. No implicit training, upload, or background scheduler.

全部子命令都是本地动作：data 生成题库、fetch 下载权重、doctor 探针、
run 训练/评测、smoke 小模型冒烟、parity 与 HF 对账、compare 配对比较、
report 渲染离线 HTML。没有任何一步会隐式开始训练或上传结果。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .logging import configure


def parser() -> argparse.ArgumentParser:
    """命令行骨架。`run` 只负责把显式参数整理成 Config 的 overrides。"""
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Probe device, dtype, backward and optimizer")
    doctor.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    doctor.add_argument("--output", type=Path, default=Path(".local/doctor.json"))
    data = commands.add_parser("data", help="Generate an immutable solver-verified dataset")
    data.add_argument("--task", choices=["countdown", "maze", "sql"], default="countdown")
    data.add_argument("--output", type=Path, default=Path(".local/data/countdown-v1"))
    data.add_argument("--seed", type=int, default=42)
    data.add_argument("--difficulty", choices=["L1", "L2", "L3", "L4"], default="L2")
    for name, default in [("train", 1000), ("dev", 200), ("test", 400), ("ood", 200)]:
        data.add_argument(f"--{name}", type=int, default=default)
    fetch = commands.add_parser("fetch", help="Download original Qwen3 weights/tokenizer")
    fetch.add_argument("--repo", default="Qwen/Qwen3-0.6B")
    fetch.add_argument("--revision", default="main")
    fetch.add_argument("--output", type=Path, default=Path(".local/models/qwen3-0.6b"))
    run = commands.add_parser("run", help="Execute one budgeted eval/SFT/GRPO/benchmark")
    run.add_argument("--config", type=Path, required=True)
    for name in [
        "stage",
        "task",
        "model",
        "data",
        "output",
        "device",
        "dtype",
        "split",
        "adapter",
        "resume",
    ]:
        run.add_argument(f"--{name}")
    for name in ["steps", "limit", "seed", "samples", "max-new-tokens"]:
        run.add_argument(f"--{name}", type=int)
    run.add_argument("--max-seconds", type=float)
    run.add_argument("--temperature", type=float)
    smoke = commands.add_parser("smoke", help="Offline tiny-model SFT + GRPO + checkpoint smoke")
    smoke.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    smoke.add_argument("--output", type=Path)
    parity = commands.add_parser("parity", help="Sequential HF FP32 and hand-written-model checks")
    parity.add_argument("--model", type=Path, default=Path(".local/models/qwen3-0.6b"))
    parity.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    parity.add_argument("--output", type=Path, default=Path(".local/parity"))
    # 内部子命令：parity 用子进程跑 HF 参考前向，把官方实现与自写实现隔在不同进程，
    # 避免两套模型同时驻留。help=SUPPRESS 表示它不是给人手工敲的。
    reference = commands.add_parser("_hf-reference", help=argparse.SUPPRESS)
    reference.add_argument("--model", type=Path, required=True)
    reference.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser("compare", help="Paired question-cluster bootstrap")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    compare.add_argument("--output", type=Path, default=Path(".local/comparison.json"))
    report = commands.add_parser("report", help="Render one run as an offline HTML report")
    report.add_argument("run", type=Path)
    return root


def execute(cfg):
    """一个 run 的完整生命周期：建目录、记身份、加载、训练或评测、落盘、渲染。

    这里才 import torch/transformers：data/doctor/fetch 等命令不需要模型依赖，
    只有真正要跑模型时才付这个代价。
    """
    import torch
    from transformers import AutoTokenizer

    from .data import load_dataset, write_json
    from .evaluation import evaluate
    from .experiments import benchmark
    from .logging import attach_file, detach, get_logger
    from .model import load_model
    from .runs import Run, adapter_hash, model_identity, warm_start
    from .runtime import Monitor, choose_device, seed_all
    from .training import train

    log = get_logger("cli")
    start_time = time.monotonic()
    device = choose_device(cfg.device)
    seed_all(cfg.seed)
    log.info(
        "starting stage=%s task=%s device=%s dtype=%s steps=%d max_seconds=%g",
        cfg.stage,
        cfg.task,
        device,
        cfg.dtype,
        cfg.steps,
        cfg.max_seconds,
    )
    path, data = Path(cfg.model), Path(cfg.data)
    manifest = json.loads((data / "manifest.json").read_text())
    # 题目必须与配置一致：拿 maze 的权重去跑 countdown 的题，
    # 会在判卷时变成“全错”，不如在这里直接失败
    if manifest["task"] != cfg.task:
        raise ValueError("Config task differs from dataset")
    identity = model_identity(path)
    # 先算模型身份再建 Run：manifest 和 protocol 都要用到它
    run = Run(cfg, device, identity, manifest)
    # 日志 handler 必须在 run 目录建立之后挂上，否则 run.log 的第一屏身份信息写不进去
    handler = attach_file(run.path / "run.log")
    try:
        run.announce()
        with Monitor(run.path / "system.jsonl", device) as monitor:
            load_metrics = {}
            with monitor.phase("load", load_metrics):
                model, report = load_model(
                    path, device, getattr(torch, cfg.dtype), cfg.rank, cfg.alpha
                )
                model.attention_impl = cfg.attention
                model.gradient_checkpointing = cfg.gradient_checkpointing
                tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
                if cfg.adapter:
                    report["warm_start"] = warm_start(Path(cfg.adapter), model, identity)
                report["starting_adapter_hash"] = adapter_hash(model.adapter_state())
                write_json(run.path / "load.json", report)
            run.log("metrics", {"stage": "load", **load_metrics})
            if cfg.stage in {"sft", "grpo"}:
                # 训练只用 train 出题、dev 选模；test/OOD 留给冻结审计
                train_tasks = load_dataset(data, "train")
                dev = load_dataset(data, "dev")
                result = train(model, tokenizer, train_tasks, dev, cfg, run, monitor, start_time)
            else:
                if cfg.resume:
                    # 评测没有“接着优化”的语义，要评上一阶段的权重请用 --adapter
                    raise ValueError("Use --adapter to evaluate weights; --resume is training only")
                tasks = load_dataset(data, cfg.split)
                # limit 会改变题集指纹（task_hash），带 limit 的结果不能与全量结果 compare
                tasks = tasks[: cfg.limit] if cfg.limit is not None else tasks
                if cfg.stage == "eval":
                    timings = {}
                    with monitor.phase("evaluation", timings):
                        result = evaluate(
                            model,
                            tokenizer,
                            tasks,
                            cfg,
                            run.path / "eval" / cfg.split,
                            deadline=start_time + cfg.max_seconds,
                        )
                    run.log("metrics", {"stage": "evaluation", **timings})
                else:
                    result = benchmark(model, tokenizer, tasks, cfg, run, monitor)
                run.status("complete", complete=result.get("complete", True))
        # 采样线程的异常已在 Monitor 里捕获，不能让监控故障伪装成训练失败
        if monitor.error:
            log.warning("memory sampler stopped early: %s", monitor.error)
        write_json(run.path / "summary.json", result)
        from .report import render

        render(run.path)
        log.info("run finished %s", run.path.resolve())
        return {"run": str(run.path.resolve()), **result}
    except BaseException as exc:
        run.status("failed", error=f"{type(exc).__name__}: {exc}")
        log.error("run failed: %s: %s", type(exc).__name__, exc)
        raise
    finally:
        detach(handler)


def main(argv=None) -> int:
    """子命令分派。返回码由结果里的 passed 决定，便于 CI 直接判断。"""
    args = parser().parse_args(argv)
    log = configure().getChild("cli")
    log.info("command %s", args.command)
    if args.command == "data":
        from .data import generate_dataset

        result = generate_dataset(
            args.output,
            args.task,
            args.seed,
            {name: getattr(args, name) for name in ["train", "dev", "test", "ood"]},
            args.difficulty,
        )
    elif args.command == "fetch":
        from huggingface_hub import HfApi, snapshot_download

        from .data import write_json

        # 先把 main 解析成不可变 commit 再下载：否则之后 main 前进了，
        # 同一份 source.json 会指向不同权重
        revision = HfApi().model_info(args.repo, revision=args.revision).sha
        snapshot_download(
            args.repo,
            revision=revision,
            local_dir=args.output,
            allow_patterns=[
                "*.json",
                "*.safetensors",
                "*.txt",
                "*.model",
                "*.jinja",
                "README.md",
                "LICENSE",
            ],
        )
        result = {"repo": args.repo, "revision": revision}
        write_json(args.output / "source.json", result)
    elif args.command == "doctor":
        from .data import write_json
        from .runtime import choose_device, doctor

        result = doctor(choose_device(args.device))
        write_json(args.output, result)
    elif args.command == "run":
        from .config import Config

        overrides = {
            key: value
            for key, value in vars(args).items()
            if key not in {"command", "config"} and value is not None
        }
        result = execute(Config.load(args.config, overrides))
    elif args.command == "smoke":
        from .experiments import smoke
        from .runtime import choose_device

        timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S-%f")
        result = smoke(args.output or Path(".local/smoke") / timestamp, choose_device(args.device))
    elif args.command == "_hf-reference":
        from .experiments import hf_reference

        hf_reference(args.model, args.output)
        return 0
    elif args.command == "parity":
        from .experiments import parity
        from .runtime import choose_device

        reference = args.output / "reference.pt"
        # 参考前向放独立进程跑：两套模型不必同时驻留内存，
        # 也避免 HF 与自写实现互相影响数值/线程设置
        subprocess.run(
            [
                sys.executable,
                "-m",
                "reasoning_lab",
                "_hf-reference",
                "--model",
                str(args.model),
                "--output",
                str(reference),
            ],
            check=True,
        )
        result = parity(
            args.model, reference, args.output / "summary.json", choose_device(args.device)
        )
    elif args.command == "report":
        from .report import render

        result = {"report": str(render(args.run).resolve())}
    else:
        from .evaluation import compare

        result = compare(args.left, args.right, args.output)
    # allow_nan=False：输出要给别的工具解析，NaN 会让 JSON 直接非法
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if result.get("passed") is False else 0
