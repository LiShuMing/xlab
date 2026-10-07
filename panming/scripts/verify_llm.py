"""One real LLM call on a fixed synthetic sample, in a disposable workspace.

This opt-in script loads the configured service and consumes its API allowance.
It never reads the owner's material objects; generated evidence stays under data/.
Use --serve to inspect the result at the isolated developer UI on port 5178.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panming.app import create_app, source_ref, today  # noqa: E402
from panming.backup import export_workspace, inspect_archive  # noqa: E402
from panming.storage import ROOT, Store, database_url  # noqa: E402

SAMPLE = """# Grace Hash Join 与 Spill：合成学习素材

Build 与 Probe 使用相同的分区函数，使相同连接键落到同一个分区。

内存不足时，将分区中的逻辑行写入临时文件；恢复该分区时重新建立局部哈希表。

一个热点键无法靠增加哈希位拆开。需要通过实验观察倾斜分区的大小与恢复内存。

临时文件生命周期、记录编码和顺序读写可以作为公共 Spill I/O；分区策略和状态恢复留给各算子。

下一步实验：分别生成 Aggregate 分区与 Sort run，检查同一套 Reader 是否够用。
"""


def checked(response):
    if response.status_code >= 400:
        # API diagnostics contain only controlled codes/messages, not credentials.
        raise RuntimeError(f"VERIFICATION_API_STATUS_{response.status_code}")
    return response.json()


def save_artifact(path: Path, body: bytes):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(body)
        out.flush()
        os.fsync(out.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    suffix = uuid.uuid4().hex
    schema = "panming_llm_verify_" + suffix
    admin = create_engine(database_url())
    store = None
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        with tempfile.TemporaryDirectory(prefix="llm-verify-", dir=ROOT / "data") as temporary:
            store = Store(database_url(), Path(temporary), {"options": f"-csearch_path={schema}"})
            with TestClient(create_app(store, enable_llm=True, start_worker=False)) as client:
                pipeline = client.app.state.pipeline
                provider = pipeline.providers.get("openai_compatible")
                if provider is None:
                    raise RuntimeError(client.app.state.llm_config_error or "LLM_NOT_CONFIGURED")
                profile = provider.profile()
                source = checked(
                    client.post(
                        "/api/v1/captures",
                        json={
                            "title": "真实 API 验收 · Join / Spill 合成素材",
                            "content": SAMPLE,
                            "kind": "markdown",
                            "topic": "database",
                        },
                    )
                )
                source = checked(
                    client.patch(
                        f"/api/v1/materials/{source['id']}/policy",
                        json={
                            "revision": source["revision"],
                            "processing_policy": "cloud_allowed",
                            "provider_profile": profile["profile_id"],
                        },
                    )
                )
                old_report = checked(client.post("/api/v1/reports/runs", json={"date": today()}))
                job = checked(
                    client.post(
                        "/api/v1/digest/jobs",
                        json={
                            "source_refs": [source_ref(source)],
                            "provider": "openai_compatible",
                            "cloud_consent": True,
                            "provider_profile": profile["profile_id"],
                        },
                    )
                )
                print("已冻结合成素材，正在调用已配置的 LLM API……", flush=True)
                pipeline.run_once("real-api-verification")
                result = checked(client.get("/api/v1/processing"))
                current = next(j for j in result["jobs"] if j["id"] == job["id"])
                if current["state"] != "succeeded":
                    raise RuntimeError(current["error_code"] or "LLM_VERIFICATION_FAILED")
                digest = next(d for d in result["digests"] if d["id"] == current["digest_id"])
                frozen_report = checked(
                    client.get(f"/api/v1/objects/{old_report['id']}?revision=1")
                )
                if frozen_report != old_report:
                    raise RuntimeError("OLD_REPORT_CHANGED")
                report = checked(client.post("/api/v1/reports/runs", json={"date": today()}))
                if (
                    report["generation_mode"] != "llm_evidence"
                    or len(report["evidence_digests"]) != 1
                ):
                    raise RuntimeError("REPORT_EVIDENCE_MISSING")
                archive = export_workspace(store)
                inspect_archive(archive)
                summary = {
                    "verified": True,
                    "provider": "openai_compatible",
                    "claims": len(digest["output"]["claims"]),
                    "citations": sum(len(c["citations"]) for c in digest["output"]["claims"]),
                    "usage": current["call_attempts"][-1]["usage"],
                    "old_report_unchanged": True,
                    "new_report_revision": report["revision"],
                }
                folder = ROOT / "data" / "v041-verification" / suffix
                folder.mkdir(parents=True, mode=0o700)
                save_artifact(folder / "workspace.zip", archive)
                save_artifact(
                    folder / "summary.json",
                    json.dumps(summary, ensure_ascii=False, indent=2).encode(),
                )
                exported = client.get(f"/api/v1/export/{digest['id']}?revision=1&format=markdown")
                if exported.status_code != 200:
                    raise RuntimeError("DIGEST_EXPORT_FAILED")
                save_artifact(folder / "evidence.md", exported.content)
                print(
                    json.dumps({**summary, "artifacts": str(folder)}, ensure_ascii=False),
                    flush=True,
                )
            if args.serve:
                print("隔离验收结果：http://127.0.0.1:5178/#/jobs", flush=True)
                uvicorn.run(
                    create_app(store, enable_llm=True, start_worker=False),
                    host="127.0.0.1",
                    port=5178,
                    log_level="warning",
                )
    finally:
        if store:
            store.engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
        print("已清理隔离 schema 与临时原件；验收导出保留在 data/。", flush=True)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
