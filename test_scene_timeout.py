import io
import unittest
from unittest.mock import Mock, patch
from scene_timeout import scene_lines, SceneTimeout

class TimeoutTests(unittest.TestCase):
    def test_unlimited_and_completed_output(self):
        for seconds in (0,120):
            process=Mock(stdout=io.StringIO('one\ntwo\n'))
            self.assertEqual(list(scene_lines(process,seconds)),['one\n','two\n'])
            process.kill.assert_not_called()

    def test_timeout_kills_scene(self):
        process=Mock(stdout=io.StringIO('one\n'))
        with patch('scene_timeout.time.monotonic',side_effect=[0,121]):
            with self.assertRaises(SceneTimeout):list(scene_lines(process,120))
        process.kill.assert_called_once()

    def test_cancel_kills_without_reporting_timeout(self):
        process=Mock(stdout=io.StringIO('one\n'))
        self.assertEqual(list(scene_lines(process,120,lambda:True)),[])
        process.kill.assert_called_once()
