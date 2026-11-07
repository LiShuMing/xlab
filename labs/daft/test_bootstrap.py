"""Check the rootfs extraction boundary without downloading anything."""

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from bootstrap import extract_layer, verify_ready


class LayerExtractionTests(unittest.TestCase):
    def extract(self, members, directory):
        layer = directory / "layer.tar"
        root = directory / "root"
        root.mkdir(exist_ok=True)
        with tarfile.open(layer, "w") as archive:
            for name, kind, value in members:
                member = tarfile.TarInfo(name)
                if kind == "symlink":
                    member.type = tarfile.SYMTYPE
                    member.linkname = value
                    archive.addfile(member)
                else:
                    data = value.encode()
                    member.size = len(data)
                    member.mode = 0o644
                    archive.addfile(member, io.BytesIO(data))
        extract_layer(layer, root)
        return root

    def test_parent_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaises(ValueError):
                self.extract([("../outside", "file", "escape")], directory)
            self.assertFalse((directory / "outside").exists())

    def test_whiteout_parent_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            sentinel = directory / "preserve"
            sentinel.write_text("outside-rootfs")
            with self.assertRaises(ValueError):
                self.extract([(".wh...", "file", "")], directory)
            self.assertEqual(sentinel.read_text(), "outside-rootfs")

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                self.extract([("link", "symlink", "../../outside")], Path(temporary))

    def test_absolute_guest_link_stays_inside_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.extract(
                [
                    ("usr/lib/value", "file", "inside"),
                    ("lib", "symlink", "/usr/lib"),
                    ("lib/second", "file", "also-inside"),
                ],
                Path(temporary),
            )
            self.assertEqual((root / "lib/value").read_text(), "inside")
            self.assertEqual((root / "usr/lib/second").read_text(), "also-inside")

    def test_whiteout_removes_only_owned_rootfs_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.extract([("keep", "file", "yes"), ("remove", "file", "old")], directory)
            root = self.extract([(".wh.remove", "file", "")], directory)
            self.assertTrue((root / "keep").exists())
            self.assertFalse((root / "remove").exists())


class RootfsIdentityTests(unittest.TestCase):
    def test_ready_digest_matches_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".daft-lab-ready").write_text("sha256:installed\n")
            lock = root / "image.lock.json"
            lock.write_text(json.dumps({"manifest_digest": "sha256:installed"}))
            verify_ready(root, lock)

    def test_mismatch_preserves_installed_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / ".daft-lab-ready"
            marker.write_text("sha256:installed\n")
            lock = root / "image.lock.json"
            lock.write_text(json.dumps({"manifest_digest": "sha256:new"}))
            with self.assertRaisesRegex(SystemExit, "differs"):
                verify_ready(root, lock)
            self.assertEqual(marker.read_text(), "sha256:installed\n")


if __name__ == "__main__":
    unittest.main()
