import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import silence_cut  # noqa: E402


class GraphTest(unittest.TestCase):
    def cmd(self, sound, video, parts=None):
        parts = parts or [(0.0, 2.0), (3.0, 5.0)]
        return silence_cut.cut_command(
            Path("a.wav"), Path("out.wav"), parts, has_sound=sound, has_video=video
        )

    def graph(self, cmd):
        return cmd[cmd.index("-filter_complex") + 1]

    def test_audio_only_graph_has_no_video_stream(self):
        g = self.graph(self.cmd(True, False))
        self.assertNotIn("0:v", g, "audio-only input must not mount a video trim")
        self.assertIn("v=0:a=1", g)
        self.assertNotIn("[v]", self.cmd(True, False), "nothing to map")

    def test_video_with_sound_keeps_both_streams(self):
        c = self.cmd(True, True)
        g = self.graph(c)
        self.assertIn("0:v", g)
        self.assertIn("v=1:a=1", g)
        self.assertIn("[v]", c)
        self.assertIn("[a]", c)

    def test_video_without_sound_maps_video_only(self):
        c = self.cmd(False, True)
        g = self.graph(c)
        self.assertNotIn("0:a", g)
        self.assertIn("v=1:a=0", g)
        self.assertNotIn("[a]", c)

    def test_forgotten_has_video_default_rebuilds_the_old_broken_video_assumption(self):
        g = self.graph(silence_cut.cut_command(
            Path("a.wav"), Path("out.wav"), [(0.0, 2.0)], has_sound=True, has_video=True
        ))
        self.assertIn("0:v", g, "default True on a wav caller reproduces the bug — callers must probe")


if __name__ == "__main__":
    unittest.main()


class CoverArtTest(unittest.TestCase):
    def test_cover_art_is_not_video(self):
        probe = '{"streams":[{"codec_name":"mjpeg","disposition":{"attached_pic":1}}]}'
        self.assertFalse(silence_cut.real_video_streams(probe))

    def test_real_video_stream_is_video(self):
        probe = '{"streams":[{"codec_name":"h264","disposition":{"attached_pic":0}}]}'
        self.assertTrue(silence_cut.real_video_streams(probe))

    def test_mixed_art_and_real_video_counts_as_video(self):
        probe = ('{"streams":[{"codec_name":"mjpeg","disposition":{"attached_pic":1}},'
                 '{"codec_name":"h264","disposition":{"attached_pic":0}}]}')
        self.assertTrue(silence_cut.real_video_streams(probe))

    def test_garbage_probe_is_not_video(self):
        self.assertFalse(silence_cut.real_video_streams("not json at all"))
