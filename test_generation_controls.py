import sys
import subprocess
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from review_tab import ReviewApp
from batch_tab import BatchApp
import personalized_dubbing_tab as custom


class GenerationControls(unittest.TestCase):
    def test_missing_translation_respects_displayed_text_and_activation(self):
        flag = SimpleNamespace(get=lambda:'1')
        app = SimpleNamespace(translate_missing_var=flag, player_text_override=('scene','Texto existente'))
        self.assertFalse(ReviewApp.needs_missing_translation(app,'scene'))
        app.player_text_override=('scene','  ')
        self.assertTrue(ReviewApp.needs_missing_translation(app,'scene'))
        app.translate_missing_var=SimpleNamespace(get=lambda:'0')
        self.assertFalse(ReviewApp.needs_missing_translation(app,'scene'))

    def test_alignment_disabled_does_not_touch_audio(self):
        BatchApp.align_generated_audio(SimpleNamespace(run_alignment_settings=None), Path('absent.wav'), Path('original.wav'))

    def test_alignment_limit_preserves_generated_audio(self):
        app = SimpleNamespace(run_alignment_settings={'max_change':25, 'pauses':False})
        with patch.object(custom, '_ffmpeg_path', return_value='ffmpeg'), patch.object(custom, '_audio_duration', side_effect=[4, 2]):
            with self.assertRaisesRegex(RuntimeError, 'limite'):
                BatchApp.align_generated_audio(app, Path('generated.wav'), Path('original.wav'))

    def test_alignment_commits_only_valid_non_cancelled_result(self):
        for cancel in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                generated = Path(tmp)/'generated.wav'
                generated.write_bytes(b'old')
                app = SimpleNamespace(run_alignment_settings={'max_change':25, 'pauses':False}, cancel_requested=cancel)
                def launch(command, **kwargs):
                    self.assertIn('atempo=', command[command.index('-af')+1])
                    Path(command[-1]).write_bytes(b'aligned')
                    return SimpleNamespace(wait=lambda:0)
                with patch.object(custom, '_ffmpeg_path', return_value='ffmpeg'), patch.object(custom, '_audio_duration', side_effect=[2.2, 2, 2]), patch('batch_tab.subprocess.Popen', side_effect=launch):
                    if cancel:
                        with self.assertRaisesRegex(RuntimeError, 'cancelado'):
                            BatchApp.align_generated_audio(app, generated, Path('original.wav'))
                    else:
                        BatchApp.align_generated_audio(app, generated, Path('original.wav'))
                self.assertEqual(generated.read_bytes(), b'old' if cancel else b'aligned')
                self.assertEqual(list(Path(tmp).iterdir()), [generated])

    def test_stop_after_scene_does_not_cancel_single_regeneration(self):
        app = SimpleNamespace(busy=True, regen_cancel_requested=False, status_var=SimpleNamespace(set=Mock()))
        ReviewApp.control_generation(app, True)
        self.assertFalse(app.regen_cancel_requested)
        ReviewApp.control_generation(app, False)
        self.assertTrue(app.regen_cancel_requested)

    def test_idle_review_routes_only_selected_source(self):
        callback = Mock()
        app = SimpleNamespace(busy=False, audio_source_mode='custom', project_actions={'control_dubbing':callback})
        ReviewApp.control_generation(app, True)
        callback.assert_called_once_with('custom', True)

    def test_cancellable_runner_stops_its_child(self):
        app = SimpleNamespace(regen_cancel_requested=True)
        with self.assertRaisesRegex(RuntimeError, 'cancelada'):
            ReviewApp._run_cancellable_generation(app, [sys.executable, '-c', 'import time; time.sleep(30)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == '__main__':
    unittest.main()
