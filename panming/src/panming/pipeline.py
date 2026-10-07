"""Durable, fenced evidence jobs, with explicit consent for cloud processing.

Jobs and digests use the existing immutable object journal, so workspace backups
cover checkpoints too. Provider execution never holds a database transaction.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text

from .content import excerpts
from .llm import (
    CLOUD_MAX_INPUT,
    LLM_PROMPT_VERSION,
    LLMError,
    abandon_calls,
    cloud_budget,
    token_reservation,
)
from .storage import Store, now, object_id

PROMPT_VERSION = "evidence-v1"
SCHEMA_VERSION = "claims-v1"
CHUNK_VERSION = "unicode-offset-v1"
MAX_INPUT = 60_000
MAX_OUTPUT = 20_000
LEASE_SECONDS = 30
MAX_ATTEMPTS = 3
ACTIVE = {"queued", "running"}


class PipelineError(Exception):
    def __init__(self, code: str, detail: str, status: int = 422):
        self.code, self.detail, self.status = code, detail, status


class Structured(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Citation(Structured):
    chunk_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=500)


class Claim(Structured):
    kind: Literal["source_statement", "inference"]
    text: str = Field(min_length=1, max_length=800)
    citations: list[Citation] = Field(min_length=1, max_length=5)


class Output(Structured):
    claims: list[Claim] = Field(min_length=1, max_length=12)
    questions: list[str] = Field(max_length=3)


def chunks_for(material: dict) -> list[dict]:
    """Keep exact text and Unicode code-point offsets, including newline bytes.

    A long line is split without dropping text. Line numbers are navigation hints;
    offset/end and chunk_hash are the precise anchor (not UTF-8 byte offsets).
    """
    content = material["content"]
    result = []
    for start in range(0, len(content), 2000):
        end = min(start + 2000, len(content))
        body = content[start:end]
        ref = {
            "material_id": material["id"],
            "material_revision": material["revision"],
            "blob_hash": material["blob_hash"],
        }
        chunk_hash = hashlib.sha256(body.encode()).hexdigest()
        identity = json.dumps([ref, start, end, chunk_hash], sort_keys=True)
        result.append(
            {
                **ref,
                "chunk_id": "chunk_" + hashlib.sha256(identity.encode()).hexdigest(),
                "chunk_hash": chunk_hash,
                "offset": start,
                "end": end,
                "start_line": content.count("\n", 0, start) + 1,
                "end_line": content.count("\n", 0, max(start, end - 1)) + 1,
                "text": body,
                "title": material["title"],
                "topic": material["topic"],
            }
        )
    return result


def validate_output(value: dict, chunks: list[dict]) -> dict:
    try:
        if len(json.dumps(value, ensure_ascii=False)) > MAX_OUTPUT:
            raise ValueError("size")
        output = Output.model_validate(value)
        by_id = {c["chunk_id"]: c for c in chunks}
        for question in output.questions:
            if not question.strip() or len(question) > 500 or "\x00" in question:
                raise ValueError("question")
        for claim in output.claims:
            if not claim.text.strip() or "\x00" in claim.text:
                raise ValueError("claim")
            for cite in claim.citations:
                chunk = by_id.get(cite.chunk_id)
                if not chunk or not cite.quote.strip() or cite.quote not in chunk["text"]:
                    raise ValueError("citation")
        return output.model_dump()
    except (ValidationError, ValueError, KeyError, TypeError) as error:
        # Never include provider output / raw material in an error or log.
        raise PipelineError("INVALID_EVIDENCE", "生成结果未通过结构与引用校验") from error


class Provider(Protocol):
    name: str
    locality: Literal["local", "cloud"]

    def generate(self, chunks: list[dict]) -> dict: ...


class MockProvider:
    name = "mock"
    locality = "local"

    def generate(self, chunks: list[dict]) -> dict:
        claims = []
        seen = set()
        # One representative excerpt per source; no semantic/conflict claims.
        full_sources = {}
        for chunk in chunks:
            full_sources.setdefault(chunk["material_id"], []).append(chunk)
        for source_chunks in full_sources.values():
            source_chunks.sort(key=lambda c: c["offset"])
            full_text = "".join(c["text"] for c in source_chunks)
            candidates = excerpts(full_text, limit=12)
            pair = next(
                (
                    (q["text"], c)
                    for q in candidates
                    for c in source_chunks
                    if q["text"] in c["text"]
                ),
                None,
            )
            if not pair:
                continue
            quote, chunk = pair
            if chunk["material_id"] in seen:
                continue
            claims.append(
                {
                    "kind": "source_statement",
                    "text": quote,
                    "citations": [{"chunk_id": chunk["chunk_id"], "quote": quote}],
                }
            )
            seen.add(chunk["material_id"])
            if len(claims) == 12:
                break
        if not claims:
            raise PipelineError("NO_EVIDENCE", "没有可提取的正文段落，原件保留；请补充说明")
        return {
            "claims": claims,
            "questions": ["哪些来源陈述需要通过自己的阅读或实验验证？"],
        }


def job_view(job: dict) -> dict:
    return {k: v for k, v in job.items() if k != "chunks"}


def lock_jobs(conn) -> None:
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(current_schema() || '/jobs'))"))


class Pipeline:
    def __init__(
        self,
        store: Store,
        *,
        providers: dict[str, Provider] | None = None,
        daily_limit: int = 500_000,
        clock: Callable[[], datetime] | None = None,
    ):
        self.store = store
        # Explicit provider injection only; backups never configure credentials.
        self.providers = providers if providers is not None else {"mock": MockProvider()}
        self.daily_limit = daily_limit
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def lock(self, conn):
        lock_jobs(conn)

    def budget(self, conn, day: str | None = None) -> dict:
        day = day or self.clock().astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
        jobs = self.store.list(conn, "job")
        reserved = sum(j["reserved_units"] for j in jobs if j["budget_day"] == day)
        used = sum(j["usage_by_day"].get(day, 0) for j in jobs)
        cloud = self.providers.get("openai_compatible")
        has_cloud = bool(cloud) or any(j["provider"] == "openai_compatible" for j in jobs)
        return {
            "day": day,
            "limit": self.daily_limit,
            "reserved": reserved,
            "used": used,
            "remaining": max(0, self.daily_limit - reserved - used),
            "unit": "unicode_characters_not_tokens",
            "cost": None if has_cloud else 0,
            "currency": "CNY",
            "mode": "cloud_available" if cloud else "offline_mock",
            "cloud": cloud_budget(jobs, cloud.config if cloud else None, day)
            if has_cloud
            else None,
        }

    def profiles(self) -> list[dict]:
        return [{"provider": "mock", "model": "extractive-mock-v1", "locality": "local"}] + [
            {
                **p.profile(),
                "locality": "cloud",
                "timeout": p.config.timeout,
                "max_input": CLOUD_MAX_INPUT,
            }
            for name, p in self.providers.items()
            if name == "openai_compatible"
        ]

    def reserve_cloud(self, conn, provider, day: str, amount: int, *, exclude: str | None = None):
        value = cloud_budget(
            self.store.list(conn, "job"), provider.config, day, exclude_reservation=exclude
        )
        if value["remaining_requests"] < 1 or value["remaining_tokens"] < amount:
            raise PipelineError("LLM_BUDGET_EXCEEDED", "模型调用/token 额度不足；未发送请求", 409)

    def check_cloud_job(self, conn, job: dict, provider) -> None:
        if job.get("provider_profile") != provider.profile() or not job.get("cloud_consent"):
            raise PipelineError(
                "LLM_PROFILE_CHANGED", "模型或服务配置已变化，请重新确认后创建新任务", 409
            )
        for ref in job["source_refs"]:
            current = self.store.get(conn, ref["material_id"])
            frozen = self.store.get_revision(conn, ref["material_id"], ref["material_revision"])
            self.check_policy(current, provider)
            self.check_policy(frozen, provider)

    def reserve(self, conn, day: str, amount: int) -> None:
        if self.budget(conn, day)["remaining"] < amount:
            raise PipelineError("BUDGET_EXCEEDED", "当日处理额度不足，未创建或启动任务", 409)

    def verify_original(self, material: dict) -> None:
        key = material["blob_hash"]
        path = self.store.data_dir / "blobs" / key[:2] / key
        try:
            valid = hashlib.sha256(path.read_bytes()).hexdigest() == key
        except OSError:
            valid = False
        if not valid:
            raise PipelineError(
                "SOURCE_BLOB_INVALID", "来源原件缺失或校验失败，请先检查工作空间完整性"
            )

    def submit(
        self,
        refs: list[dict],
        provider_name: str = "mock",
        *,
        cloud_consent: bool = False,
        provider_profile: str | None = None,
    ) -> dict:
        provider = self.providers.get(provider_name)
        if not provider or provider_name not in {"mock", "openai_compatible"}:
            raise PipelineError("PROVIDER_DISABLED", "模型服务未配置或未启用")
        cloud = provider_name == "openai_compatible"
        if cloud and (not cloud_consent or provider_profile != provider.profile()["profile_id"]):
            raise PipelineError(
                "CLOUD_CONSENT_REQUIRED", "请明确确认所选正文的外发与当前模型服务", 403
            )
        with self.store.transaction() as conn:
            self.store.lock_inputs(conn)
            self.lock(conn)
            if not refs or len(refs) > 12 or len({r["material_id"] for r in refs}) != len(refs):
                raise PipelineError("INVALID_SOURCES", "请选择 1–12 份不重复的素材版本")
            sources = []
            for ref in refs:
                material = self.store.get_revision(
                    conn, ref["material_id"], ref["material_revision"]
                )
                if (
                    not material
                    or material.get("object_kind") != "material"
                    or material.get("blob_hash") != ref["blob_hash"]
                ):
                    raise PipelineError("INVALID_SOURCE_REF", "素材版本不存在或原件 hash 不一致")
                if material.get("parse_state") != "ready" or not material["content"].strip():
                    raise PipelineError("SOURCE_NOT_READY", "请先为素材补充可阅读正文")
                self.check_policy(material, provider)
                if cloud:
                    self.check_policy(self.store.get(conn, ref["material_id"]), provider)
                self.verify_original(material)
                sources.append(material)
            refs = sorted(refs, key=lambda r: r["material_id"])
            profile = provider.profile() if cloud else None
            prompt_version = LLM_PROMPT_VERSION if cloud else PROMPT_VERSION
            identity = [refs, provider_name, prompt_version, SCHEMA_VERSION, CHUNK_VERSION]
            if cloud:
                identity.append(profile)
            signature = hashlib.sha256(
                json.dumps(
                    identity,
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            existing = next(
                (j for j in self.store.list(conn, "job") if j["signature"] == signature), None
            )
            if existing:
                return job_view(existing)
            input_units = sum(len(m["content"]) for m in sources)
            if input_units > (CLOUD_MAX_INPUT if cloud else MAX_INPUT):
                raise PipelineError(
                    "INPUT_TOO_LARGE",
                    f"单任务正文上限 {CLOUD_MAX_INPUT if cloud else MAX_INPUT:,} 字符，请拆分；不会静默截断",
                )
            day = self.clock().astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
            estimate = input_units + MAX_OUTPUT
            self.reserve(conn, day, estimate)
            chunks = [c for m in sources for c in chunks_for(m)]
            reserved_tokens = token_reservation(provider.config, chunks) if cloud else 0
            if cloud:
                self.reserve_cloud(conn, provider, day, reserved_tokens)
            job = {
                "id": object_id("job"),
                "object_kind": "job",
                "created_at": now(),
                "signature": signature,
                "state": "queued",
                "provider": provider_name,
                "source_refs": refs,
                "chunks": chunks,
                "prompt_version": prompt_version,
                "schema_version": SCHEMA_VERSION,
                "chunk_version": CHUNK_VERSION,
                "checkpoint": "input_frozen",
                "attempts": 0,
                "fence": 0,
                "lease_owner": None,
                "lease_until": None,
                "budget_day": day,
                "estimate_units": estimate,
                "reserved_units": estimate,
                "used_units": 0,
                "usage_by_day": {},
                "error_code": None,
                "digest_id": None,
                "provider_profile": profile,
                "cloud_consent": cloud_consent if cloud else False,
                "consent_at": now() if cloud else None,
                "cloud_reserved_tokens": reserved_tokens,
                "call_attempts": [],
            }
            return job_view(self.store.insert(conn, "job", job))

    @staticmethod
    def check_policy(material: dict, provider: Provider) -> None:
        if not material:
            raise PipelineError("POLICY_BLOCKED", "来源已不可用", 403)
        policy = material.get("processing_policy", "local_only")
        if policy not in {"local_only", "cloud_allowed"} or (
            provider.locality == "cloud" and policy != "cloud_allowed"
        ):
            raise PipelineError("POLICY_BLOCKED", "素材处理策略禁止该模型服务", 403)
        if (
            provider.locality == "cloud"
            and hasattr(provider, "profile")
            and material.get("cloud_allowed_profile") != provider.profile()["profile_id"]
        ):
            raise PipelineError(
                "POLICY_DESTINATION_BLOCKED", "素材未授权给当前服务/模型，请重新设置处理策略", 403
            )

    def action(
        self,
        jid: str,
        action: Literal["cancel", "retry"],
        *,
        cloud_consent: bool = False,
        provider_profile: str | None = None,
    ) -> dict:
        with self.store.transaction() as conn:
            self.lock(conn)
            job = self.store.get(conn, jid, lock=True)
            if not job or job.get("object_kind") != "job":
                raise PipelineError("JOB_NOT_FOUND", "任务不存在", 404)
            if action == "cancel":
                if job["state"] not in ACTIVE | {"paused"}:
                    return job_view(job)
                values = {
                    "state": "cancelled",
                    "reserved_units": 0,
                    "cloud_reserved_tokens": 0,
                    "checkpoint": "cancelled",
                }
            else:
                if job["state"] in ACTIVE | {"succeeded"}:
                    return job_view(job)
                if job["attempts"] >= MAX_ATTEMPTS:
                    raise PipelineError(
                        "RETRY_LIMIT", "已达到 3 次尝试上限，请检查素材后创建新版本", 409
                    )
                if job["provider"] not in self.providers:
                    raise PipelineError("PROVIDER_DISABLED", "该模型服务当前未启用")
                day = self.clock().astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
                cloud = job["provider"] == "openai_compatible"
                if cloud:
                    provider = self.providers[job["provider"]]
                    if not cloud_consent or provider_profile != provider.profile()["profile_id"]:
                        raise PipelineError(
                            "CLOUD_CONSENT_REQUIRED", "云端重试可能再次消耗额度，请明确确认", 403
                        )
                    self.check_cloud_job(conn, job, provider)
                    if any(call["state"] == "in_flight" for call in job.get("call_attempts", [])):
                        raise PipelineError(
                            "CALL_STILL_PENDING", "上一请求正在中止或结算，请稍后重试", 409
                        )
                    self.reserve_cloud(
                        conn, provider, day, token_reservation(provider.config, job["chunks"])
                    )
                self.reserve(conn, day, job["estimate_units"])
                values = {
                    "state": "queued",
                    "budget_day": day,
                    "reserved_units": job["estimate_units"],
                    "checkpoint": "input_frozen",
                    "error_code": None,
                    "cloud_reserved_tokens": token_reservation(provider.config, job["chunks"])
                    if cloud
                    else 0,
                }
            return job_view(
                self.store.update(
                    conn,
                    {
                        **job,
                        **values,
                        "fence": job["fence"] + 1,
                        "lease_owner": None,
                        "lease_until": None,
                    },
                    job["revision"],
                )
            )

    def claim(self, owner: str) -> dict | None:
        with self.store.transaction() as conn:
            self.lock(conn)
            clock = self.clock()
            for job in reversed(self.store.list(conn, "job")):
                expired = (
                    job["state"] == "running"
                    and datetime.fromisoformat(job["lease_until"]) <= clock
                )
                if job["state"] != "queued" and not expired:
                    continue
                if expired and job["provider"] == "openai_compatible":
                    # A timed-out paid request might have reached the upstream.
                    # Never automatically resend it after process/lease failure.
                    self.store.update(
                        conn,
                        {
                            **job,
                            "state": "failed",
                            "error_code": "CALL_INTERRUPTED",
                            "reserved_units": 0,
                            "cloud_reserved_tokens": 0,
                            "call_attempts": abandon_calls(job),
                            "lease_owner": None,
                            "lease_until": None,
                            "fence": job["fence"] + 1,
                        },
                        job["revision"],
                    )
                    continue
                if job["attempts"] >= MAX_ATTEMPTS:
                    self.store.update(
                        conn,
                        {
                            **job,
                            "state": "failed",
                            "error_code": "LEASE_EXHAUSTED",
                            "reserved_units": 0,
                            "cloud_reserved_tokens": 0,
                            "lease_owner": None,
                            "lease_until": None,
                            "fence": job["fence"] + 1,
                        },
                        job["revision"],
                    )
                    continue
                return self.store.update(
                    conn,
                    {
                        **job,
                        "state": "running",
                        "attempts": job["attempts"] + 1,
                        "fence": job["fence"] + 1,
                        "lease_owner": owner,
                        "lease_until": (clock + timedelta(seconds=LEASE_SECONDS)).isoformat(),
                        "checkpoint": "provider_pending",
                        "error_code": None,
                    },
                    job["revision"],
                )
        return None

    def owns(self, current: dict | None, job: dict) -> bool:
        return bool(
            current
            and current["state"] == "running"
            and current["fence"] == job["fence"]
            and current["lease_owner"] == job["lease_owner"]
            and datetime.fromisoformat(current["lease_until"]) > self.clock()
        )

    def heartbeat(self, job: dict) -> bool:
        with self.store.transaction() as conn:
            self.lock(conn)
            current = self.store.get(conn, job["id"], lock=True)
            if not self.owns(current, job):
                return False
            if current["provider"] == "openai_compatible":
                try:
                    self.check_cloud_job(conn, current, self.providers[current["provider"]])
                except PipelineError:
                    return False
            self.store.update(
                conn,
                {
                    **current,
                    "lease_until": (self.clock() + timedelta(seconds=LEASE_SECONDS)).isoformat(),
                },
                current["revision"],
            )
            return True

    def begin_call(self, job: dict) -> dict:
        with self.store.transaction() as conn:
            self.lock(conn)
            current = self.store.get(conn, job["id"], lock=True)
            if not self.owns(current, job):
                raise PipelineError("CALL_CANCELLED", "任务已取消或租约过期", 409)
            provider = self.providers[current["provider"]]
            self.check_cloud_job(conn, current, provider)
            day = self.clock().astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
            tokens = token_reservation(provider.config, current["chunks"])
            self.reserve_cloud(conn, provider, day, tokens, exclude=current["id"])
            call = {
                "id": object_id("call"),
                "fence": current["fence"],
                "day": day,
                "started_at": now(),
                "state": "in_flight",
                "token_reservation": tokens,
                "usage": None,
                "response_id": None,
                "error_code": None,
            }
            self.store.update(
                conn,
                {
                    **current,
                    "cloud_reserved_tokens": 0,
                    "call_attempts": [*current.get("call_attempts", []), call],
                },
                current["revision"],
            )
            return call

    def settle_call(
        self,
        job: dict,
        call: dict,
        *,
        usage: dict | None,
        uncertain: bool,
        error_code: str | None = None,
        response_id: str | None = None,
    ):
        # Settlement is allowed even after cancellation/fence change. Rejecting
        # a late artifact must not erase a paid or possibly-paid API request.
        with self.store.transaction() as conn:
            self.lock(conn)
            current = self.store.get(conn, job["id"], lock=True)
            calls = current.get("call_attempts", [])
            updated = []
            changed = False
            for item in calls:
                if (
                    item["id"] == call["id"]
                    and item["fence"] == job["fence"]
                    and item["state"] in {"in_flight", "uncertain"}
                ):
                    changed = True
                    updated.append(
                        {
                            **item,
                            "state": "uncertain" if usage is None and uncertain else "settled",
                            "usage": usage
                            if usage is not None
                            else None
                            if uncertain
                            else {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                            "error_code": error_code,
                            "response_id": response_id,
                        }
                    )
                else:
                    updated.append(item)
            if changed:
                self.store.update(conn, {**current, "call_attempts": updated}, current["revision"])

    def cancel_cloud_jobs(self, conn, material_id: str):
        self.lock(conn)
        for job in self.store.list(conn, "job"):
            if (
                job["provider"] == "openai_compatible"
                and job["state"] in ACTIVE | {"paused"}
                and any(r["material_id"] == material_id for r in job["source_refs"])
            ):
                self.store.update(
                    conn,
                    {
                        **job,
                        "state": "cancelled",
                        "checkpoint": "policy_revoked",
                        "error_code": "POLICY_BLOCKED",
                        "fence": job["fence"] + 1,
                        "reserved_units": 0,
                        "cloud_reserved_tokens": 0,
                        "lease_owner": None,
                        "lease_until": None,
                    },
                    job["revision"],
                )

    def finish(self, job: dict, output: dict | None = None, error_code: str | None = None) -> bool:
        validated = validate_output(output, job["chunks"]) if output is not None else None
        with self.store.transaction() as conn:
            self.lock(conn)
            current = self.store.get(conn, job["id"], lock=True)
            if not self.owns(current, job):
                return False  # Expired or cancelled workers cannot publish.
            if validated and current["provider"] == "openai_compatible":
                self.check_cloud_job(conn, current, self.providers[current["provider"]])
            used = sum(len(c["text"]) for c in job["chunks"])
            if validated:
                used += len(json.dumps(validated, ensure_ascii=False))
                chunk_sources = {c["chunk_id"]: c["material_id"] for c in job["chunks"]}
                covered = {
                    chunk_sources[cite["chunk_id"]]
                    for claim in validated["claims"]
                    for cite in claim["citations"]
                }
                prior_hashes = {
                    r["blob_hash"]
                    for d in self.store.list(conn, "digest")
                    for r in d["source_refs"]
                }
                artifact = self.store.insert(
                    conn,
                    "digest",
                    {
                        "id": object_id("digest"),
                        "object_kind": "digest",
                        "created_at": now(),
                        "job_id": job["id"],
                        "job_fence": job["fence"],
                        "provider": job["provider"],
                        "mode": "cloud_llm"
                        if job["provider"] == "openai_compatible"
                        else "offline_mock",
                        "model": job["provider_profile"]["model"]
                        if job.get("provider_profile")
                        else "extractive-mock-v1",
                        "provider_profile": job.get("provider_profile"),
                        "call_attempts": current.get("call_attempts", []),
                        "source_refs": job["source_refs"],
                        "chunks": job["chunks"],
                        "output": validated,
                        "prompt_version": job["prompt_version"],
                        "schema_version": job["schema_version"],
                        "validation": "reference_and_verbatim_quote_only_not_entailment",
                        "topic_delta": [
                            {
                                **r,
                                "status": "previously_processed"
                                if r["blob_hash"] in prior_hashes
                                else "first_processed",
                            }
                            for r in job["source_refs"]
                        ],
                        "conflict_detection": "not_assessed",
                        "needs_human_review": True,
                        "coverage_state": "complete"
                        if len(covered) == len(job["source_refs"])
                        else "partial",
                        "source_coverage": [
                            {
                                **ref,
                                "status": "excerpted"
                                if ref["material_id"] in covered
                                else "no_excerpt",
                            }
                            for ref in job["source_refs"]
                        ],
                    },
                )
            else:
                artifact = None
            self.store.update(
                conn,
                {
                    **current,
                    "state": "succeeded" if artifact else "failed",
                    "checkpoint": "evidence_validated" if artifact else "failed",
                    "digest_id": artifact["id"] if artifact else None,
                    "error_code": error_code if not artifact else None,
                    "reserved_units": 0,
                    "cloud_reserved_tokens": 0,
                    "used_units": current["used_units"] + used,
                    "usage_by_day": {
                        **current["usage_by_day"],
                        current["budget_day"]: current["usage_by_day"].get(current["budget_day"], 0)
                        + used,
                    },
                    "lease_owner": None,
                    "lease_until": None,
                },
                current["revision"],
            )
            return True

    def run_once(
        self, owner: str = "offline-worker", stop_event: threading.Event | None = None
    ) -> bool:
        job = self.claim(owner)
        if not job:
            return False
        call = None
        done, cancelled = threading.Event(), threading.Event()
        heartbeat = None
        try:
            provider = self.providers.get(job["provider"])
            if not provider or job["provider"] not in {"mock", "openai_compatible"}:
                raise PipelineError("PROVIDER_DISABLED", "服务未启用")
            # Recheck current policy immediately before execution; policy changes
            # must not grant permission by choosing an old permissive revision.
            with self.store.transaction() as conn:
                for ref in job["source_refs"]:
                    material = self.store.get(conn, ref["material_id"])
                    self.check_policy(material, provider)
                    frozen = self.store.get_revision(
                        conn, ref["material_id"], ref["material_revision"]
                    )
                    self.verify_original(frozen)
            if job["provider"] == "openai_compatible":
                call = self.begin_call(job)

                def renew():
                    while not done.wait(5):
                        try:
                            if not self.heartbeat(job):
                                cancelled.set()
                                return
                        except Exception:
                            cancelled.set()
                            return

                heartbeat = threading.Thread(target=renew, name="panming-lease", daemon=True)
                heartbeat.start()
                result = provider.generate_with_usage(
                    job["chunks"],
                    lambda: cancelled.is_set() or bool(stop_event and stop_event.is_set()),
                )
                self.settle_call(
                    job,
                    call,
                    usage=result.usage,
                    uncertain=result.usage is None,
                    response_id=result.response_id,
                )
                output = result.output
            else:
                output = provider.generate(job["chunks"])
            self.finish(job, output)
        except LLMError as error:
            if call:
                self.settle_call(
                    job,
                    call,
                    usage=error.usage,
                    uncertain=error.uncertain,
                    error_code=error.code,
                    response_id=error.response_id,
                )
            self.finish(job, error_code=error.code)
        except PipelineError as error:
            if call:
                self.settle_call(job, call, usage=None, uncertain=True, error_code=error.code)
            self.finish(job, error_code=error.code)
        except Exception:
            if call:
                self.settle_call(
                    job, call, usage=None, uncertain=True, error_code="CALL_INTERRUPTED"
                )
            self.finish(job, error_code="PROVIDER_FAILED")
        finally:
            done.set()
            if heartbeat:
                heartbeat.join(timeout=1)
        return True


class Worker:
    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="panming-evidence", daemon=True)
        self.owner = object_id("worker")

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=5)

    def run(self):
        while not self.stop_event.is_set():
            try:
                worked = self.pipeline.run_once(self.owner, self.stop_event)
            except Exception:
                # Database interruptions leave a lease for restart recovery.
                worked = False
            if not worked:
                self.stop_event.wait(1)


def evidence_markdown(digest: dict) -> str:
    chunks = {c["chunk_id"]: c for c in digest["chunks"]}
    lines = [
        f"## 证据化消化（{'真实模型 ' + digest['model'] if digest['mode'] == 'cloud_llm' else '本地 mock'} / 待人工复核）",
        "",
        "仅校验引用与原文摘录，不证明结论成立，也未自动识别冲突。",
        "",
    ]
    for claim in digest["output"]["claims"]:
        lines.extend(
            [
                f"### {'来源陈述' if claim['kind'] == 'source_statement' else '模型推断'}",
                "",
                claim["text"],
                "",
            ]
        )
        for cite in claim["citations"]:
            c = chunks[cite["chunk_id"]]
            lines.extend(
                [
                    "> " + cite["quote"].replace("\n", "\n> "),
                    "",
                    f"[{c['title']} · v{c['material_revision']} · L{c['start_line']}–{c['end_line']}](#/materials/{c['material_id']}?revision={c['material_revision']})",
                    f"\n原件 `{c['blob_hash']}`；片段 `{c['chunk_hash']}`；Unicode 偏移 [{c['offset']}, {c['end']})。",
                    "",
                ]
            )
    lines.extend(["### 待验证问题", "", *[f"- {q}" for q in digest["output"]["questions"]], ""])
    return "\n".join(lines)
