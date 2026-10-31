"""Data ownership checks run without installing Daft or Arrow."""

import hashlib
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import lab


class DataOwnershipTests(unittest.TestCase):
    def test_unowned_partition_is_preserved_before_any_deletion(self):
        self.check_conflict(symlink=False)

    def test_dangling_partition_symlink_is_preserved(self):
        self.check_conflict(symlink=True)

    def check_conflict(self, symlink):
        with tempfile.TemporaryDirectory() as temporary:
            local = Path(temporary)
            data = local / "data"
            data.mkdir()
            owned = data / "part-0000.parquet"
            owned.write_bytes(b"owned-data")
            manifest = {
                "files": [{"name": owned.name,
                           "sha256": hashlib.sha256(owned.read_bytes()).hexdigest()}]
            }
            (data / "manifest.json").write_text(json.dumps(manifest))
            conflict = data / "part-0001.parquet"
            outside = local / "must-not-be-created"
            if symlink:
                conflict.symlink_to(outside)
            else:
                conflict.write_bytes(b"user-data")
            # Only the preflight should run: dependency stubs have no compute API.
            arrow = types.ModuleType("pyarrow")
            parquet = types.ModuleType("pyarrow.parquet")
            arrow.parquet = parquet
            numpy = types.ModuleType("numpy")
            numpy.int64 = int
            numpy.arange = lambda *args, **kwargs: self.fail(
                "Reached computation before rejecting an unowned partition")
            modules = {"numpy": numpy, "pyarrow": arrow,
                       "pyarrow.parquet": parquet}
            with patch.object(lab, "LOCAL", local), patch.dict("sys.modules", modules):
                with self.assertRaisesRegex(SystemExit, "Unowned|symlink"):
                    lab.generate(2, 2, False)
            self.assertEqual(owned.read_bytes(), b"owned-data")
            self.assertEqual(json.loads((data / "manifest.json").read_text()), manifest)
            if symlink:
                self.assertTrue(conflict.is_symlink())
                self.assertFalse(outside.exists())
            else:
                self.assertEqual(conflict.read_bytes(), b"user-data")


if __name__ == "__main__":
    unittest.main()
