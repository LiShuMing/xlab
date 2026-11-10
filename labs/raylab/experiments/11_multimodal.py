"""图像/音频/文本三种模态放在一起：列裁剪、按模态解码、以及为什么必须先窄化再 shuffle。

图像和音频都是本地用标准库（zlib/struct/wave）现场生成的真实编码，不依赖 PIL 或 torch。
解码也在 Worker 里用标准库完成，目的是让“多模态的代价在解码、不在搬运”可测量。
"""
import io
import json
import struct
import wave

import numpy as np
import ray
import ray.data

from common import RUN_DIR, run, session

IMAGE_SIDE = 24          # 24x24 RGB，够大能看出字节占比，够小不撑爆对象存储。
AUDIO_RATE = 8000
AUDIO_FRAMES = 400


def make_png(seed):
    """按最小 PNG 规范拼一个真 PNG：IHDR + IDAT(filter=0) + IEND。"""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(IMAGE_SIDE):
        pixels = rng.integers(0, 256, size=IMAGE_SIDE * 3, dtype=np.uint8)
        rows.append(b"\x00" + pixels.tobytes())
    idat = __import__("zlib").compress(b"".join(rows), 6)

    def chunk(tag, data):
        body = tag + data
        crc = __import__("zlib").crc32(body) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + body + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", IMAGE_SIDE, IMAGE_SIDE, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def make_wav(seed):
    """用标准库 wave 生成真 WAV：单声道 16 bit PCM。"""
    buffer = io.BytesIO()
    t = np.arange(AUDIO_FRAMES) / AUDIO_RATE
    freq = 200 + (seed % 5) * 50
    samples = (np.sin(2 * np.pi * freq * t) * 16000).astype("<i2")
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(AUDIO_RATE)
        handle.writeframes(samples.tobytes())
    return buffer.getvalue()


def decode_png(batch):
    """Worker 侧解码：读 IHDR 拿尺寸，解 IDAT 拿像素均值。"""
    widths, heights, means = [], [], []
    for payload in batch["image_png"]:
        data = bytes(payload)
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", data[16:24])
        cursor, idat = 8, b""
        while cursor < len(data):
            length = struct.unpack(">I", data[cursor: cursor + 4])[0]
            tag = data[cursor + 4: cursor + 8]
            body = data[cursor + 8: cursor + 8 + length]
            if tag == b"IDAT":
                idat += body
            cursor += 12 + length
        raw = np.frombuffer(__import__("zlib").decompress(idat), dtype=np.uint8)
        pixels = raw.reshape(height, 1 + width * 3)[:, 1:]
        widths.append(width)
        heights.append(height)
        means.append(int(pixels.mean()))
    n = len(widths)
    return {
        "doc_id": batch["doc_id"],
        "image_w": np.asarray(widths, dtype=np.int64),
        "image_h": np.asarray(heights, dtype=np.int64),
        "image_mean": np.asarray(means, dtype=np.int64),
        "image_bytes": np.asarray([len(bytes(p)) for p in batch["image_png"]]),
    }


def decode_wav(batch):
    """Worker 侧解码：用 wave 读帧数与采样率，算 RMS 音量。"""
    frames, rates, rms = [], [], []
    for payload in batch["audio_wav"]:
        with wave.open(io.BytesIO(bytes(payload)), "rb") as handle:
            rate = handle.getframerate()
            count = handle.getnframes()
            samples = np.frombuffer(handle.readframes(count), dtype="<i2")
        frames.append(count)
        rates.append(rate)
        rms.append(int(np.sqrt(np.mean(samples.astype(np.float64) ** 2))))
    return {
        "doc_id": batch["doc_id"],
        "audio_frames": np.asarray(frames, dtype=np.int64),
        "audio_rate": np.asarray(rates, dtype=np.int64),
        "audio_rms": np.asarray(rms, dtype=np.int64),
        "audio_bytes": np.asarray([len(bytes(p)) for p in batch["audio_wav"]]),
    }


def analyze_text(batch):
    return {
        "doc_id": batch["doc_id"],
        "text_len": np.asarray([len(str(t)) for t in batch["text"]], dtype=np.int64),
        "word_count": np.asarray([len(str(t).split()) for t in batch["text"]],
                                 dtype=np.int64),
    }


def build_rows(count):
    words = ["ray", "shuffle", "operator", "multimodal", "block", "batch"]
    rows = []
    for doc_id in range(count):
        rows.append({
            "doc_id": doc_id,
            "modality": ("image", "audio", "text")[doc_id % 3],
            "text": " ".join(words[doc_id % len(words):][:3] + [f"doc{doc_id}"]),
            "image_png": make_png(doc_id),
            "audio_wav": make_wav(doc_id),
        })
    return rows


def dataset_bytes(ds):
    return sum(bundle.size_bytes() for bundle in ds.iter_internal_ref_bundles())


def section_column_pruning(path):
    """列裁剪：只读文本时，图像和音频的字节根本没进内存。"""
    wide = ray.data.read_parquet(str(path))
    narrow = ray.data.read_parquet(str(path)).select_columns(["text"])
    wide_schema = [name for name in wide.schema().names]
    narrow_schema = [name for name in narrow.schema().names]
    wide_bytes = dataset_bytes(wide.materialize())
    narrow_bytes = dataset_bytes(narrow.materialize())
    assert narrow_schema == ["text"], narrow_schema
    assert len(wide_schema) == 5, wide_schema
    assert narrow_bytes * 5 < wide_bytes, (narrow_bytes, wide_bytes)
    return {
        "wide_columns": wide_schema,
        "narrow_columns": narrow_schema,
        "wide_bytes": wide_bytes,
        "narrow_bytes": narrow_bytes,
        "compression_x": round(wide_bytes / narrow_bytes, 1),
    }


