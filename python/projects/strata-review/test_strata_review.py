"""Offline tests: no GPU, API, or external packages required."""

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from strata_review import (
    ReviewError, Source, StrataClient, build_messages, diff_sources, read_source,
    render_markdown, validate_review,
)


class ReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Source("sample.cpp", "int* p = new int(1);\ndelete p;\nreturn *p;\n")

    def response(self) -> dict:
        return {
            "summary": "Use after free.", "limitations": "Not executed.",
            "findings": [{
                "file": "sample.cpp", "line": 3, "category": "lifetime", "severity": "high",
                "evidence": "return *p;", "why": "p was deleted", "repro": "Call under ASan",
            }],
        }

    def test_good_response(self) -> None:
        value = self.response()
        self.assertIs(validate_review(value, [self.source]), value)

    def test_clean_response(self) -> None:
        value = {"summary": "No proven defect.", "limitations": "Only this file.", "findings": []}
        self.assertEqual(validate_review(value, [self.source])["findings"], [])

    def test_invalid_anchors(self) -> None:
        for field, value in [("file", "invented.cpp"), ("line", 0), ("line", True),
                             ("line", 99), ("evidence", "invented code")]:
            with self.subTest(field=field, value=value):
                response = self.response()
                response["findings"][0][field] = value
                with self.assertRaises(ReviewError):
                    validate_review(response, [self.source])

    def test_invalid_shape(self) -> None:
        for value in [[], {}, {"summary": "s", "limitations": "l", "findings": "bad"}]:
            with self.assertRaises(ReviewError):
                validate_review(value, [self.source])
        for key, value in [("category", "unknown"), ("severity", "critical"), ("why", "")]:
            response = self.response()
            response["findings"][0][key] = value
            with self.assertRaises(ReviewError):
                validate_review(response, [self.source])

    def test_numbered_prompt_and_duplicates(self) -> None:
        messages = build_messages([self.source])
        self.assertIn("3: return *p;", messages[1]["content"])
        self.assertIn("untrusted data", messages[0]["content"])
        with self.assertRaises(ReviewError):
            build_messages([self.source, self.source])
        with self.assertRaises(ReviewError):
            build_messages([Source("large.cpp", "a" * 100001)])

    def test_path_boundary_and_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "repo"
            root.mkdir()
            (root / "ok.cpp").write_text("int x;", encoding="utf-8")
            self.assertEqual(read_source(root, "ok.cpp").name, "ok.cpp")
            (base / "outside.cpp").write_text("int x;", encoding="utf-8")
            (root / "outside.cpp").symlink_to(base / "outside.cpp")
            for name in ["../outside.cpp", "outside.cpp", "secret.env", ".hidden.cpp"]:
                with self.assertRaises(ReviewError):
                    read_source(root, name)

    def test_read_only_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def run(*args: str) -> None:
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
            run("init")
            path = root / "sample.cpp"
            path.write_text("int x = 0;\n", encoding="utf-8")
            run("add", "sample.cpp")
            run("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "test")
            path.write_text("int x = 1;\n", encoding="utf-8")
            sources, patch = diff_sources(root, ["sample.cpp"], False)
            self.assertIn("+int x = 1;", patch)
            self.assertEqual(sources[0].text, "int x = 1;\n")
            self.assertEqual(path.read_text(), "int x = 1;\n")
            with self.assertRaises(ReviewError):
                diff_sources(root, [], False)
            with self.assertRaises(ReviewError):
                diff_sources(root, ["../outside.cpp"], False)
            run("add", "sample.cpp")
            path.write_text("int x = 2;\n", encoding="utf-8")
            with self.assertRaises(ReviewError):
                diff_sources(root, ["sample.cpp"], True)

    def test_client_transport(self) -> None:
        client = StrataClient()
        data = {"model": "local", "choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(self.response())}}], "usage": {"total_tokens": 20}}
        opened = MagicMock()
        opened.__enter__.return_value = io.StringIO(json.dumps(data))
        client.opener = MagicMock()
        client.opener.open.return_value = opened
        result = client.review([self.source])
        self.assertEqual(result["review"]["findings"][0]["line"], 3)
        req = client.opener.open.call_args.args[0]
        self.assertEqual(req.full_url, "http://127.0.0.1:8080/v1/chat/completions")
        body = json.loads(req.data)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["reasoning_effort"], "none")

    def test_incomplete_response_not_silently_accepted(self) -> None:
        client = StrataClient()
        data = {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        opened = MagicMock()
        opened.__enter__.return_value = io.StringIO(json.dumps(data))
        client.opener = MagicMock()
        client.opener.open.return_value = opened
        with self.assertRaises(ReviewError):
            client.review([self.source])

    def test_url_safety_and_markdown(self) -> None:
        for url in ["file:///tmp/file", "http://192.168.1.1:8080/v1", "http://user:secret@localhost/v1"]:
            with self.assertRaises(ReviewError):
                StrataClient(url)
        output = render_markdown({"review": self.response(), "evidence_validation": "not run"})
        self.assertIn("sample.cpp:3", output)
        self.assertIn("Suggested reproduction", output)


if __name__ == "__main__":
    unittest.main()
