"""Behavioral tests: semantic identities, progress evidence, and review scheduling."""

import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace
from datetime import date
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("engineering_daily", Path(__file__).parents[1] / "engineering_daily.py")
daily = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(daily)


class DailyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("docs/daily/projects/highway/curriculum.json", {
            "max_pending": 2, "units": [{"id": f"highway-{i:02}", "novelty": "boundary"} for i in range(1, 5)]})
        for path in ("docs/daily/2026-10-13.md", "docs/daily/2026-10-14.md",
                     "docs/daily/2026-10-15.md", "docs/daily/lesson.md", "docs/daily/question.md",
                     ".local/engineering-daily/evidence.md"):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("actual evidence\n")

    def write(self, relative, value):
        daily.write_json(self.root / relative, value)

    def record(self, day="2026-10-13", unit="highway-01", skill="jvm.publication"):
        return {"schema_version": 1, "date": day, "timezone": "Asia/Shanghai",
                "cutoff_at": f"{day}T18:00:00+08:00", "report": f"docs/daily/{day}.md",
                "lesson": {"unit_id": unit, "mode": "new", "novelty": "new boundary", "path": "docs/daily/lesson.md"},
                "exercise": {"id": "exercise-" + unit, "skill_key": skill, "mode": "new", "path": "docs/daily/question.md"},
                "news": [], "recall": None}

    def issue(self, record):
        path = self.root / f"docs/daily/editions/{record['date']}.json"
        daily.write_json(path, record)
        return path

    def event(self, stage="open", delta="tail-bound"):
        return {"event_id": "github:org/repo:pr:42", "stage": {"pr": stage},
                "delta_key": delta, "delta": "new correctness boundary", "event_date": "2026-10-13",
                "sources": ["https://github.com/org/repo/pull/42"]}

    def respond(self, day, level="practiced", result="correct"):
        return daily.feedback(self.root, Namespace(id="highway-01", date=date.fromisoformat(day),
                              level=level, result=result, evidence=".local/engineering-daily/evidence.md"))

    def test_same_day_rerun_is_idempotent(self):
        path = self.issue(self.record())
        self.assertTrue(daily.check(self.root, path)["ok"])
        self.assertTrue(daily.check(self.root, path)["ok"])

    def test_repeated_news_rejected_but_state_transition_allowed(self):
        first = self.record()
        first["news"] = [self.event()]
        self.issue(first)
        second = self.record("2026-10-14", "highway-02", "linux.memory")
        second["news"] = [dict(self.event(), previous=first["report"])]
        path = self.issue(second)
        with self.assertRaisesRegex(ValueError, "没有变化"):
            daily.check(self.root, path)
        second["news"] = [dict(self.event("merged", "released-fix"), previous=first["report"])]
        self.issue(second)
        self.assertTrue(daily.check(self.root, path)["ok"])

    def test_legacy_mirror_links_share_one_identity(self):
        path = self.root / "docs/github-daily/2026-10-12.md"
        path.parent.mkdir(parents=True)
        path.write_text("https://github.com/Org/Repo/pull/42#comment-1\nhttps://github.com/org/repo/pull/42\n")
        events = daily.legacy_events(self.root, date(2026, 10, 13))
        self.assertEqual(events, {"github:org/repo:pr:42": ["docs/github-daily/2026-10-12.md"]})
        record = self.record()
        record["news"] = [self.event("merged")]
        with self.assertRaisesRegex(ValueError, "旧报道"):
            daily.check(self.root, self.issue(record))

    def test_renaming_question_does_not_avoid_skill_dedup(self):
        self.issue(self.record())
        next_record = self.record("2026-10-14", "highway-02")
        with self.assertRaisesRegex(ValueError, "同能力"):
            daily.check(self.root, self.issue(next_record))
        next_record["exercise"].update(mode="variant", previous="docs/daily/question.md", reason="adds concurrent mutation")
        self.assertTrue(daily.check(self.root, self.issue(next_record))["ok"])

    def test_backlog_holds_new_course(self):
        self.issue(self.record())
        self.issue(self.record("2026-10-14", "highway-02", "linux.memory"))
        result = daily.plan(self.root, date(2026, 10, 15))
        self.assertEqual(result["selection"]["mode"], "remediation")
        self.assertEqual(result["pending_practice"], ["highway-01", "highway-02"])
        with self.assertRaisesRegex(ValueError, "补救"):
            daily.check(self.root, self.issue(self.record("2026-10-15", "highway-03", "cpp.lifetime")))
        self.respond("2026-10-14")
        self.assertEqual(daily.plan(self.root, date(2026, 10, 14))["selection"]["mode"], "new")

    def test_read_confirmation_does_not_mark_practice(self):
        self.issue(self.record())
        response = self.respond("2026-10-13", "read", None)
        self.assertEqual(response["level"], "read")
        self.assertNotIn("next_review", response)
        self.assertEqual(daily.plan(self.root, date(2026, 10, 14))["pending_practice"], ["highway-01"])

    def test_intervals_are_anchored_and_early_correct_does_not_consume_review(self):
        self.issue(self.record())
        self.assertEqual(self.respond("2026-10-13")["next_review"], "2026-10-14")
        self.assertEqual(self.respond("2026-10-13")["next_review"], "2026-10-14")
        self.assertEqual(self.respond("2026-10-14")["next_review"], "2026-10-16")
        self.assertEqual(self.respond("2026-10-16")["next_review"], "2026-10-20")
        self.assertEqual(self.respond("2026-10-20")["next_review"], "2026-10-27")

    def test_wrong_answer_resets_schedule_and_missing_response_stays_due(self):
        self.issue(self.record())
        self.respond("2026-10-13")
        self.assertEqual(daily.plan(self.root, date(2026, 10, 20))["due_reviews"][0]["due"], "2026-10-14")
        self.assertEqual(self.respond("2026-10-20", result="wrong")["next_review"], "2026-10-21")

    def test_mastery_requires_prior_practice_and_later_review(self):
        self.issue(self.record())
        with self.assertRaisesRegex(ValueError, "掌握"):
            self.respond("2026-10-13", "mastered")
        for day in ("2026-10-13", "2026-10-14", "2026-10-16", "2026-10-20"):
            self.respond(day)
        self.assertEqual(self.respond("2026-10-20", "mastered")["level"], "mastered")
        self.assertEqual(self.respond("2026-10-21", "read", None)["level"], "mastered")
        self.assertEqual(self.respond("2026-10-21", result="partial")["level"], "practiced")

    def test_private_reference_cannot_enter_public_report(self):
        record = self.record()
        record["lesson"]["path"] = ".local/engineering-daily/evidence.md"
        with self.assertRaisesRegex(ValueError, "公开引用"):
            daily.check(self.root, self.issue(record))

    def test_unissued_feedback_and_future_recall_rejected(self):
        with self.assertRaisesRegex(ValueError, "已经生成"):
            self.respond("2026-10-13")
        record = self.record()
        record["recall"] = {"unit_id": "highway-01", "question": "not previously issued"}
        with self.assertRaisesRegex(ValueError, "旧课"):
            daily.check(self.root, self.issue(record))

    def test_unavailable_source_does_not_hide_other_sources(self):
        self.write("docs/daily/sources.json", {"repositories": [
            {"id": "absent", "url": "https://github.com/org/absent.git", "sparse": ["src"]},
            {"id": "present", "url": "https://github.com/org/present.git", "sparse": ["src"]}]})
        mirror = self.root / ".local/engineering-daily/sources/present"
        (mirror / ".git").mkdir(parents=True)
        (mirror / "src").mkdir()
        def fake_git(path, *arguments, **kwargs):
            if arguments[:2] == ("config", "--get"):
                return "https://github.com/org/present.git"
            if arguments == ("status", "--porcelain"):
                return " M src/edited.cc"
            return "false" if arguments[-1] == "--is-shallow-repository" else "fixed-sha"
        with patch.object(daily, "git", side_effect=fake_git):
            result = daily.sources(self.root, "snapshot", None)
        self.assertEqual([item["status"] for item in result], ["unavailable", "ready"])
        self.assertFalse(result[1]["worktree_clean"])

    def test_dirty_mirror_update_preserves_edits_without_fetch(self):
        self.write("docs/daily/sources.json", {"repositories": [
            {"id": "present", "url": "https://github.com/org/present.git", "sparse": ["src"]}]})
        (self.root / ".local/engineering-daily/sources/present/.git").mkdir(parents=True)
        def fake_git(path, *arguments, **kwargs):
            if arguments[:2] == ("config", "--get"):
                return "https://github.com/org/present.git"
            if arguments == ("status", "--porcelain"):
                return " M edited.cc"
            return "original-sha"
        with patch.object(daily, "git", side_effect=fake_git) as calls:
            result = daily.sources(self.root, "update", None)
        self.assertIn("不自动覆盖", result[0]["error"])
        self.assertFalse(any(call.args[1] == "fetch" for call in calls.call_args_list))


if __name__ == "__main__":
    unittest.main()