def section_decode_by_modality(path, expected_rows):
    """三种模态各自解码，资源请求不同：图像重、音频中、文本轻。"""
    observations = {}

    images = ray.data.read_parquet(str(path)).select_columns(
        ["doc_id", "image_png"]
    ).map_batches(decode_png, batch_size=8, batch_format="numpy", num_cpus=1)
    image_rows = images.materialize().take_all()
    observations["image"] = {
        "rows": len(image_rows),
        "sides": sorted({(r["image_w"], r["image_h"]) for r in image_rows}),
        "avg_bytes": round(float(np.mean([r["image_bytes"] for r in image_rows])), 1),
    }
    assert len(image_rows) == expected_rows
    assert all(r["image_w"] == IMAGE_SIDE and r["image_h"] == IMAGE_SIDE
               for r in image_rows)

    audio = ray.data.read_parquet(str(path)).select_columns(
        ["doc_id", "audio_wav"]
    ).map_batches(decode_wav, batch_size=8, batch_format="numpy", num_cpus=1)
    audio_rows = audio.materialize().take_all()
    observations["audio"] = {
        "rows": len(audio_rows),
        "rates": sorted({r["audio_rate"] for r in audio_rows}),
        "frames": sorted({r["audio_frames"] for r in audio_rows}),
        "avg_bytes": round(float(np.mean([r["audio_bytes"] for r in audio_rows])), 1),
    }
    assert len(audio_rows) == expected_rows
    assert all(r["audio_frames"] == AUDIO_FRAMES for r in audio_rows)
    assert all(r["audio_rate"] == AUDIO_RATE for r in audio_rows)

    text = ray.data.read_parquet(str(path)).select_columns(
        ["doc_id", "text"]
    ).map_batches(analyze_text, batch_size=8, batch_format="numpy", num_cpus=0.25)
    text_rows = text.materialize().take_all()
    observations["text"] = {
        "rows": len(text_rows),
        "avg_words": round(float(np.mean([r["word_count"] for r in text_rows])), 2),
        "num_cpus": 0.25,
    }
    assert len(text_rows) == expected_rows
    # 视频/图像解码属于重算子，文本解析属于轻算子：CPU 请求本就该不同。
    assert observations["text"]["num_cpus"] < 1
    return observations


def section_narrow_then_shuffle(path):
    """反例与正例：把 bytes 列带进 shuffle，还是先窄化成特征再 shuffle。"""
    wide = ray.data.read_parquet(str(path)).materialize()
    wide_bytes = dataset_bytes(wide)

    # 先按模态解码出小特征，只保留 doc_id/模态/特征三列，再进 shuffle。
    def features(batch):
        return {
            "doc_id": batch["doc_id"],
            "modality": batch["modality"],
            "payload": np.asarray(
                [len(str(t).encode("utf-8")) for t in batch["text"]],
                dtype=np.int64,
            ),
        }

    narrow = ray.data.read_parquet(str(path)).select_columns(
        ["doc_id", "modality", "text"]
    ).map_batches(features, batch_size=8, batch_format="numpy").materialize()
    narrow_bytes = dataset_bytes(narrow)

    grouped_wide = wide.groupby("modality").count().materialize()
    grouped_narrow = narrow.groupby("modality").count().materialize()
    (RUN_DIR / "groupby_wide.txt").write_text(grouped_wide.stats())
    (RUN_DIR / "groupby_narrow.txt").write_text(grouped_narrow.stats())

    assert narrow_bytes * 5 < wide_bytes, (narrow_bytes, wide_bytes)
    assert grouped_wide.count() == grouped_narrow.count() == 3
    return {
        "wide_shuffle_input_bytes": wide_bytes,
        "narrow_shuffle_input_bytes": narrow_bytes,
        "ratio_x": round(wide_bytes / narrow_bytes, 1),
        "wide_block_count": wide.num_blocks(),
        "narrow_block_count": narrow.num_blocks(),
    }


def experiment():
    rows = build_rows(48)
    expected_rows = len(rows)
    table_bytes = sum(len(r["image_png"]) + len(r["audio_wav"]) for r in rows)
    root = RUN_DIR / "corpus"
    # 与 08 一致：目录已存在就失败，避免上一次运行的产物被静默追加成重复行。
    root.mkdir(parents=True)
    with session():
        ray.data.from_items(rows).write_parquet(str(root))
        pruning = section_column_pruning(root)
        decoded = section_decode_by_modality(root, expected_rows)
        narrowed = section_narrow_then_shuffle(root)
        print(json.dumps({
            "pruning": pruning, "decoded": decoded, "narrowed": narrowed,
        }, ensure_ascii=False, indent=2), flush=True)
        return {
            "scope": (
                "真实 PNG/WAV 编码与标准库解码，全程 CPU、无 PIL/torch/GPU；"
                "单机 4 CPU、对象存储 256 MiB。不是视觉模型推理基准。"
            ),
            "records": expected_rows,
            "media_bytes_total": table_bytes,
            "column_pruning": pruning,
            "per_modality": decoded,
            "narrow_before_shuffle": narrowed,
            "artifacts": str(root),
            "note": (
                "解码用的是最小 PNG 与 16bit PCM WAV，压缩率与真实图片差很远，"
                "所以 compression_x 只能说明列裁剪有效，不能当作真实多模态数据集的体积比。"
                "本轮没有测 GPU 解码，也没有测跨节点搬运。"
            ),
        }


if __name__ == "__main__":
    run(experiment)
