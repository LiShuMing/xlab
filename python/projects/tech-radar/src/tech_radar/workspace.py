from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from tech_radar.delivery import (
    ArticlePayload,
    ArtifactSpec,
    create_delivery_adapters,
    mark_xiaohongshu_published,
)


WORKSPACE_SCHEMA_VERSION = 3


@dataclass(frozen=True, slots=True)
class SyncReport:
    scanned: int
    inserted: int
    updated: int


@dataclass(frozen=True, slots=True)
class MaterialPage:
    items: tuple[dict[str, Any], ...]
    next_cursor: str | None


class WorkspaceStore:
    """Repository for the content workspace layered over the legacy signal store."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> SyncReport:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._apply_migrations(connection)
        return self.synchronize_legacy_signals()

    def synchronize_legacy_signals(self, run_id: str | None = None) -> SyncReport:
        with self._connect() as connection:
            if not self._table_exists(connection, "signals"):
                return SyncReport(0, 0, 0)
            source_rows = connection.execute(
                """
                SELECT platform, external_id, GROUP_CONCAT(source_id, ', ') source_ids
                FROM signal_sources
                GROUP BY platform, external_id
                """
            ).fetchall()
            sources = {
                (row["platform"], row["external_id"]): row["source_ids"]
                for row in source_rows
            }
            rows = connection.execute("SELECT * FROM signals").fetchall()
            inserted = 0
            updated = 0
            for row in rows:
                author = self._clean_text(row["author"], single_line=True)
                title = self._clean_text(row["title"], single_line=True)
                content = self._clean_text(row["content"])
                material_id = self._stable_id(
                    "material", row["platform"], row["external_id"]
                )
                existed = connection.execute(
                    "SELECT 1 FROM materials WHERE id = ?", (material_id,)
                ).fetchone()
                canonical_url = self._canonical_url(row["url"])
                content_hash = self._content_hash(title, content)
                url_hash = self._sha256(canonical_url) if canonical_url else None
                now = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    """
                    INSERT INTO materials (
                        id, platform, external_id, object_type, author, title,
                        content, canonical_url, published_at, first_seen_at,
                        last_seen_at, priority, quality_score, status,
                        tags_json, metrics_json, media_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform, external_id) DO UPDATE SET
                        author = excluded.author,
                        title = excluded.title,
                        content = excluded.content,
                        canonical_url = excluded.canonical_url,
                        published_at = excluded.published_at,
                        last_seen_at = excluded.last_seen_at,
                        priority = MAX(materials.priority, excluded.priority),
                        quality_score = MAX(
                            materials.quality_score, excluded.quality_score
                        ),
                        tags_json = excluded.tags_json,
                        metrics_json = excluded.metrics_json,
                        media_json = excluded.media_json,
                        raw_json = excluded.raw_json
                    """,
                    (
                        material_id,
                        row["platform"],
                        row["external_id"],
                        row["object_type"],
                        author,
                        title,
                        content,
                        canonical_url,
                        row["published_at"],
                        row["collected_at"],
                        now,
                        int(row["priority"]),
                        float(row["score"]),
                        "new",
                        row["tags_json"],
                        row["metrics_json"],
                        row["media_json"],
                        row["raw_json"],
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO material_fingerprints (
                        material_id, url_hash, content_hash, normalizer_version
                    ) VALUES (?, ?, ?, 1)
                    ON CONFLICT(material_id) DO UPDATE SET
                        url_hash = excluded.url_hash,
                        content_hash = excluded.content_hash,
                        normalizer_version = excluded.normalizer_version
                    """,
                    (material_id, url_hash, content_hash),
                )
                for source_id in sources.get(
                    (row["platform"], row["external_id"]), ""
                ).split(", "):
                    if source_id:
                        connection.execute(
                            """
                            INSERT OR IGNORE INTO material_sources (
                                material_id, target_id, first_seen_run_id
                            ) VALUES (?, ?, ?)
                            """,
                            (material_id, source_id, run_id),
                        )
                event_id = self._stable_id("event", material_id)
                connection.execute(
                    """
                    INSERT INTO events (
                        id, canonical_title, event_type, event_time,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'active', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        canonical_title = excluded.canonical_title,
                        event_type = excluded.event_type,
                        event_time = excluded.event_time,
                        updated_at = excluded.updated_at
                    """,
                    (
                        event_id,
                        title or content[:160],
                        row["object_type"],
                        row["published_at"],
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO event_materials (
                        event_id, material_id, role, confidence, reason_json
                    ) VALUES (?, ?, 'primary', 1.0, ?)
                    """,
                    (event_id, material_id, json.dumps({"rule": "exact-source-id"})),
                )
                self._import_topic_annotation(connection, row, event_id, now)
                self._replace_fts(connection, material_id, title, content, author)
                if existed:
                    updated += 1
                else:
                    inserted += 1
            return SyncReport(len(rows), inserted, updated)

    def overview(self) -> dict[str, Any]:
        with self._connect() as connection:
            material_count = self._scalar(connection, "SELECT COUNT(*) FROM materials")
            new_count = self._scalar(
                connection, "SELECT COUNT(*) FROM materials WHERE status = 'new'"
            )
            personal_count = self._scalar(
                connection, "SELECT COUNT(*) FROM materials WHERE priority >= 100"
            )
            review_count = self._scalar(
                connection,
                "SELECT COUNT(*) FROM materials WHERE status = 'needs_review'",
            )
            topic_count = self._scalar(connection, "SELECT COUNT(*) FROM topics")
            last_run = connection.execute(
                """
                SELECT id, status, started_at, finished_at, summary_json, error
                FROM ingestion_runs ORDER BY started_at DESC LIMIT 1
                """
            ).fetchone()
        return {
            "materials": material_count,
            "new": new_count,
            "personal": personal_count,
            "needs_review": review_count,
            "topics": topic_count,
            "last_run": self._run_dict(last_run) if last_run else None,
        }

    def list_materials(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        view: str = "all",
        platform: str | None = None,
        topic_id: str | None = None,
        query: str | None = None,
    ) -> MaterialPage:
        limit = max(1, min(limit, 100))
        clauses: list[str] = []
        parameters: list[Any] = []
        joins = ""
        if view == "new":
            clauses.append("m.status = 'new'")
        elif view == "personal":
            clauses.append("m.priority >= 100")
        elif view == "needs_review":
            clauses.append("m.status = 'needs_review'")
        if platform:
            clauses.append("m.platform = ?")
            parameters.append(platform)
        if topic_id:
            joins += " JOIN event_materials ef ON ef.material_id = m.id"
            joins += " JOIN topic_materials tm ON tm.event_id = ef.event_id"
            clauses.append("tm.topic_id = ?")
            parameters.append(topic_id)
        if query:
            joins += " JOIN materials_fts fts ON fts.material_id = m.id"
            clauses.append("materials_fts MATCH ?")
            parameters.append(self._fts_query(query))
        if cursor:
            score, first_seen_at, material_id = self._decode_cursor(cursor)
            clauses.append(
                "(m.quality_score, m.first_seen_at, m.id) < (?, ?, ?)"
            )
            parameters.extend((score, first_seen_at, material_id))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT DISTINCT m.*,
                GROUP_CONCAT(DISTINCT ms.target_id) source_ids,
                GROUP_CONCAT(DISTINCT t.name) topics,
                GROUP_CONCAT(DISTINCT t.id) topic_ids,
                COUNT(DISTINCT em.event_id) event_count
            FROM materials m
            {joins}
            LEFT JOIN material_sources ms ON ms.material_id = m.id
            LEFT JOIN event_materials em ON em.material_id = m.id
            LEFT JOIN topic_materials all_tm ON all_tm.event_id = em.event_id
            LEFT JOIN topics t ON t.id = all_tm.topic_id
            {where}
            GROUP BY m.id
            ORDER BY m.quality_score DESC, m.first_seen_at DESC, m.id DESC
            LIMIT ?
        """
        parameters.append(limit + 1)
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        has_more = len(rows) > limit
        selected = rows[:limit]
        items = tuple(self._material_summary(row) for row in selected)
        next_cursor = None
        if has_more and selected:
            tail = selected[-1]
            next_cursor = self._encode_cursor(
                float(tail["quality_score"]), tail["first_seen_at"], tail["id"]
            )
        return MaterialPage(items, next_cursor)

    def get_material(self, material_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT m.*,
                    GROUP_CONCAT(DISTINCT ms.target_id) source_ids,
                    GROUP_CONCAT(DISTINCT t.name) topics,
                    GROUP_CONCAT(DISTINCT t.id) topic_ids,
                    COUNT(DISTINCT em.event_id) event_count,
                    fp.url_hash, fp.content_hash, fp.normalizer_version
                FROM materials m
                LEFT JOIN material_sources ms ON ms.material_id = m.id
                LEFT JOIN material_fingerprints fp ON fp.material_id = m.id
                LEFT JOIN event_materials em ON em.material_id = m.id
                LEFT JOIN topic_materials tm ON tm.event_id = em.event_id
                LEFT JOIN topics t ON t.id = tm.topic_id
                WHERE m.id = ?
                GROUP BY m.id
                """,
                (material_id,),
            ).fetchone()
        return self._material_detail(row) if row else None

    def list_topics(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT t.id, t.slug, t.name, t.description,
                    COUNT(DISTINCT tm.event_id) material_count
                FROM topics t
                LEFT JOIN topic_materials tm ON tm.topic_id = t.id
                WHERE t.enabled = 1
                GROUP BY t.id
                ORDER BY material_count DESC, t.name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def route_materials(
        self, material_ids: Iterable[str], topic_name: str
    ) -> dict[str, Any]:
        clean_name = topic_name.strip()
        if not clean_name:
            raise ValueError("topic_name must not be empty")
        material_ids = tuple(dict.fromkeys(material_ids))
        if not material_ids:
            raise ValueError("material_ids must not be empty")
        topic_id = self._stable_id("topic", clean_name.casefold())
        now = datetime.now(timezone.utc).isoformat()
        assigned = 0
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO topics (id, slug, name, description, enabled, created_at)
                VALUES (?, ?, ?, '', 1, ?)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name, enabled = 1
                """,
                (topic_id, self._slug(clean_name), clean_name, now),
            )
            for material_id in material_ids:
                event_rows = connection.execute(
                    "SELECT event_id FROM event_materials WHERE material_id = ?",
                    (material_id,),
                ).fetchall()
                for event_row in event_rows:
                    result = connection.execute(
                        """
                        INSERT OR IGNORE INTO topic_materials (
                            topic_id, event_id, relevance, novelty, quality,
                            status, assigned_at
                        ) VALUES (?, ?, 1.0, 1.0, 1.0, 'accepted', ?)
                        """,
                        (topic_id, event_row["event_id"], now),
                    )
                    assigned += result.rowcount
        return {"topic_id": topic_id, "topic_name": clean_name, "assigned": assigned}

    def create_rule_article(self, topic_id: str, limit: int = 12) -> dict[str, Any]:
        limit = max(1, min(limit, 50))
        with self._connect() as connection:
            topic = connection.execute(
                "SELECT id, slug, name FROM topics WHERE id = ? AND enabled = 1",
                (topic_id,),
            ).fetchone()
            if topic is None:
                raise ValueError("topic not found")
            materials = connection.execute(
                """
                SELECT DISTINCT m.*, em.event_id, fp.content_hash
                FROM topic_materials tm
                JOIN event_materials em ON em.event_id = tm.event_id
                JOIN materials m ON m.id = em.material_id
                JOIN material_fingerprints fp ON fp.material_id = m.id
                WHERE tm.topic_id = ? AND tm.status = 'accepted'
                ORDER BY m.quality_score DESC, m.first_seen_at DESC
                LIMIT ?
                """,
                (topic_id, limit),
            ).fetchall()
            if not materials:
                raise ValueError("topic has no accepted materials")
            material_set_hash = self._sha256(
                "\n".join(
                    sorted(f"{row['id']}:{row['content_hash']}" for row in materials)
                )
            )
            existing = connection.execute(
                """
                SELECT a.id article_id
                FROM articles a
                JOIN article_versions av ON av.id = a.current_version_id
                WHERE a.topic_id = ? AND av.material_set_hash = ?
                ORDER BY av.created_at DESC LIMIT 1
                """,
                (topic_id, material_set_hash),
            ).fetchone()
            if existing:
                result = self.get_article(existing["article_id"])
                assert result is not None
                result["reused"] = True
                return result

            now = datetime.now(timezone.utc)
            article_id = str(uuid.uuid4())
            version_id = str(uuid.uuid4())
            title = f"{topic['name']}：{now.date().isoformat()} 增量观察"
            summary = (
                f"基于 {len(materials)} 条新增素材整理的规则版草稿；"
                "所有条目保留原始来源，等待人工补充判断与论证。"
            )
            body = self._render_rule_article(title, summary, materials)
            artifact = (
                self.path.parent
                / "artifacts"
                / "articles"
                / article_id
                / version_id
                / "article.md"
            )
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(body, encoding="utf-8")
            created_at = now.isoformat()
            connection.execute(
                """
                INSERT INTO articles (
                    id, topic_id, article_type, slug, status,
                    current_version_id, created_at, updated_at
                ) VALUES (?, ?, 'incremental-digest', ?, 'draft', ?, ?, ?)
                """,
                (
                    article_id,
                    topic_id,
                    f"{topic['slug']}-{now.date().isoformat()}",
                    version_id,
                    created_at,
                    created_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO article_versions (
                    id, article_id, version, origin, title, summary,
                    body_markdown, material_set_hash, composer_id,
                    composer_version, created_at
                ) VALUES (?, ?, 1, 'rule', ?, ?, ?, ?, 'rule-evidence', '1', ?)
                """,
                (
                    version_id,
                    article_id,
                    title,
                    summary,
                    body,
                    material_set_hash,
                    created_at,
                ),
            )
            for order, row in enumerate(materials, start=1):
                connection.execute(
                    """
                    INSERT INTO article_evidence (
                        article_version_id, event_id, material_id,
                        claim_id, citation_order, note
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        row["event_id"],
                        row["id"],
                        f"signal-{order}",
                        order,
                        "rule-selected topic evidence",
                    ),
                )
            connection.execute(
                """
                INSERT INTO article_artifacts (
                    id, article_version_id, kind, path, sha256, created_at
                ) VALUES (?, ?, 'blog-markdown', ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    version_id,
                    str(artifact),
                    self._sha256(body),
                    created_at,
                ),
            )
        result = self.get_article(article_id)
        assert result is not None
        result["reused"] = False
        return result

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT a.id article_id, a.status, a.article_type, a.topic_id,
                    t.name topic_name, av.id version_id, av.version,
                    av.title, av.summary, av.body_markdown,
                    av.material_set_hash, av.created_at,
                    aa.path artifact_path,
                    COUNT(DISTINCT ae.material_id) evidence_count
                FROM articles a
                JOIN article_versions av ON av.id = a.current_version_id
                JOIN topics t ON t.id = a.topic_id
                LEFT JOIN article_artifacts aa ON aa.article_version_id = av.id
                LEFT JOIN article_evidence ae ON ae.article_version_id = av.id
                WHERE a.id = ?
                GROUP BY a.id, av.id
                """,
                (article_id,),
            ).fetchone()
            if row is None:
                return None
            evidence_rows = connection.execute(
                """
                SELECT ae.claim_id, ae.citation_order, ae.note,
                    m.id material_id, m.title, m.author, m.platform,
                    m.canonical_url, m.quality_score
                FROM article_evidence ae
                JOIN materials m ON m.id = ae.material_id
                WHERE ae.article_version_id = ?
                ORDER BY ae.citation_order
                """,
                (row["version_id"],),
            ).fetchall()
        result = self._article_result(row, reused=False)
        result["evidence"] = [dict(item) for item in evidence_rows]
        return result

    def list_articles(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.id article_id, a.status, a.article_type, a.topic_id,
                    t.name topic_name, av.id version_id, av.version,
                    av.title, av.summary, av.body_markdown,
                    av.material_set_hash, av.created_at,
                    aa.path artifact_path,
                    COUNT(DISTINCT ae.material_id) evidence_count
                FROM articles a
                JOIN article_versions av ON av.id = a.current_version_id
                JOIN topics t ON t.id = a.topic_id
                LEFT JOIN article_artifacts aa ON aa.article_version_id = av.id
                LEFT JOIN article_evidence ae ON ae.article_version_id = av.id
                GROUP BY a.id, av.id
                ORDER BY a.updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._article_result(row, reused=False) for row in rows]

    def create_article_version(
        self,
        article_id: str,
        *,
        title: str,
        summary: str,
        body_markdown: str,
        expected_version: int,
    ) -> dict[str, Any]:
        title = self._clean_text(title, single_line=True)
        summary = self._clean_text(summary)
        body_markdown = self._clean_text(body_markdown)
        if not title or not body_markdown:
            raise ValueError("title and body_markdown must not be empty")
        with self._connect() as connection:
            current = connection.execute(
                """
                SELECT a.current_version_id, a.status, av.version,
                    av.material_set_hash, av.composer_id, av.composer_version
                FROM articles a
                JOIN article_versions av ON av.id = a.current_version_id
                WHERE a.id = ?
                """,
                (article_id,),
            ).fetchone()
            if current is None:
                raise ValueError("article not found")
            if int(current["version"]) != expected_version:
                raise ValueError("article version changed; reload before saving")
            version_id = str(uuid.uuid4())
            version = expected_version + 1
            now = datetime.now(timezone.utc).isoformat()
            artifact = (
                self.path.parent
                / "artifacts"
                / "articles"
                / article_id
                / version_id
                / "article.md"
            )
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(body_markdown, encoding="utf-8")
            connection.execute(
                """
                INSERT INTO article_versions (
                    id, article_id, version, parent_version_id, origin,
                    title, summary, body_markdown, material_set_hash,
                    composer_id, composer_version, created_at
                ) VALUES (?, ?, ?, ?, 'manual', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    article_id,
                    version,
                    current["current_version_id"],
                    title,
                    summary,
                    body_markdown,
                    current["material_set_hash"],
                    current["composer_id"],
                    current["composer_version"],
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO article_evidence (
                    article_version_id, event_id, material_id,
                    claim_id, citation_order, note
                )
                SELECT ?, event_id, material_id, claim_id, citation_order, note
                FROM article_evidence WHERE article_version_id = ?
                """,
                (version_id, current["current_version_id"]),
            )
            connection.execute(
                """
                INSERT INTO article_artifacts (
                    id, article_version_id, kind, path, sha256, created_at
                ) VALUES (?, ?, 'blog-markdown', ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    version_id,
                    str(artifact),
                    self._sha256(body_markdown),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE articles
                SET current_version_id = ?, status = 'review', updated_at = ?
                WHERE id = ?
                """,
                (version_id, now, article_id),
            )
            self._audit(
                connection,
                action="article.version-created",
                object_type="article",
                object_id=article_id,
                before={"version": expected_version, "status": current["status"]},
                after={"version": version, "status": "review"},
            )
        result = self.get_article(article_id)
        assert result is not None
        return result

    def approve_article_version(self, version_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT a.id article_id, a.status
                FROM articles a
                WHERE a.current_version_id = ?
                """,
                (version_id,),
            ).fetchone()
            if row is None:
                raise ValueError("only the current article version can be approved")
            connection.execute(
                "UPDATE articles SET status = 'approved', updated_at = ? WHERE id = ?",
                (now, row["article_id"]),
            )
            self._audit(
                connection,
                action="article.approved",
                object_type="article",
                object_id=row["article_id"],
                before={"status": row["status"]},
                after={"status": "approved", "version_id": version_id},
            )
        result = self.get_article(row["article_id"])
        assert result is not None
        return result

    def create_publication_jobs(
        self, version_id: str, platforms: Iterable[str]
    ) -> list[dict[str, Any]]:
        requested = tuple(dict.fromkeys(platforms))
        adapters = create_delivery_adapters()
        unsupported = sorted(set(requested) - set(adapters))
        if unsupported:
            raise ValueError(f"unsupported publication platforms: {', '.join(unsupported)}")
        if not requested:
            raise ValueError("at least one publication platform is required")
        now = datetime.now(timezone.utc).isoformat()
        job_ids: list[str] = []
        with self._connect() as connection:
            version = connection.execute(
                """
                SELECT a.id article_id, a.status
                FROM article_versions av
                JOIN articles a ON a.id = av.article_id
                WHERE av.id = ? AND a.current_version_id = av.id
                """,
                (version_id,),
            ).fetchone()
            if version is None or version["status"] != "approved":
                raise ValueError("approve the current article version before distribution")
            for platform in requested:
                adapter = adapters[platform]
                idempotency_key = self._sha256(f"{version_id}:{platform}")
                existing = connection.execute(
                    """
                    SELECT id FROM publication_jobs
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()
                if existing:
                    job_ids.append(existing["id"])
                    continue
                job_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO publication_jobs (
                        id, article_version_id, platform, adapter_id,
                        status, idempotency_key, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
                    """,
                    (
                        job_id,
                        version_id,
                        platform,
                        adapter.manifest.id,
                        idempotency_key,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO publication_records(job_id, status)
                    VALUES (?, 'pending')
                    """,
                    (job_id,),
                )
                job_ids.append(job_id)
                self._audit(
                    connection,
                    action="publication.created",
                    object_type="publication_job",
                    object_id=job_id,
                    before={},
                    after={"platform": platform, "status": "pending"},
                )
        jobs = [self.get_publication(job_id) for job_id in job_ids]
        return [job for job in jobs if job is not None]

    def list_publications(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                self._publication_query() + " ORDER BY pj.updated_at DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
            return [self._publication_dict(connection, row) for row in rows]

    def get_publication(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                self._publication_query() + " WHERE pj.id = ?",
                (job_id,),
            ).fetchone()
            return self._publication_dict(connection, row) if row else None

    def prepare_publication(self, job_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                self._publication_query() + " WHERE pj.id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise ValueError("publication job not found")
            if row["status"] == "published":
                raise ValueError("published jobs cannot be prepared again")
        adapter = create_delivery_adapters()[row["platform"]]
        output_directory = self._publication_root(job_id) / row["platform"]
        ledger_path = self.path.parent / ".publish" / "xhs-ledger.json"
        article = self._payload(row)
        try:
            artifacts = adapter.prepare(article, output_directory, ledger_path)
        except Exception as exc:
            self._mark_publication_failed(job_id, str(exc))
            raise
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            for artifact in artifacts:
                self._upsert_publication_artifact(connection, job_id, artifact, now)
            connection.execute(
                """
                UPDATE publication_jobs
                SET status = 'prepared', attempt_count = attempt_count + 1,
                    updated_at = ?, last_error = NULL
                WHERE id = ?
                """,
                (now, job_id),
            )
            connection.execute(
                """
                UPDATE publication_records
                SET status = 'prepared', prepared_at = ? WHERE job_id = ?
                """,
                (now, job_id),
            )
            self._audit(
                connection,
                action="publication.prepared",
                object_type="publication_job",
                object_id=job_id,
                before={"status": row["status"]},
                after={"status": "prepared", "artifacts": len(artifacts)},
            )
        result = self.get_publication(job_id)
        assert result is not None
        return result

    def preview_publication(self, job_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                self._publication_query() + " WHERE pj.id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise ValueError("publication job not found")
            if row["status"] not in {"prepared", "previewed"}:
                raise ValueError("prepare the publication before previewing")
            artifact_rows = connection.execute(
                """
                SELECT kind, path, metadata_json
                FROM publication_artifacts WHERE job_id = ?
                """,
                (job_id,),
            ).fetchall()
        artifacts = tuple(
            ArtifactSpec(
                item["kind"],
                Path(item["path"]),
                json.loads(item["metadata_json"]),
            )
            for item in artifact_rows
        )
        adapter = create_delivery_adapters()[row["platform"]]
        preview = adapter.preview(
            self._payload(row), self._publication_root(job_id) / row["platform"], artifacts
        )
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            self._upsert_publication_artifact(connection, job_id, preview, now)
            connection.execute(
                """
                UPDATE publication_jobs SET status = 'previewed', updated_at = ?
                WHERE id = ?
                """,
                (now, job_id),
            )
            connection.execute(
                """
                UPDATE publication_records
                SET status = 'previewed', previewed_at = ? WHERE job_id = ?
                """,
                (now, job_id),
            )
            self._audit(
                connection,
                action="publication.previewed",
                object_type="publication_job",
                object_id=job_id,
                before={"status": row["status"]},
                after={"status": "previewed"},
            )
        result = self.get_publication(job_id)
        assert result is not None
        return result

    def record_publication(
        self,
        job_id: str,
        *,
        external_url: str,
        confirmation_note: str,
        confirmed_by: str = "local-user",
    ) -> dict[str, Any]:
        if not external_url.startswith(("http://", "https://")):
            raise ValueError("external_url must be an absolute HTTP URL")
        if not confirmation_note.strip():
            raise ValueError("confirmation_note is required")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT pj.status, pj.platform, pa.path manifest_path
                FROM publication_jobs pj
                LEFT JOIN publication_artifacts pa
                    ON pa.job_id = pj.id AND pa.kind = 'manifest'
                WHERE pj.id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                raise ValueError("publication job not found")
            if row["status"] != "previewed":
                raise ValueError("preview the publication before recording it published")
            if row["platform"] == "xiaohongshu":
                if not row["manifest_path"]:
                    raise ValueError("Xiaohongshu publication manifest is missing")
                mark_xiaohongshu_published(
                    Path(row["manifest_path"]), external_url
                )
            connection.execute(
                """
                UPDATE publication_jobs SET status = 'published', updated_at = ?
                WHERE id = ?
                """,
                (now, job_id),
            )
            connection.execute(
                """
                UPDATE publication_records
                SET status = 'published', external_url = ?, published_at = ?,
                    confirmed_by = ?, confirmation_note = ?
                WHERE job_id = ?
                """,
                (
                    external_url,
                    now,
                    confirmed_by,
                    confirmation_note.strip(),
                    job_id,
                ),
            )
            self._audit(
                connection,
                action="publication.recorded-published",
                object_type="publication_job",
                object_id=job_id,
                before={"status": "previewed"},
                after={"status": "published", "external_url": external_url},
            )
        result = self.get_publication(job_id)
        assert result is not None
        return result

    def artifact_path(self, artifact_id: str) -> Path | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT path FROM publication_artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()
        if row is None:
            return None
        path = Path(row["path"]).resolve()
        root = (self.path.parent / "artifacts").resolve()
        if path != root and root not in path.parents:
            raise ValueError("artifact path escaped workspace root")
        return path

    def begin_run(self, trigger: str, config_hash: str) -> str:
        run_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_runs (
                    id, trigger, started_at, status, config_hash, summary_json
                ) VALUES (?, ?, ?, 'running', ?, '{}')
                """,
                (run_id, trigger, datetime.now(timezone.utc).isoformat(), config_hash),
            )
        return run_id

    def record_target_run(
        self,
        run_id: str,
        target_id: str,
        *,
        status: str,
        fetched: int = 0,
        error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO target_runs (
                    id, run_id, target_id, status, fetched,
                    started_at, finished_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    run_id,
                    target_id,
                    status,
                    fetched,
                    now,
                    now,
                    error,
                ),
            )

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        summary: dict[str, Any],
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_runs
                SET finished_at = ?, status = ?, summary_json = ?, error = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    json.dumps(summary, ensure_ascii=False, sort_keys=True),
                    error,
                    run_id,
                ),
            )

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, trigger, status, started_at, finished_at,
                    summary_json, error
                FROM ingestion_runs
                ORDER BY started_at DESC LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._run_dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @classmethod
    def _apply_migrations(cls, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        version = cls._scalar(
            connection, "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        )
        if version < 1:
            connection.executescript(
                """
            CREATE TABLE ingestion_runs (
                id TEXT PRIMARY KEY,
                trigger TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                config_hash TEXT NOT NULL DEFAULT '',
                summary_json TEXT NOT NULL DEFAULT '{}',
                error TEXT
            );
            CREATE TABLE target_runs (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES ingestion_runs(id) ON DELETE CASCADE,
                target_id TEXT NOT NULL,
                status TEXT NOT NULL,
                cursor_before TEXT,
                cursor_after TEXT,
                fetched INTEGER NOT NULL DEFAULT 0,
                inserted INTEGER NOT NULL DEFAULT 0,
                updated INTEGER NOT NULL DEFAULT 0,
                duplicates INTEGER NOT NULL DEFAULT 0,
                filtered INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                error TEXT
            );
            CREATE TABLE source_cursors (
                target_id TEXT PRIMARY KEY,
                cursor_type TEXT NOT NULL,
                cursor_value_json TEXT NOT NULL,
                watermark_at TEXT,
                last_success_at TEXT,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE materials (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                external_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                author TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                published_at TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                quality_score REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'new',
                tags_json TEXT NOT NULL DEFAULT '[]',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                media_json TEXT NOT NULL DEFAULT '[]',
                raw_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(platform, external_id)
            );
            CREATE TABLE material_sources (
                material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                target_id TEXT NOT NULL,
                first_seen_run_id TEXT,
                PRIMARY KEY(material_id, target_id)
            );
            CREATE TABLE material_fingerprints (
                material_id TEXT PRIMARY KEY REFERENCES materials(id) ON DELETE CASCADE,
                url_hash TEXT,
                content_hash TEXT NOT NULL,
                simhash64 INTEGER,
                normalizer_version INTEGER NOT NULL
            );
            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                canonical_title TEXT NOT NULL,
                event_type TEXT NOT NULL,
                entities_json TEXT NOT NULL DEFAULT '[]',
                event_time TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE event_materials (
                event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                confidence REAL NOT NULL,
                reason_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY(event_id, material_id)
            );
            CREATE TABLE topics (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE topic_materials (
                topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                relevance REAL NOT NULL,
                novelty REAL NOT NULL,
                quality REAL NOT NULL,
                status TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                reviewed_at TEXT,
                PRIMARY KEY(topic_id, event_id)
            );
            CREATE INDEX idx_materials_inbox
                ON materials(quality_score DESC, first_seen_at DESC, id DESC);
            CREATE INDEX idx_materials_platform ON materials(platform);
            CREATE INDEX idx_topic_materials_topic ON topic_materials(topic_id);
            CREATE INDEX idx_target_runs_run ON target_runs(run_id);
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE materials_fts USING fts5(
                    material_id UNINDEXED, title, content, author,
                    tokenize = 'unicode61'
                )
                """
            )
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (1, ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )
            version = 1
        if version < 2:
            connection.executescript(
                """
                CREATE TABLE articles (
                    id TEXT PRIMARY KEY,
                    topic_id TEXT NOT NULL REFERENCES topics(id),
                    article_type TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_version_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE article_versions (
                    id TEXT PRIMARY KEY,
                    article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL,
                    parent_version_id TEXT,
                    origin TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    body_markdown TEXT NOT NULL,
                    material_set_hash TEXT NOT NULL,
                    composer_id TEXT NOT NULL,
                    composer_version TEXT NOT NULL,
                    model TEXT,
                    prompt_hash TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(article_id, version)
                );
                CREATE TABLE article_evidence (
                    article_version_id TEXT NOT NULL
                        REFERENCES article_versions(id) ON DELETE CASCADE,
                    event_id TEXT NOT NULL REFERENCES events(id),
                    material_id TEXT NOT NULL REFERENCES materials(id),
                    claim_id TEXT NOT NULL,
                    citation_order INTEGER NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(article_version_id, claim_id, material_id)
                );
                CREATE TABLE article_artifacts (
                    id TEXT PRIMARY KEY,
                    article_version_id TEXT NOT NULL
                        REFERENCES article_versions(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX idx_articles_topic ON articles(topic_id, updated_at DESC);
                CREATE INDEX idx_article_evidence_version
                    ON article_evidence(article_version_id, citation_order);
                """
            )
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (2, ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )
            version = 2
        if version < 3:
            connection.executescript(
                """
                CREATE TABLE publication_jobs (
                    id TEXT PRIMARY KEY,
                    article_version_id TEXT NOT NULL
                        REFERENCES article_versions(id),
                    platform TEXT NOT NULL,
                    adapter_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_error TEXT,
                    UNIQUE(article_version_id, platform)
                );
                CREATE TABLE publication_artifacts (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL
                        REFERENCES publication_jobs(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    UNIQUE(job_id, kind)
                );
                CREATE TABLE publication_records (
                    job_id TEXT PRIMARY KEY
                        REFERENCES publication_jobs(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    external_draft_id TEXT,
                    external_url TEXT,
                    prepared_at TEXT,
                    previewed_at TEXT,
                    published_at TEXT,
                    confirmed_by TEXT,
                    confirmation_note TEXT
                );
                CREATE TABLE audit_events (
                    id TEXT PRIMARY KEY,
                    actor_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    before_json TEXT NOT NULL DEFAULT '{}',
                    after_json TEXT NOT NULL DEFAULT '{}',
                    run_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX idx_publication_jobs_status
                    ON publication_jobs(status, updated_at DESC);
                CREATE INDEX idx_audit_object
                    ON audit_events(object_type, object_id, created_at DESC);
                """
            )
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (3, ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )

    @classmethod
    def _import_topic_annotation(
        cls,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        event_id: str,
        now: str,
    ) -> None:
        annotations = json.loads(row["annotations_json"] or "{}")
        topic_name = str(annotations.get("topic", "")).strip()
        if not topic_name:
            return
        topic_id = cls._stable_id("topic", topic_name.casefold())
        connection.execute(
            """
            INSERT OR IGNORE INTO topics (
                id, slug, name, description, enabled, created_at
            ) VALUES (?, ?, ?, '', 1, ?)
            """,
            (topic_id, cls._slug(topic_name), topic_name, now),
        )
        relevance = float(annotations.get("relevance", 100)) / 100.0
        connection.execute(
            """
            INSERT OR IGNORE INTO topic_materials (
                topic_id, event_id, relevance, novelty, quality,
                status, assigned_at
            ) VALUES (?, ?, ?, 1.0, 1.0, 'accepted', ?)
            """,
            (topic_id, event_id, max(0.0, min(relevance, 1.0)), now),
        )

    @staticmethod
    def _replace_fts(
        connection: sqlite3.Connection,
        material_id: str,
        title: str,
        content: str,
        author: str,
    ) -> None:
        connection.execute(
            "DELETE FROM materials_fts WHERE material_id = ?", (material_id,)
        )
        connection.execute(
            """
            INSERT INTO materials_fts(material_id, title, content, author)
            VALUES (?, ?, ?, ?)
            """,
            (material_id, title, content, author),
        )

    @staticmethod
    def _material_summary(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "platform": row["platform"],
            "external_id": row["external_id"],
            "author": row["author"],
            "title": row["title"],
            "excerpt": row["content"][:280],
            "url": row["canonical_url"],
            "published_at": row["published_at"],
            "first_seen_at": row["first_seen_at"],
            "priority": int(row["priority"]),
            "quality_score": float(row["quality_score"]),
            "status": row["status"],
            "personal": int(row["priority"]) >= 100,
            "tags": json.loads(row["tags_json"]),
            "topics": (row["topics"] or "").split(",") if row["topics"] else [],
            "topic_ids": (
                (row["topic_ids"] or "").split(",") if row["topic_ids"] else []
            ),
            "source_ids": (
                (row["source_ids"] or "").split(",") if row["source_ids"] else []
            ),
            "event_count": int(row["event_count"]),
        }

    @classmethod
    def _material_detail(cls, row: sqlite3.Row) -> dict[str, Any]:
        result = cls._material_summary(row)
        result.update(
            {
                "content": row["content"],
                "object_type": row["object_type"],
                "metrics": json.loads(row["metrics_json"]),
                "media": json.loads(row["media_json"]),
                "fingerprints": {
                    "url_hash": row["url_hash"],
                    "content_hash": row["content_hash"],
                    "normalizer_version": row["normalizer_version"],
                },
            }
        )
        return result

    @staticmethod
    def _render_rule_article(
        title: str, summary: str, materials: Iterable[sqlite3.Row]
    ) -> str:
        sections = [f"# {title}", "", summary, "", "## 本期新增线索", ""]
        for order, row in enumerate(materials, start=1):
            item_title = row["title"] or row["content"][:100]
            excerpt = re.sub(r"\s+", " ", row["content"]).strip()[:420]
            source = f"{row['author']} · {row['platform']}"
            if row["canonical_url"]:
                source = f"[{source}]({row['canonical_url']})"
            sections.extend(
                [
                    f"### {order}. {item_title}",
                    "",
                    excerpt,
                    "",
                    f"- 来源：{source}",
                    f"- 相关度：{round(float(row['quality_score']))}",
                    f"- Evidence ID：`{row['id']}`",
                    "",
                ]
            )
        sections.extend(
            [
                "## 后续编辑建议",
                "",
                "- 核对跨来源是否描述同一事件，必要时合并证据。",
                "- 补充源码、发布说明或 benchmark，避免只复述社交媒体观点。",
                "- 删除与专题主线无关的低价值条目，再进入人工审阅。",
                "",
            ]
        )
        return "\n".join(sections)

    @staticmethod
    def _article_result(row: sqlite3.Row, *, reused: bool) -> dict[str, Any]:
        keys = set(row.keys())
        result: dict[str, Any] = {
            "article_id": row["article_id"],
            "version_id": row["version_id"],
            "title": row["title"],
            "summary": row["summary"],
            "body_markdown": row["body_markdown"],
            "artifact_path": row["artifact_path"],
            "reused": reused,
        }
        optional = {
            "status": "status",
            "article_type": "article_type",
            "topic_id": "topic_id",
            "topic_name": "topic_name",
            "version": "version",
            "material_set_hash": "material_set_hash",
            "created_at": "created_at",
            "evidence_count": "evidence_count",
        }
        for target, source in optional.items():
            if source in keys:
                result[target] = row[source]
        return result

    @staticmethod
    def _publication_query() -> str:
        return """
            SELECT pj.id job_id, pj.article_version_id, pj.platform,
                pj.adapter_id, pj.status, pj.attempt_count,
                pj.created_at, pj.updated_at, pj.last_error,
                pr.external_url, pr.prepared_at, pr.previewed_at,
                pr.published_at, pr.confirmed_by, pr.confirmation_note,
                a.id article_id, a.status article_status,
                av.title, av.summary, av.body_markdown,
                t.name topic_name
            FROM publication_jobs pj
            JOIN publication_records pr ON pr.job_id = pj.id
            JOIN article_versions av ON av.id = pj.article_version_id
            JOIN articles a ON a.id = av.article_id
            JOIN topics t ON t.id = a.topic_id
        """

    @staticmethod
    def _payload(row: sqlite3.Row) -> ArticlePayload:
        return ArticlePayload(
            article_id=row["article_id"],
            version_id=row["article_version_id"],
            title=row["title"],
            summary=row["summary"],
            body_markdown=row["body_markdown"],
            topic=row["topic_name"],
        )

    def _publication_dict(
        self, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> dict[str, Any]:
        artifact_rows = connection.execute(
            """
            SELECT id, kind, path, sha256, metadata_json, created_at
            FROM publication_artifacts WHERE job_id = ? ORDER BY kind
            """,
            (row["job_id"],),
        ).fetchall()
        adapter = create_delivery_adapters()[row["platform"]]
        return {
            "job_id": row["job_id"],
            "article_version_id": row["article_version_id"],
            "article_id": row["article_id"],
            "article_title": row["title"],
            "topic_name": row["topic_name"],
            "platform": row["platform"],
            "adapter_id": row["adapter_id"],
            "capabilities": list(adapter.manifest.capabilities),
            "manual_confirmation_required": (
                adapter.manifest.manual_confirmation_required
            ),
            "status": row["status"],
            "attempt_count": int(row["attempt_count"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_error": row["last_error"],
            "prepared_at": row["prepared_at"],
            "previewed_at": row["previewed_at"],
            "published_at": row["published_at"],
            "external_url": row["external_url"],
            "confirmed_by": row["confirmed_by"],
            "confirmation_note": row["confirmation_note"],
            "artifacts": [
                {
                    "id": item["id"],
                    "kind": item["kind"],
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "metadata": json.loads(item["metadata_json"]),
                    "created_at": item["created_at"],
                    "url": f"/api/artifacts/{item['id']}",
                }
                for item in artifact_rows
            ],
        }

    def _publication_root(self, job_id: str) -> Path:
        return self.path.parent / "artifacts" / "publications" / job_id

    @classmethod
    def _upsert_publication_artifact(
        cls,
        connection: sqlite3.Connection,
        job_id: str,
        artifact: ArtifactSpec,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO publication_artifacts (
                id, job_id, kind, path, sha256, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, kind) DO UPDATE SET
                path = excluded.path,
                sha256 = excluded.sha256,
                metadata_json = excluded.metadata_json,
                created_at = excluded.created_at
            """,
            (
                str(uuid.uuid4()),
                job_id,
                artifact.kind,
                str(artifact.path.resolve()),
                hashlib.sha256(artifact.path.read_bytes()).hexdigest(),
                json.dumps(artifact.metadata, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )

    def _mark_publication_failed(self, job_id: str, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE publication_jobs
                SET status = 'failed', attempt_count = attempt_count + 1,
                    updated_at = ?, last_error = ? WHERE id = ?
                """,
                (now, error, job_id),
            )
            connection.execute(
                """
                UPDATE publication_records SET status = 'failed' WHERE job_id = ?
                """,
                (job_id,),
            )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        *,
        action: str,
        object_type: str,
        object_id: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events (
                id, actor_type, actor_id, action, object_type, object_id,
                before_json, after_json, created_at
            ) VALUES (?, 'human', 'local-user', ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                action,
                object_type,
                object_id,
                json.dumps(before, ensure_ascii=False, sort_keys=True),
                json.dumps(after, ensure_ascii=False, sort_keys=True),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    @staticmethod
    def _run_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "status": row["status"],
            "trigger": row["trigger"] if "trigger" in row.keys() else "collect",
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "summary": json.loads(row["summary_json"] or "{}"),
            "error": row["error"],
        }

    @staticmethod
    def _canonical_url(value: str) -> str:
        if not value:
            return ""
        parts = urlsplit(value.strip())
        filtered_query = [
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in {"ref", "source", "s"}
        ]
        path = parts.path.rstrip("/") or "/"
        return urlunsplit(
            (
                parts.scheme.casefold(),
                parts.netloc.casefold(),
                path,
                urlencode(filtered_query),
                "",
            )
        )

    @classmethod
    def _content_hash(cls, title: str, content: str) -> str:
        normalized = re.sub(r"\s+", " ", f"{title}\n{content}").strip().casefold()
        return cls._sha256(normalized)

    @staticmethod
    def _clean_text(value: str, *, single_line: bool = False) -> str:
        decoded = html.unescape(value or "")
        cleaned = "".join(
            character
            for character in decoded
            if character in {"\n", "\t"} or ord(character) >= 32
        )
        if single_line:
            return re.sub(r"\s+", " ", cleaned).strip()
        return cleaned.strip()

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _stable_id(namespace: str, *values: str) -> str:
        payload = "\0".join((namespace, *values))
        return str(uuid.uuid5(uuid.NAMESPACE_URL, payload))

    @classmethod
    def _slug(cls, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return slug or f"topic-{cls._sha256(value)[:10]}"

    @staticmethod
    def _fts_query(value: str) -> str:
        tokens = re.findall(r"[\w\-]+", value, flags=re.UNICODE)
        if not tokens:
            raise ValueError("query must contain searchable characters")
        return " AND ".join(f'"{token}"' for token in tokens[:12])

    @staticmethod
    def _encode_cursor(score: float, seen_at: str, material_id: str) -> str:
        payload = json.dumps([score, seen_at, material_id], separators=(",", ":"))
        return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(value: str) -> tuple[float, str, str]:
        try:
            padding = "=" * (-len(value) % 4)
            score, seen_at, material_id = json.loads(
                base64.urlsafe_b64decode(value + padding).decode()
            )
            return float(score), str(seen_at), str(material_id)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid material cursor") from exc

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _scalar(connection: sqlite3.Connection, sql: str) -> int:
        row = connection.execute(sql).fetchone()
        return int(row[0])
