"""Playback-speed restore: factor parsing, metadata priority, and the ffmpeg pass.

The restore must run ONCE, on the finished film, never per segment. These tests
cover the decisions around that pass; the ffmpeg pass itself is exercised with
a real encode whenever ffmpeg is on PATH, and skipped otherwise.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _support

_support.load_clipbin_package()
lb = _support.load_clipbin_module("long_builder")


class TestParseRestoreSpeed(unittest.TestCase):
    def test_presets_keep_their_exact_values(self):
        self.assertEqual(lb.parse_restore_speed("1.0x"), 1.0)
        self.assertEqual(lb.parse_restore_speed("0.75x"), 0.75)
        self.assertEqual(lb.parse_restore_speed("0.5x"), 0.5)

    def test_options_mirror_the_cut_side(self):
        self.assertEqual(list(lb.RESTORE_SPEED_OPTIONS), ["1.0x", "0.75x", "0.5x", "custom"])

    def test_custom_rounds_to_one_decimal(self):
        self.assertEqual(lb.parse_restore_speed("custom", 0.6), 0.6)
        self.assertEqual(lb.parse_restore_speed("custom", 0.62), 0.6)

    def test_custom_must_be_inside_the_range(self):
        for bad in (0.0, -0.5, 1.05):
            with self.assertRaises(ValueError):
                lb.parse_restore_speed("custom", bad)

    def test_unknown_option_is_refused(self):
        with self.assertRaises(ValueError):
            lb.parse_restore_speed("2.0x")


class TestResolveRestoreFactor(unittest.TestCase):
    def test_without_metadata_the_widget_is_the_only_source(self):
        factor, warnings = lb.resolve_restore_factor("0.5x", 1.0, None)
        self.assertEqual(factor, 0.5)
        self.assertEqual(warnings, [])

    def test_matching_metadata_is_silent(self):
        factor, warnings = lb.resolve_restore_factor("0.5x", 1.0, 0.5)
        self.assertEqual(factor, 0.5)
        self.assertEqual(warnings, [])

    def test_mismatched_metadata_wins_and_says_so(self):
        factor, warnings = lb.resolve_restore_factor("0.75x", 1.0, 0.5)
        self.assertEqual(factor, 0.5)
        self.assertEqual(len(warnings), 1)
        self.assertIn("0.5x", warnings[0])
        self.assertIn("0.75x", warnings[0])

    def test_default_widget_against_metadata_still_restores(self):
        # The most common mistake: the user forgets the widget at 1.0x while the
        # project was cut at 0.5x. Metadata wins, the film still gets restored.
        factor, warnings = lb.resolve_restore_factor("1.0x", 1.0, 0.5)
        self.assertEqual(factor, 0.5)
        self.assertTrue(warnings)


class TestReadProjectPlaybackSpeed(unittest.TestCase):
    def setUp(self):
        self.store = _support.make_temp_dir("cs_lvm_read")
        self._real_root = lb.get_output_root
        lb.get_output_root = lambda: self.store

    def tearDown(self):
        lb.get_output_root = self._real_root
        _support.remove_temp_dir(self.store)

    def _write_index(self, project, playback):
        pdir = os.path.join(self.store, lb.LVM_BIN_DIR_NAME, project)
        os.makedirs(pdir, exist_ok=True)
        with open(os.path.join(pdir, lb.LVM_INDEX_NAME), "w", encoding="utf-8") as stream:
            json.dump({"playback": playback}, stream)

    def test_reads_the_recorded_factor(self):
        self._write_index("Proj", {"playback_speed": 0.5})
        self.assertEqual(lb.read_project_playback_speed("Proj"), 0.5)

    def test_missing_project_has_no_metadata(self):
        self.assertIsNone(lb.read_project_playback_speed("Proj"))

    def test_index_without_the_block_has_no_metadata(self):
        pdir = os.path.join(self.store, lb.LVM_BIN_DIR_NAME, "Proj")
        os.makedirs(pdir, exist_ok=True)
        with open(os.path.join(pdir, lb.LVM_INDEX_NAME), "w", encoding="utf-8") as stream:
            json.dump({"segments": []}, stream)
        self.assertIsNone(lb.read_project_playback_speed("Proj"))

    def test_out_of_range_or_broken_values_are_ignored(self):
        self._write_index("Proj", {"playback_speed": 1.5})
        self.assertIsNone(lb.read_project_playback_speed("Proj"))
        self._write_index("Proj", {"playback_speed": "fast"})
        self.assertIsNone(lb.read_project_playback_speed("Proj"))

    def test_empty_name_is_ignored(self):
        self.assertIsNone(lb.read_project_playback_speed(""))


class TestApplySpeedRestore(unittest.TestCase):
    """One real ffmpeg pass: a 2s film cut at 0.5x restores to about 1s."""

    def setUp(self):
        self.ffmpeg = shutil.which("ffmpeg")
        self.workdir = _support.make_temp_dir("cs_restore")

    def tearDown(self):
        _support.remove_temp_dir(self.workdir)

    @unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg not on PATH")
    def test_half_speed_restore_halves_the_duration(self):
        path = os.path.join(self.workdir, "film.mp4")
        make = [self.ffmpeg, "-y",
                "-f", "lavfi", "-i", "testsrc2=duration=2:rate=24:size=128x72",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", path]
        self.assertEqual(subprocess.run(make, capture_output=True).returncode, 0)

        before = lb.probe_video_streams(path)
        self.assertAlmostEqual(before["duration"], 2.0, delta=0.2)

        lb.apply_speed_restore(path, 0.5, fps=24.0, has_audio=True)

        after = lb.probe_video_streams(path)
        # 0.5x cut -> 2x playback: the film is about 1s again, still CFR 24
        self.assertAlmostEqual(after["duration"], 1.0, delta=0.15)
        self.assertAlmostEqual(after["fps"], 24.0, delta=0.5)
        self.assertTrue(after["has_audio"])
        # in place: same path, no leftover temp files
        self.assertTrue(os.path.isfile(path))
        self.assertEqual([n for n in os.listdir(self.workdir) if n.startswith(".")], [])


if __name__ == "__main__":
    unittest.main()
