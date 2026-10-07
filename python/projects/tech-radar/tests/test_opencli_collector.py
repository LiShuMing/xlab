from __future__ import annotations

import unittest

from tech_radar.collectors.opencli import OpenCliCollector, OpenCliError
from tech_radar.domain import Target


class FakeClient:
    def __init__(self, access: str = "read") -> None:
        self.access = access
        self.calls: list[tuple[str, ...]] = []

    def run_json(self, arguments: tuple[str, ...]):
        self.calls.append(arguments)
        if arguments == ("list",):
            return [
                {
                    "site": "twitter",
                    "name": "tweets",
                    "access": self.access,
                }
            ]
        return [
            {
                "id": "42",
                "author": "db_author",
                "text": "Database optimizer update",
                "likes": 10,
                "url": "https://x.com/db_author/status/42",
            }
        ]


class OpenCliCollectorTest(unittest.TestCase):
    def test_normalizes_read_only_command(self) -> None:
        client = FakeClient()
        collector = OpenCliCollector(client)  # type: ignore[arg-type]
        target = Target(
            id="x-db",
            collector="opencli",
            platform="twitter",
            command="tweets",
            arguments=("db_author", "--limit", "5"),
            tags=("database",),
        )

        signals = collector.collect(target)

        self.assertEqual(1, len(signals))
        self.assertEqual("42", signals[0].external_id)
        self.assertEqual(10, signals[0].metrics["likes"])
        self.assertEqual(
            [("list",), ("twitter", "tweets", "db_author", "--limit", "5")],
            client.calls,
        )

    def test_rejects_non_read_command(self) -> None:
        collector = OpenCliCollector(FakeClient(access="write"))  # type: ignore[arg-type]
        target = Target("x-post", "opencli", "twitter", "tweets")

        with self.assertRaisesRegex(OpenCliError, "refusing non-read"):
            collector.collect(target)

    def test_fans_out_subject_watchlist(self) -> None:
        client = FakeClient()
        collector = OpenCliCollector(client)  # type: ignore[arg-type]
        target = Target(
            id="people",
            collector="opencli",
            platform="twitter",
            command="tweets",
            arguments=("{subject}", "--limit", "5"),
            options={"subjects": ["alice", "bob"]},
        )

        signals = collector.collect(target)

        self.assertEqual(2, len(signals))
        self.assertEqual("alice", signals[0].raw["_watch_subject"])
        self.assertEqual("bob", signals[1].raw["_watch_subject"])
        self.assertIn(("twitter", "tweets", "alice", "--limit", "5"), client.calls)
        self.assertIn(("twitter", "tweets", "bob", "--limit", "5"), client.calls)


if __name__ == "__main__":
    unittest.main()
