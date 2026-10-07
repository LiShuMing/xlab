from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from tech_radar.web.app import create_app
except ImportError:
    create_app = None  # type: ignore[assignment]


@unittest.skipIf(create_app is None, "web optional dependencies are not installed")
class WebAppTest(unittest.TestCase):
    def test_application_exposes_workspace_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = root / "config.toml"
            config.write_text(
                '[app]\ndatabase = "radar.sqlite3"\ntimezone = "Asia/Shanghai"\n',
                encoding="utf-8",
            )

            app = create_app(config)  # type: ignore[misc]
            paths = {route.path for route in app.routes}

            self.assertIn("/api/health", paths)
            self.assertIn("/api/materials", paths)
            self.assertIn("/api/topics/{topic_id}/drafts", paths)
            self.assertIn("/api/articles/{article_id}", paths)
            self.assertIn("/api/articles/{article_id}/versions", paths)
            self.assertIn("/api/publications", paths)
            self.assertIn("/api/publication-jobs/{job_id}/prepare", paths)
            self.assertIn("/api/publication-jobs/{job_id}/preview", paths)


if __name__ == "__main__":
    unittest.main()
