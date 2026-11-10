"""JSONL → 清洗 → 常驻字节分词器 → 按分片排序拼接 → 幂等输出。

故意在一个分片落盘后、成功返回前退出 Worker，检验 Ray Data 重试。
token ID：0=PAD，1=EOS，UTF-8 字节+2；这是教学分词器，不是 BPE。
"""
from collections import Counter
import hashlib
import html
import json
import os
from pathlib import Path
import re
import unicodedata
import uuid

import numpy as np
import ray
import ray.data

from common import RUN_DIR, run, session

SHARDS = 4


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fixture():
    """已知清洗结果作为参考，避免验收时再次调用待测清洗函数。"""
    raw, expected = [], []
    for doc_id in range(64):
        if doc_id % 11 == 0:
            text = "<p> \n\t </p>"
        else:
            clean = f"Document {doc_id}: Ray & Spark 训练数据 " + "learn " * (doc_id % 5 + 1)
            clean = clean.strip()
            text = "<p>" + clean.replace(" & ", " &amp; ").replace(" ", "  ") + "</p>"
            expected.append({"id": doc_id, "text": clean})
        raw.append({"id": doc_id, "text": text})
    return raw, expected


def clean_batch(batch):
    ids, texts = [], []
    for doc_id, text in zip(batch["id"], batch["text"]):
        text = re.sub(r"<[^>]*>", " ", str(text))
        text = unicodedata.normalize("NFKC", html.unescape(text))
        text = " ".join(text.split())
        if text:
            ids.append(int(doc_id))
            texts.append(text)
    return {"id": np.asarray(ids, dtype=np.int64), "text": np.asarray(texts, dtype=str)}


class ByteTokenizer:
    def __init__(self):
        # 模拟一次性加载词表；batch 之间保留 instance 和 calls。
        self.vocabulary = {i: i + 2 for i in range(256)}
        self.instance = uuid.uuid4().hex
        self.calls = 0

    def __call__(self, batch):
        self.calls += 1
        tokens = [[self.vocabulary[b] for b in str(text).encode("utf-8")] + [1]
                  for text in batch["text"]]
        n = len(tokens)
        return {
            "id": batch["id"], "shard_id": batch["id"] % SHARDS,
            "tokens_json": np.asarray([canonical(t) for t in tokens]),
            "tokenizer_instance": np.full(n, self.instance),
            "tokenizer_pid": np.full(n, os.getpid()),
            "tokenizer_call": np.full(n, self.calls),
        }


def pack_and_write_group(batch, output_dir, sequence_length, inject_failure):
    """一个确定分片为一个重放单元，不把跨 batch 余数留在 Actor 内存中。"""
    shard_id = int(batch["shard_id"][0])
    assert np.all(batch["shard_id"] == shard_id)
    order = np.argsort(batch["id"])
    flat_tokens, positions = [], []
    for i in order:
        tokens = json.loads(batch["tokens_json"][i])
        doc_id = int(batch["id"][i])
        flat_tokens.extend(tokens)
        positions.extend([[doc_id, p] for p in range(len(tokens))])
    samples = []
    for index, start in enumerate(range(0, len(flat_tokens), sequence_length)):
        tokens = flat_tokens[start:start + sequence_length]
        valid = len(tokens)
        samples.append({
            "sample_id": f"{shard_id}:{index}", "valid_length": valid,
            "input_ids": tokens + [0] * (sequence_length - valid),
            "source_positions": positions[start:start + sequence_length],
        })
    # 固定文件名、固定排序、固定内容；同一分片重试不会追加第二份记录。
    payload = ("\n".join(canonical(row) for row in samples) + "\n").encode("utf-8")
    path = Path(output_dir) / f"shard-{shard_id:03d}.jsonl"
    reused = path.exists()
    if reused:
        assert path.read_bytes() == payload, "已有分片内容不同，拒绝覆盖"
    else:
        temporary = path.with_suffix(f".{os.getpid()}.pending")
        temporary.write_bytes(payload)
        temporary.replace(path)  # 此处仅使用本机 POSIX 文件系统。
    marker = Path(output_dir) / "failure_after_commit.json"
    if inject_failure and shard_id == 1:
        try:
            fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as stream:
                json.dump({"pid": os.getpid(), "shard_id": shard_id,
                           "sha256": hashlib.sha256(payload).hexdigest()}, stream)
            print("故障注入：分片 1 已落盘，返回成功之前退出 Worker", flush=True)
            os._exit(23)
    traces = {}
    for instance, pid, call in zip(batch["tokenizer_instance"], batch["tokenizer_pid"],
                                   batch["tokenizer_call"]):
        trace = traces.setdefault(str(instance), {"pid": int(pid), "calls": []})
        trace["calls"].append(int(call))
        trace["calls"] = sorted(set(trace["calls"]))
    return {
        "shard_id": np.array([shard_id]), "file": np.array([path.name]),
        "sha256": np.array([hashlib.sha256(payload).hexdigest()]),
        "samples": np.array([len(samples)]), "tokens": np.array([len(flat_tokens)]),
        "reused": np.array([reused]), "writer_pid": np.array([os.getpid()]),
        "tokenizer_trace": np.array([canonical(traces)]),
    }


