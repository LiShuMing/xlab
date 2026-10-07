"""Versioned, credential-free workspace archives; restore only into an empty workspace."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any

from sqlalchemy import text

from .storage import Store, now

MAX_ARCHIVE = 128 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
HASH = re.compile(r"^[0-9a-f]{64}$")


class BackupError(Exception):
    pass


def hashes(value: Any) -> set[str]:
    if isinstance(value, list):
        return set().union(*(hashes(v) for v in value))
    if isinstance(value, dict):
        found = {value["blob_hash"]} if isinstance(value.get("blob_hash"), str) else set()
        if any(not HASH.fullmatch(key) for key in found):
            raise BackupError("原件 hash 无效")
        return found.union(*(hashes(v) for v in value.values()))
    return set()


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def export_workspace(store: Store) -> bytes:
    # All API writes hold the shared workspace gate. This exclusive gate also
    # protects immutable blob reads from an application restore/maintenance run.
    with store.transaction(exclusive=True) as conn:
        conn.execute(text("LOCK TABLE pm_objects,pm_revisions,pm_idempotency IN SHARE MODE"))
        metadata = {
            "objects": [
                dict(row)
                for row in conn.execute(
                    text(
                        "SELECT id,kind,data,revision,created_at::text AS created_at,updated_at::text AS updated_at FROM pm_objects ORDER BY id"
                    )
                ).mappings()
            ],
            "revisions": [
                dict(row)
                for row in conn.execute(
                    text(
                        "SELECT object_id,revision,data,created_at::text AS created_at FROM pm_revisions ORDER BY object_id,revision"
                    )
                ).mappings()
            ],
            "idempotency": [
                dict(row)
                for row in conn.execute(
                    text("SELECT key,body_hash,result FROM pm_idempotency ORDER BY key")
                ).mappings()
            ],
        }
        files = {"metadata.json": encoded(metadata)}
        total = len(files["metadata.json"])
        for key in sorted(hashes(metadata)):
            path = store.data_dir / "blobs" / key[:2] / key
            if not path.is_file():
                raise BackupError(f"备份中止：缺失原件 {key}")
            total += path.stat().st_size
            if total > MAX_EXPANDED:
                raise BackupError("工作空间超过本版备份上限 256MiB")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != key:
                raise BackupError(f"备份中止：原件校验失败 {key}")
            files["blobs/" + key] = raw
        if total > MAX_EXPANDED:
            raise BackupError("工作空间超过本版备份上限 256MiB")
        if len(files) + 1 > 10_000:
            raise BackupError("工作空间超过本版备份文件数量上限")
        manifest = {
            "format": "panming-workspace",
            "schema_version": 3,
            "created_at": now(),
            "objects": len(metadata["objects"]),
            "revisions": len(metadata["revisions"]),
            "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
        }
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", encoded(manifest))
            for name, raw in files.items():
                archive.writestr(name, raw)
        if output.tell() > MAX_ARCHIVE:
            raise BackupError("备份包超过本版 128MiB 上限")
        return output.getvalue()


def workspace_integrity(store: Store) -> dict:
    """Read-only orphan/corruption inventory; never delete originals automatically."""
    with store.transaction(exclusive=True) as conn:
        metadata = [row.data for row in conn.execute(text("SELECT data FROM pm_revisions"))]
        referenced = hashes(metadata)
        missing = []
        corrupt = []
        for key in sorted(referenced):
            path = store.data_dir / "blobs" / key[:2] / key
            if not path.is_file():
                missing.append(key)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != key:
                corrupt.append(key)
        present = {
            p.name
            for p in (store.data_dir / "blobs").glob("*/*")
            if p.is_file() and HASH.fullmatch(p.name)
        }
        return {
            "ok": not missing and not corrupt,
            "referenced_blobs": len(referenced),
            "missing": missing,
            "corrupt": corrupt,
            "orphan_count": len(present - referenced),
            "mode": "read_only",
        }


def inspect_archive(raw: bytes) -> tuple[dict, dict[str, bytes]]:
    if len(raw) > MAX_ARCHIVE:
        raise BackupError("备份包超过 128MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if (
                len(names) > 10_000
                or len(names) != len(set(names))
                or sum(i.file_size for i in infos) > MAX_EXPANDED
            ):
                raise BackupError("备份重复条目或展开规模超限")
            if any(
                name not in {"manifest.json", "metadata.json"}
                and not re.fullmatch(r"blobs/[0-9a-f]{64}", name)
                for name in names
            ):
                raise BackupError("备份包含不安全路径或未知文件")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != "panming-workspace" or manifest.get(
                "schema_version"
            ) not in {1, 2, 3}:
                raise BackupError("不支持的备份版本")
            expected = manifest["files"]
            if (
                not isinstance(expected, dict)
                or set(expected) != set(names) - {"manifest.json"}
                or "metadata.json" not in expected
            ):
                raise BackupError("备份清单不完整")
            files = {name: archive.read(name) for name in expected}
            if any(
                hashlib.sha256(body).hexdigest() != expected[name] for name, body in files.items()
            ):
                raise BackupError("备份内容校验失败")
            metadata = json.loads(files.pop("metadata.json"))
            validate_metadata(metadata)
            if manifest.get("objects") != len(metadata["objects"]) or manifest.get(
                "revisions"
            ) != len(metadata["revisions"]):
                raise BackupError("备份数量与清单不一致")
            if set(files) != {"blobs/" + key for key in hashes(metadata)}:
                raise BackupError("原件集合与内容引用不一致")
            if any(
                hashlib.sha256(body).hexdigest() != name.split("/")[1]
                for name, body in files.items()
            ):
                raise BackupError("原件 hash 不匹配")
            return metadata, files
    except (
        zipfile.BadZipFile,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        AttributeError,
        RuntimeError,
        RecursionError,
        OverflowError,
        IndexError,
    ) as error:
        raise BackupError("无效或损坏的盘铭备份") from error


def validate_metadata(metadata: dict) -> None:
    if set(metadata) != {"objects", "revisions", "idempotency"} or any(
        not isinstance(v, list) for v in metadata.values()
    ):
        raise BackupError("元数据结构无效")
    heads = {item["id"]: item for item in metadata["objects"]}
    if len(metadata["objects"]) > 100_000 or len(metadata["revisions"]) > 100_000:
        raise BackupError("元数据规模超限")
    for item in metadata["objects"]:
        if (
            set(item) != {"id", "kind", "data", "revision", "created_at", "updated_at"}
            or not isinstance(item["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", item["id"])
        ):
            raise BackupError("对象行结构无效")
        datetime.fromisoformat(item["created_at"])
        datetime.fromisoformat(item["updated_at"])
    for item in metadata["revisions"]:
        if set(item) != {"object_id", "revision", "data", "created_at"}:
            raise BackupError("修订行结构无效")
        datetime.fromisoformat(item["created_at"])
    keys = set()
    for item in metadata["idempotency"]:
        if (
            set(item) != {"key", "body_hash", "result"}
            or not isinstance(item["key"], str)
            or len(item["key"]) > 250
            or item["key"] in keys
            or not HASH.fullmatch(item["body_hash"])
            or item["result"].get("id") not in heads
        ):
            raise BackupError("幂等记录无效")
        keys.add(item["key"])
    history = {
        (item["object_id"], item["revision"]): item["data"] for item in metadata["revisions"]
    }
    if len(heads) != len(metadata["objects"]) or len(history) != len(metadata["revisions"]):
        raise BackupError("对象或修订重复")
    revisions_by_id: dict[str, list[int]] = {}
    for oid, rev in history:
        revisions_by_id.setdefault(oid, []).append(rev)
    for oid, item in heads.items():
        if item["kind"] not in {
            "material",
            "report",
            "blog",
            "entry",
            "proposal",
            "source",
            "settings",
            "job",
            "digest",
        }:
            raise BackupError("未知对象类型")
        if (
            item["data"].get("id") != oid
            or item["data"].get("object_kind") != item["kind"]
            or not isinstance(item["revision"], int)
            or item["revision"] < 1
            or item["revision"] > 100_000
        ):
            raise BackupError("对象标识不一致")
        required = {
            "material": {
                "title": str,
                "content": str,
                "kind": str,
                "url": str,
                "topic": str,
                "reason": str,
                "fingerprint": str,
                "blob_hash": str,
                "parse_state": str,
                "digest": dict,
                "day": str,
                "feedback": str,
                "is_demo": bool,
            },
            "report": {
                "title": str,
                "day": str,
                "cutoff_at": str,
                "sources": list,
                "groups": list,
                "briefs": list,
                "coverage_state": str,
                "ready_count": int,
                "pending_count": int,
            },
            "blog": {
                "title": str,
                "body": str,
                "material_ids": list,
                "topic": str,
                "lifecycle": str,
                "is_demo": bool,
            },
            "entry": {
                "title": str,
                "body": str,
                "material_ids": list,
                "topic": str,
                "book": str,
                "blog_id": str,
                "due_day": str,
                "reviews": list,
                "is_demo": bool,
            },
            "proposal": {
                "title": str,
                "body": str,
                "material_ids": list,
                "topic": str,
                "blog_id": str,
                "blog_revision": int,
                "book": str,
                "status": str,
                "is_demo": bool,
            },
            "source": {"title": str, "url": str, "kind": str, "enabled": bool, "status": str},
            "settings": {"display_name": str, "report_time": str, "timezone": str},
            "job": {
                "state": str,
                "source_refs": list,
                "chunks": list,
                "provider": str,
                "signature": str,
                "fence": int,
                "attempts": int,
                "budget_day": str,
                "estimate_units": int,
                "reserved_units": int,
                "used_units": int,
                "usage_by_day": dict,
                "checkpoint": str,
            },
            "digest": {
                "source_refs": list,
                "chunks": list,
                "output": dict,
                "job_id": str,
                "job_fence": int,
                "provider": str,
                "mode": str,
            },
        }[item["kind"]]
        if any(
            not isinstance(item["data"].get(key), value_type)
            for key, value_type in required.items()
        ):
            raise BackupError("对象字段缺失或类型错误")
        if history.get((oid, item["revision"])) != item["data"]:
            raise BackupError("head 与修订记录不一致")
        revisions = sorted(revisions_by_id.get(oid, []))
        if revisions != list(range(1, item["revision"] + 1)):
            raise BackupError("修订历史不完整")
    for (oid, revision), data in history.items():
        if oid not in heads or data.get("id") != oid or data.get("revision") != revision:
            raise BackupError("修订标识不一致")

    def check(value: Any):
        if isinstance(value, str) and "\x00" in value:
            raise BackupError("元数据包含无效字符")
        if isinstance(value, list):
            for item in value:
                check(item)
        if isinstance(value, dict):
            if value.get("object_kind") == "material" and "blob_hash" in value:
                source = history.get((value.get("id"), value.get("revision")))
                if not source or source.get("blob_hash") != value["blob_hash"]:
                    raise BackupError("素材快照版本不一致")
            for mid in value.get("material_ids", []):
                if mid not in heads or heads[mid]["kind"] != "material":
                    raise BackupError("素材关系缺失")
            for key in ("blog_id", "report_id", "entry_id", "job_id", "digest_id"):
                if value.get(key) and value[key] not in heads:
                    raise BackupError("关联对象缺失")
            if "material_id" in value and "material_revision" in value:
                source = history.get((value["material_id"], value["material_revision"]))
                if not source or source.get("blob_hash") != value.get("blob_hash"):
                    raise BackupError("来源版本缺失或 hash 不一致")
            for item in value.values():
                check(item)

    check(metadata)
    # New pipeline state is validated against authoritative material revisions,
    # never against self-reported chunks. Legacy v1 archives have no pipeline rows.
    from .llm import CLOUD_MAX_INPUT, LLM_PROMPT_VERSION, valid_call, valid_profile
    from .pipeline import (
        CHUNK_VERSION,
        MAX_ATTEMPTS,
        MAX_INPUT,
        MAX_OUTPUT,
        PROMPT_VERSION,
        SCHEMA_VERSION,
        PipelineError,
        chunks_for,
        validate_output,
    )

    for (oid, revision), data in history.items():
        kind = heads[oid]["kind"]
        if kind not in {"job", "digest"}:
            continue
        refs = data["source_refs"]
        if not 1 <= len(refs) <= 12 or len({r["material_id"] for r in refs}) != len(refs):
            raise BackupError("任务素材范围无效")
        sources = [history[(r["material_id"], r["material_revision"])] for r in refs]
        expected_chunks = [c for source in sources for c in chunks_for(source)]
        # Source order can differ after canonical signature sorting.
        if sorted(data["chunks"], key=lambda c: c["chunk_id"]) != sorted(
            expected_chunks, key=lambda c: c["chunk_id"]
        ):
            raise BackupError("证据片段与素材版本不一致")
        cloud = data["provider"] == "openai_compatible"
        if (
            data["provider"] not in {"mock", "openai_compatible"}
            or data["prompt_version"] != (LLM_PROMPT_VERSION if cloud else PROMPT_VERSION)
            or data["schema_version"] != SCHEMA_VERSION
        ):
            raise BackupError("未知模型或证据协议")
        if cloud:
            profile = data.get("provider_profile")
            if not isinstance(profile, dict) or not valid_profile(profile):
                raise BackupError("模型服务元数据无效或包含未知字段")
            calls = data.get("call_attempts")
            if (
                not isinstance(calls, list)
                or len(calls) > 3
                or not all(valid_call(call) for call in calls)
                or len({c["id"] for c in calls}) != len(calls)
            ):
                raise BackupError("模型请求账本无效")
        if kind == "digest":
            if (
                data["mode"] != ("cloud_llm" if cloud else "offline_mock")
                or heads[data["job_id"]]["kind"] != "job"
            ):
                raise BackupError("消化任务关联无效")
            job_versions = [history[(data["job_id"], r)] for r in revisions_by_id[data["job_id"]]]
            if not any(
                j["fence"] == data["job_fence"]
                and j["state"] == "running"
                and j["source_refs"] == refs
                for j in job_versions
            ):
                raise BackupError("消化结果缺失有效租约来源")
            if cloud and (
                data.get("model") != profile["model"]
                or not any(
                    c["fence"] == data["job_fence"] and c["state"] != "in_flight" for c in calls
                )
            ):
                raise BackupError("模型结果缺少请求记录")
            try:
                validated = validate_output(data["output"], data["chunks"])
            except PipelineError as error:
                raise BackupError("备份含无效消化引用") from error
            chunk_sources = {c["chunk_id"]: c["material_id"] for c in data["chunks"]}
            covered = {
                chunk_sources[cite["chunk_id"]]
                for claim in validated["claims"]
                for cite in claim["citations"]
            }
            coverage = [
                {**ref, "status": "excerpted" if ref["material_id"] in covered else "no_excerpt"}
                for ref in refs
            ]
            if data.get("source_coverage") != coverage or data.get("coverage_state") != (
                "complete" if len(covered) == len(refs) else "partial"
            ):
                raise BackupError("消化覆盖状态不一致")
        else:
            datetime.fromisoformat(data["budget_day"])
            if (
                data["state"]
                not in {"queued", "running", "succeeded", "failed", "cancelled", "paused"}
                or data["chunk_version"] != CHUNK_VERSION
            ):
                raise BackupError("任务状态无效")
            if (
                not 0 <= data["attempts"] <= MAX_ATTEMPTS
                or data["fence"] < 0
                or not 0
                <= sum(len(s["content"]) for s in sources)
                <= (CLOUD_MAX_INPUT if cloud else MAX_INPUT)
                or data["estimate_units"] != sum(len(s["content"]) for s in sources) + MAX_OUTPUT
                or data["reserved_units"]
                != (data["estimate_units"] if data["state"] in {"queued", "running"} else 0)
                or any(type(v) is not int or v < 0 for v in data["usage_by_day"].values())
                or data["used_units"] != sum(data["usage_by_day"].values())
            ):
                raise BackupError("任务预算或尝试次数无效")
            for day in data["usage_by_day"]:
                datetime.fromisoformat(day)
            if data["state"] == "running":
                datetime.fromisoformat(data["lease_until"])
                if not data["lease_owner"]:
                    raise BackupError("任务租约无效")
            initial = history[(oid, 1)]
            if any(
                data[key] != initial[key]
                for key in ("source_refs", "chunks", "provider", "signature")
            ):
                raise BackupError("任务冻结输入已被修改")
            if cloud:
                if (
                    data.get("cloud_consent") is not True
                    or data.get("provider_profile") != initial.get("provider_profile")
                    or any(
                        s.get("processing_policy") != "cloud_allowed"
                        or s.get("cloud_allowed_profile") != profile["profile_id"]
                        for s in sources
                    )
                    or type(data.get("cloud_reserved_tokens")) is not int
                    or not 0 <= data["cloud_reserved_tokens"] <= 200_000
                    or (
                        data["state"] not in {"queued", "running"}
                        and data["cloud_reserved_tokens"] != 0
                    )
                    or any(call["fence"] > data["fence"] for call in calls)
                ):
                    raise BackupError("云端任务授权或预算无效")
                datetime.fromisoformat(data["consent_at"])
            if data["state"] == "succeeded":
                artifact = heads.get(data.get("digest_id"), {}).get("data", {})
                if (
                    artifact.get("object_kind") != "digest"
                    or artifact.get("job_id") != oid
                    or artifact.get("job_fence") != data["fence"]
                ):
                    raise BackupError("成功任务交付关联不一致")

    def check_embedded(value):
        if isinstance(value, dict):
            if (
                value.get("object_kind") == "digest"
                and history.get((value["id"], value["revision"])) != value
            ):
                raise BackupError("报告消化快照不一致")
            for item in value.values():
                check_embedded(item)
        elif isinstance(value, list):
            for item in value:
                check_embedded(item)

    check_embedded(metadata)


def restore_workspace(store: Store, raw: bytes) -> dict:
    metadata, files = inspect_archive(raw)  # No filesystem/DB writes before full validation.
    with store.transaction(exclusive=True) as conn:
        conn.execute(text("LOCK TABLE pm_objects,pm_revisions,pm_idempotency IN EXCLUSIVE MODE"))
        if any(
            conn.execute(text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar()
            for table in ("pm_objects", "pm_revisions", "pm_idempotency")
        ):
            raise BackupError("恢复只允许空工作空间；不会覆盖已有内容")
        for name, body in files.items():
            key = name.split("/")[1]
            dest = store.data_dir / "blobs" / key[:2] / key
            if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() != key:
                raise BackupError("目标目录已有损坏原件，拒绝覆盖")
            store.put_blob(body)
        for item in metadata["objects"]:
            conn.execute(
                text(
                    "INSERT INTO pm_objects(id,kind,data,revision,created_at,updated_at) VALUES(:id,:kind,CAST(:data AS jsonb),:revision,CAST(:created_at AS timestamptz),CAST(:updated_at AS timestamptz))"
                ),
                {**item, "data": json.dumps(item["data"], ensure_ascii=False)},
            )
        for item in metadata["revisions"]:
            conn.execute(
                text(
                    "INSERT INTO pm_revisions(object_id,revision,data,created_at) VALUES(:object_id,:revision,CAST(:data AS jsonb),CAST(:created_at AS timestamptz))"
                ),
                {**item, "data": json.dumps(item["data"], ensure_ascii=False)},
            )
        for item in metadata["idempotency"]:
            conn.execute(
                text(
                    "INSERT INTO pm_idempotency(key,body_hash,result) VALUES(:key,:body_hash,CAST(:result AS jsonb))"
                ),
                {**item, "result": json.dumps(item["result"], ensure_ascii=False)},
            )
        paused_jobs = 0
        for job in store.list(conn, "job"):
            has_pending_call = any(c["state"] == "in_flight" for c in job.get("call_attempts", []))
            if job["state"] in {"queued", "running"} or has_pending_call:
                from .llm import abandon_calls

                store.update(
                    conn,
                    {
                        **job,
                        "state": "paused"
                        if job["state"] in {"queued", "running"}
                        else job["state"],
                        "checkpoint": "restored_paused"
                        if job["state"] in {"queued", "running"}
                        else "restored_usage_uncertain",
                        "fence": job["fence"] + 1,
                        "reserved_units": 0,
                        "cloud_reserved_tokens": 0,
                        "call_attempts": abandon_calls(job),
                        "lease_owner": None,
                        "lease_until": None,
                    },
                    job["revision"],
                )
                if job["state"] in {"queued", "running"}:
                    paused_jobs += 1
    return {
        "restored": True,
        "objects": len(metadata["objects"]),
        "revisions": len(metadata["revisions"]),
        "blobs": len(files),
        "paused_jobs": paused_jobs,
    }
