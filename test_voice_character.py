import math
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from voice_character import build_filter, spectral_profile


def write_tones(path: Path, tones, rate=24000, seconds=1.0):
    time = np.arange(int(rate * seconds)) / rate
    samples = sum(amplitude * np.sin(2 * math.pi * frequency * time) for frequency, amplitude in tones)
    samples = np.clip(samples, -1, 1)
    pcm = (samples * 28000).astype('<i2')
    with wave.open(str(path), 'wb') as target:
        target.setnchannels(1); target.setsampwidth(2); target.setframerate(rate)
        target.writeframes(pcm.tobytes())


class VoiceCharacterTests(unittest.TestCase):
    def test_builds_restrained_profile_from_original_without_copying_speech(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, generated = root / 'original.wav', root / 'generated.wav'
            write_tones(original, [(650, .75), (2400, .25)])
            write_tones(generated, [(150, .45), (650, .20), (7000, .35)])
            before = original.read_bytes()
            audio_filter, summary = build_filter(original, generated)
            self.assertIn('equalizer=', audio_filter)
            self.assertTrue('lowpass=' in audio_filter or 'highpass=' in audio_filter)
            self.assertIn('detectado', summary)
            self.assertEqual(original.read_bytes(), before)

    def test_profile_is_normalized(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / 'voice.wav'
            write_tones(audio, [(300, .5), (1200, .5)])
            profile = spectral_profile(audio)
            self.assertGreater(sum(profile['bands']), .9)
            self.assertLessEqual(sum(profile['bands']), 1.01)


if __name__ == '__main__':
    unittest.main()
