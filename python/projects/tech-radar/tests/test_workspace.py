from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tech_radar.domain import Signal
from tech_radar.storage import SignalStore
from tech_radar.workspace import WorkspaceStore


class WorkspaceStoreTest(unittest.TestCase):
    def test_imports_legacy_signals_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "radar.sqlite3"
            legacy = SignalStore(database)
            legacy.initialize()
            legacy.upsert_many(
                [
                    Signal(
                        external_id="42",
                        source_id="x-liked",
                        platform="twitter",
                        object_type="likes",
                        author="duckdb",
                        title="Join ordering update",
                        content=(
                            "DuckDB join ordering and cardinality estimation update"
                        ),
                        url="https://x.com/duckdb/status/42?utm_source=test",
                        published_at="2026-10-07T01:00:00+00:00",
                        collected_at="2026-10-07T02:00:00+00:00",
                        tags=("database",),
                        priority=100,
                        score=96,
                        annotations={"topic": "数据库与查询引擎", "relevance": 92},
                    )
                ]
            )
            workspace = WorkspaceStore(database)

            first = workspace.initialize()
            second = workspace.synchronize_legacy_signals()
            page = workspace.list_materials(view="personal")
            detail = workspace.get_material(page.items[0]["id"])

            self.assertEqual(1, first.inserted)
            self.assertEqual(0, second.inserted)
            self.assertEqual(1, second.updated)
            self.assertEqual(1, len(page.items))
            self.assertEqual("https://x.com/duckdb/status/42", page.items[0]["url"])
            self.assertEqual(["数据库与查询引擎"], page.items[0]["topics"])
            self.assertIsNotNone(detail)
            self.assertEqual(64, len(detail["fingerprints"]["content_hash"]))

    def test_search_and_manual_topic_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "radar.sqlite3"
            legacy = SignalStore(database)
            legacy.initialize()
            legacy.upsert_many(
                [
                    Signal(
                        external_id="rust-1",
                        source_id="reddit-upvoted",
                        platform="reddit",
                        object_type="upvoted",
                        author="rustacean",
                        title="Rust scheduler internals",
                        content=(
                            "A detailed analysis of Linux scheduler internals in Rust"
                        ),
                        url="https://reddit.com/r/rust/comments/rust-1",
                        published_at=None,
                        score=88,
                    )
                ]
            )
            workspace = WorkspaceStore(database)
            workspace.initialize()

            result = workspace.list_materials(query="scheduler")
            material_id = result.items[0]["id"]
            routed = workspace.route_materials([material_id], "Linux 与系统工程")
            routed_again = workspace.route_materials([material_id], "Linux 与系统工程")
            topic_id = routed["topic_id"]
            draft = workspace.create_rule_article(topic_id)
            repeated_draft = workspace.create_rule_article(topic_id)

            self.assertEqual(1, len(result.items))
            self.assertEqual(1, routed["assigned"])
            self.assertEqual(0, routed_again["assigned"])
            self.assertEqual("Linux 与系统工程", workspace.list_topics()[0]["name"])
            self.assertFalse(draft["reused"])
            self.assertTrue(repeated_draft["reused"])
            self.assertIn("Evidence ID", draft["body_markdown"])
            self.assertTrue(Path(draft["artifact_path"]).is_file())
            self.assertEqual(
                draft["version_id"],
                workspace.get_article(draft["article_id"])["version_id"],
            )

            edited = workspace.create_article_version(
                draft["article_id"],
                title="Linux scheduler internals",
                summary="A reviewed scheduler summary.",
                body_markdown=draft["body_markdown"] + "\n## 人工结论\n\n值得跟进。\n",
                expected_version=1,
            )
            approved = workspace.approve_article_version(edited["version_id"])
            jobs = workspace.create_publication_jobs(
                approved["version_id"], ["blog", "xiaohongshu"]
            )

            self.assertEqual(2, edited["version"])
            self.assertEqual("approved", approved["status"])
            self.assertEqual(2, len(jobs))
            for job in jobs:
                prepared = workspace.prepare_publication(job["job_id"])
                previewed = workspace.preview_publication(job["job_id"])
                self.assertEqual("prepared", prepared["status"])
                self.assertEqual("previewed", previewed["status"])
                self.assertTrue(
                    any(item["kind"] == "preview-html" for item in previewed["artifacts"])
                )
            xhs = next(
                job
                for job in workspace.list_publications()
                if job["platform"] == "xiaohongshu"
            )
            self.assertEqual(
                3,
                sum(item["kind"].startswith("image-") for item in xhs["artifacts"]),
            )
            blog = next(
                job
                for job in workspace.list_publications()
                if job["platform"] == "blog"
            )
            published = workspace.record_publication(
                blog["job_id"],
                external_url="https://example.com/articles/scheduler",
                confirmation_note="Published manually in test.",
            )
            self.assertEqual("published", published["status"])
            xhs_published = workspace.record_publication(
                xhs["job_id"],
                external_url="https://www.xiaohongshu.com/explore/test-note",
                confirmation_note="Published manually in test.",
            )
            manifest = next(
                Path(item["path"])
                for item in xhs_published["artifacts"]
                if item["kind"] == "manifest"
            )
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            ledger = json.loads(
                Path(manifest_data["ledger"]).read_text(encoding="utf-8")
            )
            ledger_record = next(
                item
                for item in ledger["records"]
                if item["fingerprint"] == manifest_data["fingerprint"]
            )
            self.assertEqual("published", xhs_published["status"])
            self.assertEqual("published", ledger_record["status"])
            self.assertEqual(
                "https://www.xiaohongshu.com/explore/test-note",
                ledger_record["external_url"],
            )

    def test_run_lifecycle_is_visible_in_overview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = WorkspaceStore(Path(temporary_directory) / "radar.sqlite3")
            workspace.initialize()
            run_id = workspace.begin_run("test", "config-hash")
            workspace.record_target_run(
                run_id, "fixture", status="succeeded", fetched=2
            )
            workspace.finish_run(
                run_id,
                status="succeeded",
                summary={"fetched": 2, "inserted": 2},
            )

            overview = workspace.overview()

            self.assertEqual(run_id, overview["last_run"]["id"])
            self.assertEqual(2, overview["last_run"]["summary"]["fetched"])


if __name__ == "__main__":
    unittest.main()
