"""Single-owner loopback prototype. All actions commit to PostgreSQL."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .backup import (
    MAX_ARCHIVE,
    BackupError,
    export_workspace,
    restore_workspace,
    workspace_integrity,
)
from .content import TOPICS, blog_body, classify, digest
from .llm import LLMConfigError, OpenAICompatibleProvider, load_config
from .pipeline import (
    MockProvider,
    Pipeline,
    PipelineError,
    Worker,
    evidence_markdown,
    job_view,
    lock_jobs,
)
from .storage import ROOT, RevisionConflict, Store, now, object_id

KINDS = ("material", "report", "blog", "entry", "proposal", "source")


class InputModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def no_nul(cls, value: Any) -> Any:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("文字不能包含 NUL 字符")
        return value

    @field_validator("title", "display_name", mode="before", check_fields=False)
    @classmethod
    def trim_title(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class Capture(InputModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=500_000)
    kind: Literal["user_note", "markdown", "ai_conversation", "web_page", "video_reference"] = (
        "user_note"
    )
    topic: str = ""
    url: str = Field(default="", max_length=2000)
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def meaningful_input(self):
        if (
            self.kind in {"user_note", "ai_conversation"}
            and not self.content.strip()
            and not self.url
        ):
            raise ValueError("笔记和对话需要正文")
        return self


class ReportRequest(InputModel):
    date: date
    include_carryover: bool = True


class SourceRef(InputModel):
    material_id: str = Field(min_length=1, max_length=100)
    material_revision: int = Field(ge=1)
    blob_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DigestRequest(InputModel):
    source_refs: list[SourceRef] = Field(min_length=1, max_length=12)
    provider: Literal["mock", "openai_compatible"] = "mock"
    cloud_consent: bool = False
    provider_profile: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class CloudConfirmation(InputModel):
    cloud_consent: bool = False
    provider_profile: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class PolicyRequest(InputModel):
    revision: int = Field(ge=1)
    processing_policy: Literal["local_only", "cloud_allowed"]
    provider_profile: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


def source_ref(material: dict) -> dict:
    return {
        "material_id": material["id"],
        "material_revision": material["revision"],
        "blob_hash": material["blob_hash"],
    }


class BlogRequest(InputModel):
    title: str = Field(min_length=1, max_length=200)
    material_ids: list[str] = Field(default_factory=list, max_length=100)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=100)
    report_id: str | None = None
    report_revision: int | None = Field(default=None, ge=1)

    @field_validator("material_ids")
    @classmethod
    def valid_ids(cls, value: list[str]) -> list[str]:
        if any(not mid.strip() or len(mid) > 100 or "\x00" in mid for mid in value):
            raise ValueError("素材 ID 格式无效")
        return value

    @model_validator(mode="after")
    def require_sources(self):
        if not self.material_ids and not self.source_refs:
            raise ValueError("请选择素材")
        if (
            self.source_refs
            and self.material_ids
            and self.material_ids != [r.material_id for r in self.source_refs]
        ):
            raise ValueError("素材 ID 与版本引用不一致")
        if self.report_revision and not self.report_id:
            raise ValueError("指定报告版本需要 report_id")
        return self


class RevisionRequest(InputModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(max_length=500_000)
    revision: int = Field(ge=1)


class Feedback(InputModel):
    value: Literal["unread", "useful", "known", "later"]


class Review(InputModel):
    grade: Literal["clear", "fuzzy", "forgot"]


class SourceRequest(InputModel):
    title: str = Field(min_length=1, max_length=150)
    url: str = Field(min_length=1, max_length=2000)
    kind: Literal["rss", "github", "website"] = "website"


class SettingsRequest(InputModel):
    display_name: str = Field(min_length=1, max_length=80)
    report_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class AcceptRequest(InputModel):
    revision: int = Field(ge=1)


class ProposalRequest(InputModel):
    blog_id: str = Field(min_length=1, max_length=100)


def today() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


def checked_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise HTTPException(422, "链接格式无效") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or any(char.isspace() or ord(char) < 32 for char in url)
        or (port is not None and not 0 < port < 65536)
    ):
        raise HTTPException(422, "请输入不包含凭据的 HTTP(S) 链接")
    return url


def require_revision(
    store: Store, conn: Any, oid: str, revision: int | None = None, kind: str = ""
) -> dict:
    head = require(store, conn, oid, kind)
    if revision is None or revision == head["revision"]:
        return head
    frozen = store.get_revision(conn, oid, revision)
    if not frozen:
        raise HTTPException(404, "内容版本不存在")
    return frozen


def require(store: Store, conn: Any, oid: str, kind: str = "", lock: bool = False) -> dict:
    item = store.get(conn, oid, lock)
    if not item or (kind and item.get("object_kind") != kind):
        raise HTTPException(404, "内容不存在")
    return item


def record(object_kind: str, **values: Any) -> dict:
    return {"id": object_id(object_kind), "object_kind": object_kind, "created_at": now(), **values}


def settings(store: Store, conn: Any) -> dict:
    return store.get(conn, "settings") or {
        "display_name": "我的工作空间",
        "report_time": "21:30",
        "timezone": "Asia/Shanghai",
    }


def capture_material(
    store: Store, conn: Any, body: Capture, raw: bytes | None = None, demo: bool = False
) -> dict:
    checked_url(body.url)
    topic = body.topic or classify(body.title + " " + body.content)
    if topic not in {t["id"] for t in TOPICS}:
        raise HTTPException(422, "主题不存在")
    store.lock_inputs(conn)
    original = raw if raw is not None else (body.content or body.url).encode()
    fingerprint = hashlib.sha256(
        (body.kind + "\0" + body.title + "\0" + body.url).encode() + original
    ).hexdigest()
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": fingerprint})
    item = store.fingerprint(conn, fingerprint)
    if item:
        return {**item, "duplicate": True}
    blob_hash = store.put_blob(original)
    state = "ready" if body.content.strip() else "needs_input"
    material = record(
        "material",
        title=body.title,
        content=body.content,
        kind=body.kind,
        url=body.url,
        topic=topic,
        reason=body.reason,
        fingerprint=fingerprint,
        blob_hash=blob_hash,
        parse_state=state,
        digest=digest(body.content),
        day=today(),
        feedback="unread",
        is_demo=demo,
        sensitivity="private",
        processing_policy="local_only",
    )
    return store.insert(conn, "material", material)


def build_report(store: Store, conn: Any, request: ReportRequest) -> dict:
    day = request.date.isoformat()
    if day > today():
        raise HTTPException(422, "不能为未来日期生成报告")
    store.lock_inputs(conn)
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "report:" + day})
    lock_jobs(conn)  # Freeze completed evidence deliveries before measuring cutoff.
    cutoff = now()
    materials = store.list(conn, "material")
    reports = store.list(conn, "report")
    previous = next((r for r in reports if r["day"] == day), None)
    covered_before = {
        (s["id"], s["blob_hash"])
        for r in reports
        if r["day"] < day
        for s in r["sources"]
        if s["parse_state"] == "ready"
    }
    selected = [
        m
        for m in materials
        if m["day"] == day
        or (
            request.include_carryover
            and m["day"] < day
            and (m["id"], m["blob_hash"]) not in covered_before
        )
    ]
    ready = [m for m in selected if m["parse_state"] == "ready"]
    sources = [
        {**m, "inclusion_reason": "today" if m["day"] == day else "carryover"} for m in selected
    ]
    groups = [
        {
            "topic": t["id"],
            "name": t["name"],
            "materials": [m["id"] for m in ready if m["topic"] == t["id"]],
        }
        for t in TOPICS
    ]
    briefs = [
        {
            "title": f"从材料到理解：{t['name']}"
            + (f" · 第 {start // 30 + 1} 组" if len(group["materials"]) > 30 else ""),
            "topic": t["id"],
            "material_ids": group["materials"][start : start + 30],
            "question": "这些线索如何连接起来，哪些结论还需要验证？",
        }
        for t, group in zip(TOPICS, groups)
        for start in range(0, len(group["materials"]), 30)
    ]
    manifest_keys = {(m["id"], m["revision"], m["blob_hash"]) for m in sources}
    evidence_digests = [
        d
        for d in store.list(conn, "digest")
        if d["created_at"] <= cutoff
        and all(
            (r["material_id"], r["material_revision"], r["blob_hash"]) in manifest_keys
            for r in d["source_refs"]
        )
    ]
    values = {
        "title": f"{day} · 每日 Report",
        "day": day,
        "cutoff_at": cutoff,
        "manifest": [source_ref(m) for m in sources],
        "snapshot_protocol": "input_and_delivery_commit_barrier_v2",
        "timezone": "Asia/Shanghai",
        "sources": sources,
        "groups": groups,
        "briefs": briefs,
        "coverage_state": "no_updates"
        if not selected
        else "complete"
        if len(ready) == len(selected)
        else "partial",
        "ready_count": len(ready),
        "pending_count": len(selected) - len(ready),
        "generation_mode": "llm_evidence"
        if any(d["mode"] == "cloud_llm" for d in evidence_digests)
        else "mock_evidence"
        if evidence_digests
        else "extractive",
        "evidence_digests": evidence_digests,
        "is_demo": bool(selected) and all(m["is_demo"] for m in selected),
    }
    if previous:
        return store.update(conn, {**previous, **values}, previous["revision"])
    return store.insert(conn, "report", record("report", **values))


def seed_demo(store: Store) -> dict:
    with store.transaction() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('panming-demo'))"))
        if any(m.get("is_demo") for m in store.list(conn, "material")):
            return {"seeded": False}
        samples = [
            (
                "Grace Hash Join：先分区，再恢复",
                "database",
                "markdown",
                "# Grace Hash Join 学习摘记\n\nBuild 与 Probe 使用相同的哈希函数和分区规则，使相同键在同一个分区相遇。\n\n落盘的是能够重建哈希表的逻辑行；恢复一个分区后，再建立局部哈希表。\n\n一个热点键无法被更多哈希位拆开，继续递归并不能解决所有倾斜。",
            ),
            (
                "从 Join 到 Aggregate：复用 Spill I/O",
                "database",
                "user_note",
                "今天想继续梳理外存算子的公共部分。临时文件的生命周期、记录编解码和顺序 I/O 可以复用；分区策略和状态恢复应留给各算子。\n\n下一步实验：分别写一个聚合分区和一个排序 run，检查同一个 Reader 是否够用。",
            ),
            (
                "AI 对话里的结论，如何留下证据？",
                "ai",
                "ai_conversation",
                "用户：如何避免把模型推断写成事实？\n\n助手：可以分开保存来源陈述、模型推断和个人观察，并为每条引用绑定原始段落。\n\n用户：这是待验证的设计建议。我需要尝试一组带冲突的输入，再观察归纳是否遗漏。",
            ),
            (
                "知识消化的四层：从输入到图书馆",
                "thinking",
                "markdown",
                "# 每日知识工作流\n\n原始素材先保留出处，再整理为可引用的知识卡。围绕具体问题写成博客，最后通过复习和修订编入自己的图书馆。\n\n归纳不能代替个人判断；能用自己的例子解释一个概念，才算向前推进。",
            ),
            (
                "让一篇博客从一个好问题开始",
                "thinking",
                "user_note",
                "先写中心问题，再列出已有证据、自己的看法和未知之处。\n\n与其强迫每天产出文章，不如让一份日报告诉我，今天哪个问题值得继续。",
            ),
        ]
        captured = [
            capture_material(
                store,
                conn,
                Capture(
                    title=title,
                    topic=topic,
                    kind=kind,
                    content=body,
                    reason="内置体验资料，可用自己的素材替换",
                ),
                demo=True,
            )
            for title, topic, kind, body in samples
        ]
        report = build_report(store, conn, ReportRequest(date=date.fromisoformat(today())))
        blog = store.insert(
            conn,
            "blog",
            record(
                "blog",
                title="把外存算法的逻辑，写成自己的理解",
                body=blog_body("把外存算法的逻辑，写成自己的理解", captured[:2]),
                material_ids=[m["id"] for m in captured[:2]],
                source_snapshots=captured[:2],
                source_refs=[source_ref(m) for m in captured[:2]],
                topic="database",
                lifecycle="draft",
                is_demo=True,
                report_id=report["id"],
            ),
        )
        store.insert(
            conn,
            "entry",
            record(
                "entry",
                title="Grace Hash Join 的分区不变量",
                body="# Grace Hash Join 的分区不变量\n\n这是一份内置体验条目。\n\nBuild 与 Probe 需要遵循相同的分区规则。恢复分区时，用逻辑行重建局部哈希表。\n\n## 复习问题\n\n为什么修改一侧的分区规则可能漏掉匹配？\n\n更多分区为什么不能拆开同一个热点键？",
                topic="database",
                book="数据库执行引擎",
                material_ids=[captured[0]["id"]],
                source_snapshots=captured[:1],
                source_refs=[source_ref(captured[0])],
                blog_id=blog["id"],
                is_demo=True,
                due_day=today(),
                reviews=[],
            ),
        )
        return {"seeded": True}


def create_app(
    store_override: Store | None = None,
    *,
    start_worker: bool | None = None,
    enable_llm: bool | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = store_override or Store()
        providers = {"mock": MockProvider()}
        app.state.llm_config_error = None
        if enable_llm if enable_llm is not None else store_override is None:
            try:
                config = load_config()
                if config:
                    providers["openai_compatible"] = OpenAICompatibleProvider(config)
            except LLMConfigError as error:
                app.state.llm_config_error = str(error)
        app.state.pipeline = Pipeline(app.state.store, providers=providers)
        worker = (
            Worker(app.state.pipeline)
            if (start_worker if start_worker is not None else store_override is None)
            else None
        )
        if worker:
            worker.start()
        try:
            yield
        finally:
            if worker:
                from starlette.concurrency import run_in_threadpool

                await run_in_threadpool(worker.stop)
            if not store_override:
                app.state.store.engine.dispose()

    app = FastAPI(title="盘铭 · Panming", version="0.4.1", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def loopback_guard(request: Request, call_next: Any):
        if request.url.path.startswith("/api/"):
            if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
                return JSONResponse({"detail": "原型只允许本机访问"}, status_code=403)
            origin = request.headers.get("origin")
            if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
                try:
                    parsed = urlsplit(origin)
                    allowed = (
                        parsed.scheme in {"http", "https"}
                        and parsed.hostname in {"127.0.0.1", "localhost"}
                        and parsed.port in {8788, 5178}
                        and not parsed.username
                        and not parsed.password
                    )
                except ValueError:
                    allowed = False
                if not allowed:
                    return JSONResponse({"detail": "拒绝跨站写入"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(RevisionConflict)
    async def value_error(request: Request, error: RevisionConflict):
        return JSONResponse(
            {"code": "REVISION_CONFLICT", "detail": "内容版本已变化，请比较服务器版本后保存"},
            status_code=409,
        )

    @app.exception_handler(BackupError)
    async def backup_error(request: Request, error: BackupError):
        return JSONResponse({"code": "BACKUP_INVALID", "detail": str(error)}, status_code=422)

    @app.exception_handler(PipelineError)
    async def pipeline_error(request: Request, error: PipelineError):
        return JSONResponse({"code": error.code, "detail": error.detail}, status_code=error.status)

    def db(request: Request) -> Store:
        return request.app.state.store

    @app.get("/api/v1/health")
    def health(request: Request):
        with db(request).transaction() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "storage": "postgresql",
            "mode": "local-prototype",
            "version": "0.4.1",
        }

    def processing_state(request: Request, conn: Any) -> dict:
        pipeline = request.app.state.pipeline
        pipeline.lock(conn)
        return {
            "jobs": [job_view(j) for j in pipeline.store.list(conn, "job")],
            "digests": pipeline.store.list(conn, "digest"),
            "processing": {
                "provider": "mock",
                "external_calls_enabled": "openai_compatible" in pipeline.providers,
                "profiles": pipeline.profiles(),
                "config_error": request.app.state.llm_config_error,
                "budget": pipeline.budget(conn),
            },
        }

    @app.get("/api/v1/processing")
    def processing(request: Request):
        with db(request).transaction() as conn:
            return processing_state(request, conn)

    @app.post("/api/v1/digest/jobs", status_code=202)
    def digest_job(request: Request, payload: DigestRequest):
        return request.app.state.pipeline.submit(
            [ref.model_dump() for ref in payload.source_refs],
            payload.provider,
            cloud_consent=payload.cloud_consent,
            provider_profile=payload.provider_profile,
        )

    @app.post("/api/v1/jobs/{jid}/cancel")
    def cancel_job(request: Request, jid: str):
        return request.app.state.pipeline.action(jid, "cancel")

    @app.post("/api/v1/jobs/{jid}/retry")
    def retry_job(request: Request, jid: str, payload: CloudConfirmation):
        return request.app.state.pipeline.action(jid, "retry", **payload.model_dump())

    @app.get("/api/v1/bootstrap")
    def bootstrap(request: Request):
        store = db(request)
        with store.transaction() as conn:
            return {
                "today": today(),
                "topics": TOPICS,
                "settings": settings(store, conn),
                "materials": store.list(conn, "material"),
                "reports": store.list(conn, "report"),
                "blogs": store.list(conn, "blog"),
                "entries": store.list(conn, "entry"),
                "sources": store.list(conn, "source"),
                "proposals": store.list(conn, "proposal"),
                "generation_mode": "extractive",
                **processing_state(request, conn),
            }

    @app.post("/api/v1/demo")
    def demo(request: Request):
        return seed_demo(db(request))

    @app.post("/api/v1/captures")
    def capture(
        request: Request, payload: Capture, idempotency_key: str | None = Header(default=None)
    ):
        store = db(request)
        with store.transaction() as conn:
            body_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
            if idempotency_key:
                if len(idempotency_key) > 200:
                    raise HTTPException(422, "请求标识最多 200 字符")
                key = "capture:" + idempotency_key
                conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})
                old = conn.execute(
                    text("SELECT body_hash,result FROM pm_idempotency WHERE key=:key"), {"key": key}
                ).first()
                if old:
                    if old.body_hash != body_hash:
                        raise HTTPException(409, "相同请求标识不能用于不同内容")
                    return old.result
            result = capture_material(store, conn, payload)
            if idempotency_key:
                conn.execute(
                    text(
                        "INSERT INTO pm_idempotency(key,body_hash,result) VALUES(:key,:hash,CAST(:result AS jsonb))"
                    ),
                    {
                        "key": key,
                        "hash": body_hash,
                        "result": json.dumps(result, ensure_ascii=False),
                    },
                )
            return result

    @app.post("/api/v1/captures/files")
    async def upload(request: Request, file: UploadFile = File(...)):
        raw = await file.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(413, "本版单文件上限为 8 MiB")
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = ""
        if len(content) > 500_000:
            content = ""
        if "\x00" in content:
            content = ""  # Preserve these bytes as an unparseable original, not JSONB text.
        payload = Capture(
            title=(file.filename or "").strip().replace("\x00", "")[:200] or "未命名素材",
            content=content,
            kind="markdown",
        )
        store = db(request)
        with store.transaction() as conn:
            result = capture_material(store, conn, payload, raw)
            if not content and not result.get("duplicate"):
                result = store.update(
                    conn, {**result, "parse_state": "stored_only"}, result["revision"]
                )
            return result

    @app.post("/api/v1/materials/{oid}/feedback")
    def feedback(request: Request, oid: str, payload: Feedback):
        store = db(request)
        with store.transaction() as conn:
            store.lock_inputs(conn)
            material = require(store, conn, oid, "material", True)
            return store.update(conn, {**material, "feedback": payload.value}, material["revision"])

    @app.post("/api/v1/materials/{oid}/revisions")
    def material_revision(request: Request, oid: str, payload: RevisionRequest):
        store = db(request)
        with store.transaction() as conn:
            store.lock_inputs(conn)
            material = require(store, conn, oid, "material", True)
            if not payload.body.strip():
                raise HTTPException(422, "请补充正文")
            if payload.revision != material["revision"]:
                raise HTTPException(409, "素材版本已变化，请刷新")
            blob_hash = store.put_blob(payload.body.encode())
            request.app.state.pipeline.cancel_cloud_jobs(conn, oid)
            return store.update(
                conn,
                {
                    **material,
                    "title": payload.title,
                    "content": payload.body,
                    "blob_hash": blob_hash,
                    "parse_state": "ready",
                    "digest": digest(payload.body),
                    "processing_policy": "local_only",
                    "cloud_allowed_profile": None,
                    "fingerprint": hashlib.sha256(
                        (material["kind"] + "\0" + payload.title + "\0" + material["url"]).encode()
                        + payload.body.encode()
                    ).hexdigest(),
                },
                payload.revision,
            )

    @app.patch("/api/v1/materials/{oid}/policy")
    def material_policy(request: Request, oid: str, payload: PolicyRequest):
        store = db(request)
        pipeline = request.app.state.pipeline
        with store.transaction() as conn:
            store.lock_inputs(conn)
            material = require(store, conn, oid, "material", True)
            if payload.revision != material["revision"]:
                raise RevisionConflict("REVISION_CONFLICT")
            profile_id = None
            if payload.processing_policy == "cloud_allowed":
                provider = pipeline.providers.get("openai_compatible")
                if not provider:
                    raise PipelineError("PROVIDER_DISABLED", "先配置并启用模型服务")
                profile_id = provider.profile()["profile_id"]
                if payload.provider_profile != profile_id:
                    raise PipelineError(
                        "LLM_PROFILE_CHANGED", "模型/服务配置已变化，请刷新后确认", 409
                    )
            else:
                pipeline.cancel_cloud_jobs(conn, oid)
            if (
                material.get("processing_policy", "local_only") == payload.processing_policy
                and material.get("cloud_allowed_profile") == profile_id
            ):
                return material
            return store.update(
                conn,
                {
                    **material,
                    "processing_policy": payload.processing_policy,
                    "cloud_allowed_profile": profile_id,
                    "policy_changed_at": now(),
                },
                payload.revision,
            )

    @app.get("/api/v1/materials/{oid}/original")
    def original(request: Request, oid: str, revision: int | None = None):
        store = db(request)
        with store.transaction() as conn:
            material = require_revision(store, conn, oid, revision, "material")
        digest_key = material["blob_hash"]
        return FileResponse(
            store.data_dir / "blobs" / digest_key[:2] / digest_key, filename=material["title"]
        )

    @app.get("/api/v1/objects/{oid}/revisions")
    def revisions(request: Request, oid: str):
        store = db(request)
        with store.transaction() as conn:
            require(store, conn, oid)
            return store.revisions(conn, oid)

    @app.get("/api/v1/objects/{oid}")
    def get_object(request: Request, oid: str, revision: int | None = Query(default=None, ge=1)):
        store = db(request)
        with store.transaction() as conn:
            return require_revision(store, conn, oid, revision)

    @app.post("/api/v1/reports/runs")
    def generate_report(request: Request, payload: ReportRequest):
        store = db(request)
        with store.transaction() as conn:
            return build_report(store, conn, payload)

    @app.post("/api/v1/blogs")
    def new_blog(request: Request, payload: BlogRequest):
        store = db(request)
        with store.transaction() as conn:
            material_ids = list(
                dict.fromkeys(payload.material_ids or [r.material_id for r in payload.source_refs])
            )
            materials = [require(store, conn, mid, "material") for mid in material_ids]
            if payload.report_id:
                report = require(store, conn, payload.report_id, "report")
                if payload.report_revision and payload.report_revision != report["revision"]:
                    report = next(
                        (
                            r
                            for r in store.revisions(conn, report["id"])
                            if r["revision"] == payload.report_revision
                        ),
                        None,
                    )
                    if not report:
                        raise HTTPException(404, "报告版本不存在")
                frozen = {m["id"]: m for m in report["sources"]}
                if any(mid not in frozen for mid in material_ids):
                    raise HTTPException(422, "选题输入不在报告中")
                materials = [frozen[mid] for mid in material_ids]
            if payload.source_refs:
                materials = []
                if len({r.material_id for r in payload.source_refs}) != len(payload.source_refs):
                    raise HTTPException(422, "同一篇文章不能选择同一素材的多个版本")
                for ref in payload.source_refs:
                    frozen_source = require_revision(
                        store, conn, ref.material_id, ref.material_revision, "material"
                    )
                    if frozen_source["blob_hash"] != ref.blob_hash:
                        raise HTTPException(422, "原件 hash 与素材版本不匹配")
                    if (
                        payload.report_id
                        and source_ref(frozen[ref.material_id]) != ref.model_dump()
                    ):
                        raise HTTPException(422, "来源版本不属于报告快照")
                    materials.append(frozen_source)
            if not any(m["parse_state"] == "ready" for m in materials):
                raise HTTPException(422, "请先补充素材正文")
            return store.insert(
                conn,
                "blog",
                record(
                    "blog",
                    title=payload.title,
                    body=blog_body(payload.title, materials),
                    material_ids=material_ids,
                    source_snapshots=materials,
                    source_refs=[source_ref(m) for m in materials],
                    topic=materials[0]["topic"],
                    lifecycle="draft",
                    report_id=payload.report_id,
                    is_demo=all(m.get("is_demo", False) for m in materials),
                ),
            )

    @app.post("/api/v1/blogs/{oid}/revisions")
    def save_blog(request: Request, oid: str, payload: RevisionRequest):
        store = db(request)
        with store.transaction() as conn:
            blog = require(store, conn, oid, "blog", True)
            return store.update(
                conn,
                {**blog, "title": payload.title, "body": payload.body, "lifecycle": "draft"},
                payload.revision,
            )

    @app.post("/api/v1/blogs/{oid}/accept")
    def accept_blog(request: Request, oid: str, payload: AcceptRequest):
        store = db(request)
        with store.transaction() as conn:
            blog = require(store, conn, oid, "blog", True)
            if payload.revision != blog["revision"]:
                raise HTTPException(409, "请先保存并确认当前版本")
            if blog["lifecycle"] == "accepted":
                return blog
            return store.update(conn, {**blog, "lifecycle": "accepted"}, blog["revision"])

    @app.post("/api/v1/library/proposals")
    def library_proposal(request: Request, payload: ProposalRequest):
        store = db(request)
        with store.transaction() as conn:
            blog = require(store, conn, payload.blog_id, "blog", True)
            if blog["lifecycle"] != "accepted":
                raise HTTPException(422, "请先确认博客，再整理到图书馆")
            for proposal in store.list(conn, "proposal"):
                if (
                    proposal["blog_id"] == blog["id"]
                    and proposal["blog_revision"] == blog["revision"]
                ):
                    return proposal
            return store.insert(
                conn,
                "proposal",
                record(
                    "proposal",
                    title=blog["title"],
                    body=blog["body"],
                    topic=blog["topic"],
                    blog_id=blog["id"],
                    blog_revision=blog["revision"],
                    material_ids=blog["material_ids"],
                    source_snapshots=blog.get("source_snapshots", []),
                    source_refs=blog.get("source_refs", []),
                    book="数据库执行引擎" if blog["topic"] == "database" else "我的知识手册",
                    status="pending",
                    is_demo=blog.get("is_demo", False),
                ),
            )

    @app.post("/api/v1/library/proposals/{oid}/accept")
    def accept_proposal(request: Request, oid: str):
        store = db(request)
        with store.transaction() as conn:
            proposal = require(store, conn, oid, "proposal", True)
            if proposal.get("entry_id"):
                return require(store, conn, proposal["entry_id"], "entry")
            blog = require(store, conn, proposal["blog_id"], "blog")
            if blog["revision"] != proposal["blog_revision"] or blog["lifecycle"] != "accepted":
                raise HTTPException(409, "博客已修改，请基于最新确认版本重新整理")
            entry = store.insert(
                conn,
                "entry",
                record(
                    "entry",
                    title=proposal["title"],
                    body=proposal["body"],
                    topic=proposal["topic"],
                    book=proposal["book"],
                    material_ids=proposal["material_ids"],
                    source_snapshots=proposal.get("source_snapshots", []),
                    source_refs=proposal.get("source_refs", []),
                    blog_id=blog["id"],
                    blog_revision=blog["revision"],
                    is_demo=proposal["is_demo"],
                    due_day=(date.fromisoformat(today()) + timedelta(days=3)).isoformat(),
                    reviews=[],
                ),
            )
            store.update(
                conn,
                {**proposal, "status": "accepted", "entry_id": entry["id"]},
                proposal["revision"],
            )
            return entry

    @app.post("/api/v1/library/entries/{oid}/reviews")
    def review(request: Request, oid: str, payload: Review):
        store = db(request)
        with store.transaction() as conn:
            entry = require(store, conn, oid, "entry", True)
            days = {"clear": 30, "fuzzy": 7, "forgot": 3}[payload.grade]
            reviews = entry["reviews"] + [{"date": today(), "grade": payload.grade}]
            return store.update(
                conn,
                {
                    **entry,
                    "reviews": reviews,
                    "due_day": (date.fromisoformat(today()) + timedelta(days=days)).isoformat(),
                },
                entry["revision"],
            )

    @app.post("/api/v1/sources")
    def add_source(request: Request, payload: SourceRequest):
        checked_url(payload.url)
        store = db(request)
        with store.transaction() as conn:
            return store.insert(
                conn,
                "source",
                record("source", **payload.model_dump(), enabled=False, status="manual"),
            )

    @app.patch("/api/v1/settings")
    def save_settings(request: Request, payload: SettingsRequest):
        store = db(request)
        with store.transaction() as conn:
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(current_schema() || '/settings'))")
            )
            existing = store.get(conn, "settings", True)
            value = {
                "id": "settings",
                "object_kind": "settings",
                "timezone": "Asia/Shanghai",
                **payload.model_dump(),
            }
            return (
                store.update(conn, value, existing["revision"])
                if existing
                else store.insert(conn, "settings", value)
            )

    @app.get("/api/v1/export/{oid}")
    def export(
        request: Request,
        oid: str,
        revision: int | None = Query(default=None, ge=1),
        format: Literal["auto", "raw", "markdown"] = "auto",
    ):
        store = db(request)
        with store.transaction() as conn:
            item = require_revision(store, conn, oid, revision)
        if item["object_kind"] == "material" and format in {"auto", "raw"}:
            key = item["blob_hash"]
            return FileResponse(
                store.data_dir / "blobs" / key[:2] / key,
                filename=item["title"],
                headers={"X-Content-SHA256": key, "X-Object-Revision": str(item["revision"])},
            )
        if format == "raw":
            raise HTTPException(422, "只有素材支持原件导出")
        if item["object_kind"] == "material" and not item["content"]:
            raise HTTPException(422, "素材没有可导出的正文，请选择原件")
        body = item.get("body", item.get("content", ""))
        if item["object_kind"] in {"blog", "entry", "proposal"}:
            frozen = {m["id"]: m for m in item.get("source_snapshots", [])}
            body = re.sub(
                r"(#/materials/([A-Za-z0-9_-]+))(?=\))",
                lambda match: (
                    f"{match[1]}?revision={frozen[match[2]]['revision']}"
                    if match[2] in frozen
                    else match[1]
                ),
                body,
            )
        if item["object_kind"] == "report":
            mode = (
                "真实模型证据消化"
                if item.get("generation_mode") == "llm_evidence"
                else "提取式整理"
            )
            body = f"# {item['title']}\n\n{mode} · 版本 {item['revision']} · 截止 {item['cutoff_at']}\n\n"
            for material in item["sources"]:
                body += f"## {material['title']}\n\n"
                for quote in material["digest"]["excerpts"]:
                    body += f"> {quote['text']}\n\n"
                body += f"来源：{material['url'] or material['kind']} · {material['id']} · revision {material['revision']} · sha256 {material['blob_hash']}\n\n[查看原件]({request.base_url}api/v1/materials/{material['id']}/original?revision={material['revision']})\n\n"
            for artifact in item.get("evidence_digests", []):
                body += evidence_markdown(artifact) + "\n"
        if item["object_kind"] == "digest":
            body = evidence_markdown(item)
        return PlainTextResponse(
            body, headers={"Content-Disposition": f'attachment; filename="{oid}.md"'}
        )

    @app.get("/api/v1/workspace/backup")
    def backup_workspace(request: Request):
        raw = export_workspace(db(request))
        return Response(
            raw,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="panming-workspace.zip"',
                "X-Content-SHA256": hashlib.sha256(raw).hexdigest(),
            },
        )

    @app.get("/api/v1/workspace/integrity")
    def integrity(request: Request):
        return workspace_integrity(db(request))

    @app.post("/api/v1/workspace/restore")
    async def restore(request: Request, file: UploadFile = File(...)):
        raw = await file.read(MAX_ARCHIVE + 1)
        # Parsing/SQL/fsync run in the thread pool, not the event loop.
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(restore_workspace, db(request), raw)

    dist = ROOT / "web" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/favicon.svg")
    def favicon():
        return FileResponse(ROOT / "web" / "public" / "favicon.svg")

    @app.get("/")
    def index():
        if not (dist / "index.html").exists():
            return PlainTextResponse("请先在 web/ 运行 npm run build", status_code=503)
        return FileResponse(dist / "index.html")

    return app


app = create_app()
