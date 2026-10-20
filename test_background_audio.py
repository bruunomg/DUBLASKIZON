import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'build_vendor'))
import unittest
import numpy as np
from pydub import AudioSegment
from background_audio import mix_background, silence_range, segment, track_frames


def audio(value, ms=1000, rate=8000, channels=1):
    return AudioSegment(np.full(rate*ms//1000*channels, value, dtype='<i2').tobytes(),
                        sample_width=2, frame_rate=rate, channels=channels)


class MixerTests(unittest.TestCase):
    def test_gain_and_duration(self):
        result = mix_background(audio(1000), audio(2000, 2000, 16000, 2), -20)
        self.assertEqual((len(result), result.frame_rate, result.channels, result.sample_width),
                         (2000, 8000, 1, 2))
        self.assertTrue(np.all(np.abs(np.array(result[:999].get_array_of_samples())-1200) <= 1))
        self.assertTrue(np.all(np.abs(np.array(result[1001:].get_array_of_samples())-200) <= 1))

    def test_short_background_keeps_dub_tail(self):
        result = mix_background(audio(1000), audio(2000, 200), 0)
        samples = result.get_array_of_samples()
        self.assertEqual(samples[0], 3000)
        self.assertEqual(samples[-1], 1000)

    def test_overload_does_not_wrap(self):
        result = mix_background(audio(-30000), audio(-30000), 0)
        self.assertGreaterEqual(min(result.get_array_of_samples()), -32768)
        self.assertLess(min(result.get_array_of_samples()), -32000)

    def test_mute_keeps_timing_and_source(self):
        source = audio(1000)
        result = silence_range(source, 200, 500)
        self.assertEqual(len(result), len(source))
        self.assertLess(result[210:490].rms, 2)
        self.assertEqual(result[600:].raw_data, source[600:].raw_data)
        self.assertEqual(source.rms, 1000)

    def test_invalid_gain(self):
        for gain in [float('nan'), float('inf'), -61, 7]:
            with self.assertRaises(ValueError):
                mix_background(audio(1), audio(1), gain)

    def test_wav_8_and_24_bit_round_trip(self):
        for width, raw in [(1, bytes([128, 140, 100])*80),
                           (3, b'\x00\x10\x00'*240)]:
            track=dict(frames=raw,sample_width=width,sample_rate=8000,channels=1)
            decoded=segment(track)
            self.assertEqual(track_frames(decoded,width),raw)
            mixed=mix_background(decoded,decoded,-20)
            self.assertEqual(len(track_frames(mixed,width)),len(raw))


if __name__ == '__main__':
    unittest.main()
