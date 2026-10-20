import io
import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave
import shutil

import batch_tab
import personalized_dubbing_tab as custom
import review_tab as review


def make_audio(path, seconds):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(1000)
        audio.writeframes(b'\x01\x02' * (1000 * seconds))


class NaturalTimingTests(unittest.TestCase):
    def test_player_navigation_scrolls_personalized_list_even_during_redub(self):
        from unittest.mock import Mock
        app=custom.PersonalizedDubbingApp.__new__(custom.PersonalizedDubbingApp)
        app.stems=['first','next'];app.scene_list=Mock()
        app._ensure_scene_review=Mock(return_value=SimpleNamespace(busy=True))
        app._sync_personalized_scene('next',1)
        app.scene_list.selection_clear.assert_called_once_with(0, custom.END)
        app.scene_list.selection_set.assert_called_once_with(1)
        app.scene_list.see.assert_called_once_with(1)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        old_custom, old_review = custom.ROOT, review.ROOT
        self.addCleanup(custom.configure_project_root, old_custom)
        self.addCleanup(review.configure_project_root, old_review)
        custom.configure_project_root(self.root)
        review.configure_project_root(self.root)
        self.original = self.root / 'WAV ORIGINAIS' / 'cena.wav'
        self.reference = self.root / 'modelo.wav'
        self.generated = self.root / 'gerado.wav'
        self.text = self.root / 'TXT TEXTO PORTUGUES' / 'cena.txt'
        make_audio(self.original, 4)
        make_audio(self.reference, 2)
        make_audio(self.generated, 1)
        self.text.parent.mkdir(parents=True)
        self.text.write_text('Venha aqui agora.', encoding='utf-8')
        self.original_bytes = self.original.read_bytes()

    def test_personalized_worker_preserves_natural_duration(self):
        app = custom.PersonalizedDubbingApp.__new__(custom.PersonalizedDubbingApp)
        app.cancel_requested = False
        app.queue = queue.Queue()
        app.audio_by_stem = {'cena': self.original}
        app.text_by_stem = {'cena': self.text}
        app.run_voice_model = 'edwixx/omnivoice-brpt-v15'
        app.run_alignment_settings = None
        content = self.generated.read_bytes()
        def generate(command, **_kwargs):
            Path(command[command.index('--output') + 1]).write_bytes(content)
            return SimpleNamespace(stdout=io.StringIO('Saved to gerado.wav\n'), returncode=0, wait=lambda: 0)
        with patch.object(custom.subprocess, 'Popen', side_effect=generate), patch.object(custom, 'match_original_expression') as forced:
            app._worker(['cena'], self.reference, ['fake-infer'])
        target = custom.CUSTOM_DIR / 'cena.wav'
        self.assertEqual(target.read_bytes(), content)
        self.assertEqual(self.original.read_bytes(), self.original_bytes)
        forced.assert_not_called()
        record = json.loads(custom.MANIFEST_FILE.read_text())['cena']
        self.assertEqual(record['timing_mode'], 'natural')
        self.assertIn(('done', 1, 1, False), list(app.queue.queue))

    def test_alignment_limit_keeps_generated_audio_available(self):
        app = SimpleNamespace(run_alignment_settings={'pauses': False, 'max_change': 25}, queue=queue.Queue())
        before = self.generated.read_bytes()
        with patch.object(custom, '_ffmpeg_path', return_value='ffmpeg'), patch.object(custom, '_audio_duration', side_effect=[1, 4]), patch.object(custom.subprocess, 'Popen') as process:
            batch_tab.BatchApp.align_generated_audio(app, self.generated, self.original)
        process.assert_not_called()
        self.assertEqual(self.generated.read_bytes(), before)
        self.assertIn('ritmo natural', app.queue.get()[1])

    def test_optional_pause_alignment_keeps_tail_and_does_not_mute_words(self):
        import numpy as np
        class Audio:
            def __init__(self, data, **_kwargs): self.raw_data = data
            @classmethod
            def from_file(cls, path):
                with wave.open(str(path)) as stream:
                    return cls(stream.readframes(stream.getnframes()))
            def set_frame_rate(self, _value): return self
            def set_channels(self, _value): return self
            def set_sample_width(self, _value): return self
            def export(self, path, **_kwargs):
                with wave.open(str(path), 'wb') as stream:
                    stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
                    stream.writeframes(self.raw_data)
        # Original is shorter and silent where translated speech is present.
        with wave.open(str(self.original), 'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
            stream.writeframes(np.zeros(24000, dtype=np.int16).tobytes())
        with wave.open(str(self.generated), 'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
            stream.writeframes(np.full(48000, 1000, dtype=np.int16).tobytes())
        target = self.root / 'aligned.wav'
        def run(command, **_kwargs):
            shutil.copy2(self.generated, command[-1])
            return SimpleNamespace(returncode=0)
        with patch.dict('sys.modules', {'pydub': SimpleNamespace(AudioSegment=Audio)}), \
                patch.object(custom, '_silero_speech_regions', side_effect=RuntimeError('not installed')), \
                patch.object(custom, '_ffmpeg_path', return_value='ffmpeg'), \
                patch.object(custom, '_audio_duration', return_value=2), \
                patch.object(custom.subprocess, 'run', side_effect=run):
            custom.match_original_expression(self.generated, self.original, target)
        with wave.open(str(target)) as stream:
            samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype=np.int16)
        self.assertEqual(len(samples), 48000)
        self.assertGreaterEqual(samples.min(), 300)

    def _review_generate(self, aligned=False):
        app = review.ReviewApp.__new__(review.ReviewApp)
        import queue
        app.regen_stage_events = queue.Queue()
        callbacks = []
        app.root = SimpleNamespace(after=lambda _time, callback: callbacks.append(callback))
        app.config = {'model': 'edwixx/omnivoice-brpt-v15', 'language': 'pt', 'instruct': 'portuguese accent'}
        app.audio_by_stem = {'cena': self.original}
        app.regen_alignment_settings = {'max_change': 25, 'pauses': False} if aligned else None
        target = review.CUSTOM_OUTPUT_DIR / 'cena.wav'
        make_audio(target, 3)
        previous = target.read_bytes()
        content = self.generated.read_bytes()
        def generate(command, **_kwargs):
            Path(command[command.index('--output') + 1]).write_bytes(content)
            return SimpleNamespace(returncode=0, stdout='Saved to gerado.wav')
        app._run_cancellable_generation = generate
        def align(_app, generated, original):
            self.assertEqual(original, self.original)
            make_audio(generated, 2)
        with patch.object(batch_tab, 'find_voice_command', return_value=['fake-infer']), patch.object(custom, 'match_original_expression') as forced, patch.object(batch_tab.BatchApp, 'align_generated_audio', side_effect=align) as alignment:
            app._run_generation('cena', 'Venha aqui agora.', target, target, self.reference)
        forced.assert_not_called()
        self.assertEqual(self.original.read_bytes(), self.original_bytes)
        self.assertEqual((self.root / 'revisoes' / 'cena_v01.wav').read_bytes(), previous)
        self.assertEqual(len(callbacks), 1)
        return target, content, alignment

    def test_redub_with_model_preserves_duration_and_backup(self):
        target, content, alignment = self._review_generate()
        self.assertEqual(target.read_bytes(), content)
        alignment.assert_not_called()

    def test_explicit_alignment_is_still_used(self):
        target, _content, alignment = self._review_generate(aligned=True)
        alignment.assert_called_once()
        with wave.open(str(target)) as audio:
            self.assertEqual(audio.getnframes() / audio.getframerate(), 2)


if __name__ == '__main__':
    unittest.main()
