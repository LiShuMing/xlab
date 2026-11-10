"""Versioned provenance, bounded run directories, and complete training checkpoints."""

from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import torch

from .data import write_json
from .logging import get_logger
from .runtime import environment, git_identity
from .tasks import digest


def file_hash(path: Path) -> str:
    """分块 sha256：模型权重动辄数 GB，没必要整个读进内存。"""
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def adapter_hash(state: dict) -> str:
    """把 {参数名: 张量} 压成一个指纹。

    三个细节决定它可复现：按名字排序（与字典顺序无关）、detach().cpu()
    （与设备无关）、contiguous().numpy().tobytes()（与内存布局无关）。
    """
    sha = hashlib.sha256()
    for name, value in sorted(state.items()):
        sha.update(name.encode())
        sha.update(value.detach().cpu().contiguous().numpy().tobytes())
    return sha.hexdigest()


def model_identity(path: Path) -> dict:
    """模型目录的身份：白名单配置/分词文件，加上全部 *.safetensors 权重分片。

    目录里可能还躺着日志和下载残留，不能整个目录哈希；但权重必须全覆盖，
    否则换了某个分片而 hash 不变。source.json 记录下载来源，可以为空。
    """
    names = {
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
        "special_tokens_map.json",
        "added_tokens.json",
        "model.safetensors.index.json",
    }
    names.update(p.name for p in path.glob("*.safetensors"))
    hashes = {name: file_hash(path / name) for name in sorted(names) if (path / name).exists()}
    source = path / "source.json"
    return {
        "files": hashes,
        "hash": digest(hashes),
        "source": json.loads(source.read_text()) if source.exists() else None,
    }


def protocol_identity(cfg, model_id: dict, data_manifest: dict) -> dict:
    """训练协议指纹：它变了，旧 checkpoint 就不允许 resume。

    排除的是不改变训练语义的字段：输出目录、预算、limit、续训入口、
    实验卡描述，以及 model/data/device 三个路径。路径被换成内容哈希后
    再参与比较：换机器或挪模型目录不该让协议失效，权重内容变了则必须失效。
    """
    excluded = {
        "output",
        "steps",
        "max_seconds",
        "limit",
        "resume",
        "adapter",
        "hypothesis",
        "change",
        "model",
        "data",
        "device",
    }
    return {
        "model": model_id["hash"],
        "data": digest(data_manifest),
        "training": {k: v for k, v in cfg.to_dict().items() if k not in excluded},
    }


def rng_state(device: str) -> dict:
    """四路随机数快照：python random、torch、numpy，以及 MPS 专用发生器。

    numpy 的 state 里含一个 ndarray，直接 json 序列化会失败，
    所以存成 list，恢复时再拼回 tuple。
    """
    numpy = np.random.get_state()
    result = {
        "python": random.getstate(),
        "torch": torch.get_rng_state(),
        "numpy": [numpy[0], numpy[1].tolist(), numpy[2], numpy[3], numpy[4]],
    }
    if device == "mps":
        result["mps"] = torch.mps.get_rng_state()
    return result


def restore_rng(value: dict, device: str) -> None:
    """按快照原样恢复。MPS 缺存档时宁可直接报错：
    静默换成新序列会让“同一 seed 可复现”悄悄失效。
    """
    random.setstate(value["python"])
    torch.set_rng_state(value["torch"])
    state = value["numpy"]
    np.random.set_state((state[0], np.array(state[1], dtype=np.uint32), *state[2:]))
    if device == "mps":
        if "mps" not in value:
            raise ValueError("Cannot resume MPS exactly without saved MPS RNG")
        torch.mps.set_rng_state(value["mps"])


