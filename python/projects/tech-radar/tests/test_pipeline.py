from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tech_radar.builtins import create_registry
from tech_radar.config import load_config
from tech_radar.pipeline import RadarPipeline
from tech_radar.storage import SignalStore


class PipelineTest(unittest.TestCase):
    def test_fixture_to_markdown_end_to_end(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "twitter_timeline.json"
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config_path = root / "config.toml"
            config_path.write_text(
                f'''[app]
database = "radar.sqlite3"
timezone = "Asia/Shanghai"

[processing]
keywords = ["database", "Rust"]
plugins = ["keyword-score", "topic-rule"]

[[targets]]
id = "fixture-x"
collector = "opencli"
platform = "twitter"
command = "timeline"
tags = ["x"]
priority = 100
fixture = "{fixture.as_posix()}"

[[publishers]]
id = "daily"
plugin = "markdown"
directory = "output"
''',
                encoding="utf-8",
            )
            config = load_config(config_path)
            pipeline = RadarPipeline(
                config, create_registry(), SignalStore(config.database)
            )
            now = datetime.now(ZoneInfo("Asia/Shanghai"))

            report = pipeline.collect()
            results = pipeline.publish(now.date())
            repeated_results = pipeline.publish(now.date())

            expected_count = len(json.loads(fixture.read_text(encoding="utf-8")))
            self.assertEqual(expected_count, report.inserted)
            self.assertFalse(report.failures)
            self.assertEqual(1, len(results))
            self.assertEqual([], repeated_results)
            content = Path(results[0].location).read_text(encoding="utf-8")
            self.assertIn("ClickHouse", content)
            self.assertIn("rustlang", content)
            self.assertIn("离线结构预览", content)
            self.assertNotIn("https://x.com/ClickHouseDB/status", content)
            self.assertIn("## 个人精选", content)
            self.assertIn("## 今日概览", content)
            self.assertIn("## 可写作选题", content)


if __name__ == "__main__":
    unittest.main()
