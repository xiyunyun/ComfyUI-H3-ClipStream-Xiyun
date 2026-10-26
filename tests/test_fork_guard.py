"""Fork guard: stop the 熙云 copy from loading beside the original plugin."""

import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from fork_guard import find_other_copy

MARKER_REL = os.path.join("clipbin", "long_nodes.py")
MARKER_TEXT = "node_id='MiniMaxClipBinLongBuilder'"


class TestForkGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.self_dir = os.path.join(self.root, "ComfyUI-H3-ClipStream-Xiyun")
        self._write(self.self_dir, MARKER_TEXT)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, folder, text):
        os.makedirs(os.path.join(folder, "clipbin"), exist_ok=True)
        with open(os.path.join(folder, MARKER_REL), "w", encoding="utf-8") as stream:
            stream.write(text)

    def test_detects_a_sibling_copy(self):
        other = os.path.join(self.root, "ComfyUI-H3-ClipStream")
        self._write(other, MARKER_TEXT)
        self.assertEqual(
            find_other_copy(self.self_dir, MARKER_REL, MARKER_TEXT),
            os.path.abspath(other),
        )

    def test_ignores_an_unrelated_folder(self):
        self._write(os.path.join(self.root, "OtherPlugin"), "no marker")
        self.assertIsNone(find_other_copy(self.self_dir, MARKER_REL, MARKER_TEXT))

    def test_ignores_the_copy_itself(self):
        self.assertIsNone(find_other_copy(self.self_dir, MARKER_REL, MARKER_TEXT))

    def test_ignores_a_disabled_copy(self):
        self._write(os.path.join(self.root, "ComfyUI-H3-ClipStream.disabled"),
                    MARKER_TEXT)
        self.assertIsNone(find_other_copy(self.self_dir, MARKER_REL, MARKER_TEXT))

    def test_environment_override_forces_both_to_load(self):
        self._write(os.path.join(self.root, "ComfyUI-H3-ClipStream"), MARKER_TEXT)
        with mock.patch.dict(os.environ, {"H3_XYIYUN_ALLOW_DUPLICATE": "1"}):
            self.assertIsNone(find_other_copy(self.self_dir, MARKER_REL, MARKER_TEXT))


if __name__ == "__main__":
    unittest.main()