def save_checkpoint(
    path: Path,
    model,
    optimizer,
    step: int,
    cursor: int,
    protocol: dict,
    device: str,
    elapsed: float,
    reference: dict | None,
    best: float,
) -> None:
    """一次检查点的完整内容：走到哪、权重是什么、随机数在哪。

    除 adapter 权重外还要存 optimizer（AdamW 的动量）、rng、step、cursor、
    protocol 和 elapsed；少任何一项，resume 出来的轨迹都会偏离原来的 run。
    architecture/rank/alpha 是给 warm start 校验用的，不参与 resume。

    先写 .tmp 再 os.replace：中途中断时旧检查点仍完整，
    不会留下一个写了一半、torch.load 直接报错的半成品。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "schema": 1,
        "adapter": model.adapter_state(),
        "optimizer": optimizer.state_dict(),
        "step": step,
        "cursor": cursor,
        "protocol": protocol,
        "rng": rng_state(device),
        "elapsed_seconds": elapsed,
        "reference": reference,
        "best_dev": best,
        "architecture": asdict(model.config),
        "rank": model.rank,
        "alpha": model.alpha,
    }
    temp = path.with_suffix(".tmp")
    torch.save(value, temp)
    os.replace(temp, path)


def load_checkpoint(path: Path, model, protocol: dict, optimizer=None, device="cpu") -> dict:
    """严格续训：协议逐字段相等才允许加载。

    weights_only=True 让反序列化只还原张量，避免 checkpoint 夹带可执行对象；
    protocol 里含 source_hash/lock_hash/device，所以换了代码或设备就别假装能接着跑。
    optimizer 为 None 时只装权重，不碰优化器与 RNG（只读权重的场景）。
    """
    value = torch.load(path, map_location="cpu", weights_only=True)
    if value.get("schema") != 1 or value["protocol"] != protocol:
        raise ValueError("Checkpoint schema, model, data or protocol mismatch")
    model.load_adapter(value["adapter"])
    if optimizer is not None:
        optimizer.load_state_dict(value["optimizer"])
        restore_rng(value["rng"], device)
    return value


def warm_start(path: Path, model, model_id: dict) -> dict:
    """只换权重、不继承训练状态：在上一个 adapter 上开新实验。

    校验比 resume 少（模型身份 + LoRA 的 rank/alpha），
    因为这里不要求接着同一条优化器轨迹。
    """
    value = torch.load(path, map_location="cpu", weights_only=True)
    if (
        value.get("schema") != 1
        or value["protocol"]["model"] != model_id["hash"]
        or value["rank"] != model.rank
        or value["alpha"] != model.alpha
    ):
        raise ValueError("Warm-start model identity or LoRA configuration mismatch")
    model.load_adapter(value["adapter"])
    return {"path": str(path), "sha256": file_hash(path), "step": value["step"]}


class Run:
    """一次运行的目录：所有产物写进同一个不可复用的路径，便于事后审计。

    目录名带微秒时间戳，且 exist_ok=False：同名冲突直接失败，
    而不是把两次运行的日志混在一起。
    """

    def __init__(self, cfg, device: str, model_id: dict, data_manifest: dict):
        root = Path(cfg.output)
        timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S-%f")
        self.path = root / f"{timestamp}_{cfg.task}_{cfg.stage}_{cfg.seed}"
        self.path.mkdir(parents=True, exist_ok=False)
        self.config, self.device = cfg, device
        source = Path(__file__).resolve().parent
        lock = source.parents[1] / "uv.lock"
        # manifest 回答“这次跑的是什么”：模型/数据的哈希、代码哈希、依赖锁、git 提交。
        # source_hash 覆盖本包全部 *.py，改动任何一行实现都会换指纹。
        # parent_run 记下它是从哪个 checkpoint 续训或 warm start 来的。
        manifest = {
            "schema": 1,
            "model": model_id,
            "data": data_manifest,
            "source_hash": digest({p.name: file_hash(p) for p in source.glob("*.py")}),
            "lock_hash": file_hash(lock) if lock.exists() else None,
            "git": git_identity(source),
            "parent_run": cfg.resume or cfg.adapter,
        }
        write_json(self.path / "config.json", cfg.to_dict())
        write_json(self.path / "manifest.json", manifest)
        write_json(self.path / "environment.json", environment(device))
        # protocol 在 manifest 之上再加源/锁/设备，构成 resume 的准入条件
        self.protocol = protocol_identity(cfg, model_id, data_manifest)
        self.protocol["source_hash"] = manifest["source_hash"]
        self.protocol["lock_hash"] = manifest["lock_hash"]
        self.protocol["device"] = device
        self.manifest = manifest
        # 实验卡先写假设与改动，再看指标：避免拿到数字后反向编理由
        self.status("running")
        self.path.joinpath("decision.md").write_text(
            f"# Experiment card\n\nHypothesis: {cfg.hypothesis}\n\nChange: {cfg.change}\n\n"
            f"Budget: {cfg.steps} updates / {cfg.max_seconds} seconds.\n\n"
            "Decision: pending. Use dev evidence; reserve test/OOD for frozen-stage audits.\n"
        )
        print(f"Run: {self.path.resolve()}", flush=True)

    def announce(self) -> None:
        """在日志文件已存在后写入身份信息，让 run.log 第一屏就是 provenance。"""
        logger = get_logger("run")
        logger.info(
            "run %s stage=%s task=%s seed=%d device=%s",
            self.path.name,
            self.config.stage,
            self.config.task,
            self.config.seed,
            self.device,
        )
        logger.info(
            "provenance model=%s data=%s source=%s lock=%s commit=%s",
            self.protocol["model"][:12],
            self.protocol["data"][:12],
            self.manifest["source_hash"][:12],
            # A missing lock file is recorded as absent provenance, not as a failure.
            (self.manifest["lock_hash"] or "none")[:12],
            self.manifest["git"]["commit"] or "none",
        )
        if self.config.resume:
            logger.info("budget continues from checkpoint %s", self.config.resume)
        if self.config.adapter:
            logger.info("weights warm start from %s", self.config.adapter)

    def log(self, name: str, record: dict) -> None:
        """追加一行 JSONL。allow_nan=False：NaN 不是合法 JSON，
        写进去只会在下游解析时于另一台机器上炸掉。"""
        with (self.path / f"{name}.jsonl").open("a") as file:
            file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")

    def status(self, status: str, **details) -> None:
        """覆盖写当前状态（running/completed/failed），给外部脚本轮询用。"""
        write_json(self.path / "status.json", {"status": status, **details})