def reference_samples(documents, sequence_length):
    """串行参考：从已知清洗文本构造 (位置, token)，再按位置生成样本。"""
    result = {}
    for shard_id in range(SHARDS):
        stream = []
        for doc in sorted(documents, key=lambda d: d["id"]):
            if doc["id"] % SHARDS != shard_id:
                continue
            tokens = [byte + 2 for byte in doc["text"].encode("utf-8")] + [1]
            stream.extend(((doc["id"], i), token) for i, token in enumerate(tokens))
        rows = []
        for start in range(0, len(stream), sequence_length):
            chunk = stream[start:start + sequence_length]
            rows.append({
                "sample_id": f"{shard_id}:{start // sequence_length}",
                "valid_length": len(chunk),
                "input_ids": [v for _, v in chunk] + [0] * (sequence_length - len(chunk)),
                "source_positions": [list(pos) for pos, _ in chunk],
            })
        result[shard_id] = rows
    return result


def validate_output(receipts, expected, output_dir, sequence_length):
    assert len(receipts) == SHARDS
    assert {r["shard_id"] for r in receipts} == set(range(SHARDS))
    sample_ids, positions, manifest = [], [], []
    for receipt in sorted(receipts, key=lambda r: r["shard_id"]):
        data = (output_dir / receipt["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == receipt["sha256"]
        samples = [json.loads(line) for line in data.decode("utf-8").splitlines()]
        assert samples == expected[receipt["shard_id"]], "与串行参考不一致"
        assert len(samples) == receipt["samples"]
        assert sum(s["valid_length"] for s in samples) == receipt["tokens"]
        for sample in samples:
            valid = sample["valid_length"]
            assert len(sample["input_ids"]) == sequence_length
            assert len(sample["source_positions"]) == valid
            assert sample["input_ids"][valid:] == [0] * (sequence_length - valid)
            sample_ids.append(sample["sample_id"])
            positions.extend(tuple(p) for p in sample["source_positions"])
        manifest.append({k: receipt[k] for k in ("shard_id", "file", "sha256", "samples", "tokens")})
    expected_positions = [tuple(p) for rows in expected.values() for row in rows
                          for p in row["source_positions"]]
    assert len(sample_ids) == len(set(sample_ids)), "重复 sample_id"
    assert len(positions) == len(set(positions)), "重复源 token"
    assert Counter(positions) == Counter(expected_positions), "源 token 重复或遗漏"
    assert len(list(output_dir.glob("shard-*.jsonl"))) == SHARDS
    assert not list(output_dir.glob("*.pending"))
    return {"sequence_length": sequence_length, "shards": manifest,
            "samples": len(sample_ids), "tokens": len(positions)}


def experiment():
    sequence_length = int(os.environ.get("RAYLAB_LLM_SEQUENCE_LENGTH", "64"))
    if not 8 <= sequence_length <= 4096:
        raise ValueError("教学范围：SEQUENCE_LENGTH 为 8..4096")
    raw, clean_reference = fixture()
    input_dir, output_dir = RUN_DIR / "input", RUN_DIR / "shards"
    input_dir.mkdir()
    output_dir.mkdir()
    for i in range(8):
        (input_dir / f"part-{i:02d}.jsonl").write_text(
            "\n".join(canonical(r) for r in raw[i * 8:(i + 1) * 8]) + "\n")
    expected = reference_samples(clean_reference, sequence_length)
    with session():
        tokenized = ray.data.read_json(str(input_dir), override_num_blocks=8).map_batches(
            clean_batch, batch_size=4, batch_format="numpy", num_cpus=1,
        ).map_batches(
            ByteTokenizer, batch_size=4, batch_format="numpy", num_cpus=1,
            udf_modifying_row_count=False,
            compute=ray.data.ActorPoolStrategy(
                size=2, max_tasks_in_flight_per_actor=1, max_concurrent_calls_per_actor=1,
            ),
        ).materialize()
        # 小数据在此缓存，便于重放下游；这不是全流程无物化流水线。
        (RUN_DIR / "tokenize_stats.txt").write_text(tokenized.stats())
        token_rows = tokenized.take_all()  # 教学验收；生产不能把完整语料收回 Driver。
        assert sorted(r["id"] for r in token_rows) == [d["id"] for d in clean_reference]
        grouped = tokenized.groupby("shard_id", num_partitions=SHARDS)
        options = {"output_dir": str(output_dir), "sequence_length": sequence_length}
        first = grouped.map_groups(
            pack_and_write_group, batch_format="numpy", num_cpus=1,
            compute=ray.data.TaskPoolStrategy(size=2),
            max_retries=2, fn_kwargs={**options, "inject_failure": True},
        ).materialize()
        receipts = first.take_all()
        (RUN_DIR / "packing_stats.txt").write_text(first.stats())
        marker = json.loads((output_dir / "failure_after_commit.json").read_text())
        retried = next(r for r in receipts if r["shard_id"] == 1)
        assert retried["writer_pid"] != marker["pid"] and retried["reused"]
        assert retried["sha256"] == marker["sha256"]
        manifest = validate_output(receipts, expected, output_dir, sequence_length)
        temporary = output_dir / "manifest.pending"
        temporary.write_text(canonical(manifest) + "\n")
        temporary.replace(output_dir / "manifest.json")
        # 再执行一次下游；已有内容必须完全一致，不能 append 或生成重复分片。
        replay = grouped.map_groups(
            pack_and_write_group, batch_format="numpy", num_cpus=1,
            compute=ray.data.TaskPoolStrategy(size=2),
            max_retries=2, fn_kwargs={**options, "inject_failure": False},
        ).take_all()
        assert all(r["reused"] for r in replay)
        assert validate_output(replay, expected, output_dir, sequence_length) == manifest
        traces = {}
        for row in token_rows:
            trace = traces.setdefault(row["tokenizer_instance"],
                                      {"pid": row["tokenizer_pid"], "calls": []})
            trace["calls"] = sorted(set(trace["calls"] + [row["tokenizer_call"]]))
        assert 1 <= len(traces) <= 2 and any(len(t["calls"]) > 1 for t in traces.values())
        (RUN_DIR / "writer_receipts.json").write_text(json.dumps({
            "first_execution": receipts, "replay": replay, "failure": marker,
        }, ensure_ascii=False, indent=2))
        print(f"原始 {len(raw)} 篇 → 保留 {len(clean_reference)} 篇 → "
              f"{manifest['tokens']} token → {manifest['samples']} 样本；重放无重复/遗漏", flush=True)
        return {
            "scope": "真实 CPU Ray Data + 写入 Worker 异常退出及自动重试；教学字节分词器",
            "input_documents": len(raw), "kept_documents": len(clean_reference),
            "sequence_length": sequence_length, "samples": manifest["samples"],
            "tokens": manifest["tokens"], "tokenizer_instances": traces,
            "failed_writer_pid": marker["pid"], "retry_writer_pid": retried["writer_pid"],
            "replayed_shards": len(replay), "serial_reference_match": True,
            "no_duplicate_or_missing_source_tokens": True,
            "manifest": str(output_dir / "manifest.json"),
            "note": "按固定 shard_id 和文档 ID 排序，每分片尾部补 PAD，不丢余数；未做全局去重。"
                    "groupby 有数据交换且单组须能装入内存。只验证单机 Worker 失败；不是断电、跨节点或对象存储提交保证。",
        }


if __name__ == "__main__":
    run(experiment)
