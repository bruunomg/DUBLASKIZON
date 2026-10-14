import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import personalized_dubbing_tab as custom


class AlignmentTests(unittest.TestCase):
    def test_background_hiss_gap_is_removed_despite_broad_vad(self):
        rate=1000
        hiss=np.tile(np.array([-3,3],dtype=np.int16),300)
        pcm=np.r_[np.full(200,1000,dtype=np.int16),hiss,np.full(200,2000,dtype=np.int16)]
        regions=custom._protected_speech_regions(pcm,[(0,len(pcm))],rate)
        result=custom._compact_speech_block(pcm,regions,0,len(pcm))
        self.assertLess(len(result),len(pcm)-400)
        self.assertEqual(np.count_nonzero(result==1000),200)
        self.assertEqual(np.count_nonzero(result==2000),200)

    def test_quiet_word_next_to_hiss_survives_energy_check(self):
        pcm=np.r_[np.full(100,1000,dtype=np.int16),np.tile([-1,1],300),np.full(100,5,dtype=np.int16),np.full(100,2000,dtype=np.int16)].astype(np.int16)
        regions=custom._protected_speech_regions(pcm,[(0,len(pcm))],1000)
        result=custom._compact_speech_block(pcm,regions,0,len(pcm))
        self.assertEqual(np.count_nonzero(result==5),100)
        self.assertLess(len(result),len(pcm))

    def test_silent_edge_padding_is_not_a_speech_block(self):
        samples=np.zeros(48000,dtype=np.int16)
        samples[16000:24000]=5  # Quiet voice must be retained.
        regions=custom._protected_speech_regions(samples,[(16000,24000)])
        self.assertEqual(len(regions),1)
        a,b=regions[0]
        self.assertLessEqual(a,16000)
        self.assertGreaterEqual(b,24000)
        self.assertTrue(np.array_equal(custom._compact_speech_block(samples,regions,0,len(samples))[np.flatnonzero(custom._compact_speech_block(samples,regions,0,len(samples)))],samples[samples!=0]))
    def test_vad_missed_beginning_and_quiet_words_are_preserved(self):
        pcm = np.array([3]*100+[2000]*100+[0]*600+[2]*100+[3000]*100, dtype=np.int16)
        regions = custom._protected_speech_regions(pcm, [(100,200),(900,1000)], 1000)
        result = custom._compact_speech_block(pcm, regions, 0, len(pcm))
        self.assertEqual(result[result!=0].tolist(), pcm[pcm!=0].tolist())
        self.assertEqual(result[0], 3)
        self.assertEqual(result[-1], 3000)

    def test_nonzero_noise_is_retained_when_vad_is_uncertain(self):
        pcm = np.array([1]*1000, dtype=np.int16)
        self.assertEqual(custom._protected_speech_regions(pcm, [(400,500)], 1000), [(0,1000)])

    def test_middle_silence_removal_preserves_speech_order_and_outer_edges(self):
        from audio_player import process_scene_internal_silence
        class Audio:
            def __init__(self, data, **kwargs): self.raw_data = data
            def set_channels(self, value): return self
            def set_sample_width(self, value): return self
        data = np.array([0]*100+[1000]*100+[0]*500+[2000]*100+[0]*100, dtype=np.int16)
        track = dict(frames=data.tobytes(), sample_rate=1000, channels=1, sample_width=2)
        with patch.dict('sys.modules', {'pydub': SimpleNamespace(AudioSegment=Audio)}), patch.object(custom, '_silero_speech_regions', return_value=([(100,200),(700,800)],[])):
            result = np.frombuffer(process_scene_internal_silence(track), dtype=np.int16)
        self.assertEqual(result.tolist(), [0]*100+[1000]*100+[0]*140+[2000]*100+[0]*100)
        self.assertEqual(track['frames'], data.tobytes())

    def test_silero_protocol_returns_intervals_from_managed_runtime(self):
        completed = SimpleNamespace(returncode=0, stdout='DUBLASKIZON_VAD [[[10, 100]], [[20, 200]]]\n')
        with patch('dependency_setup.managed_python', return_value=Path('managed/python.exe')), patch.object(custom.subprocess, 'run', return_value=completed) as run:
            result = custom._silero_speech_regions(np.ones(300, dtype=np.int16), np.ones(400, dtype=np.int16))
        self.assertEqual(result, [[[10, 100]], [[20, 200]]])
        self.assertEqual(run.call_args.args[0][0], 'managed\\python.exe')

    def test_wave_reader_falls_back_for_unsupported_wav(self):
        from audio_player import AudioPlayerManager
        decoded = SimpleNamespace(raw_data=b'\x01\x10' * 8000, channels=1, frame_rate=8000)
        decoded.set_sample_width = lambda value: decoded
        module = SimpleNamespace(AudioSegment=SimpleNamespace(from_file=lambda path: decoded))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'float.wav'; path.write_bytes(b'float wave')
            with patch('audio_player.wave.open', side_effect=wave.Error('unknown format: 3')), patch.dict('sys.modules', {'pydub': module}):
                data = AudioPlayerManager._read_waveform(path)
        self.assertEqual(data['duration'], 1)
        self.assertTrue(data['samples'])

    def test_discards_detected_leading_middle_and_trailing_silence(self):
        samples = np.array([0]*100 + [1000]*50 + [0]*200 + [2000]*60 + [0]*300, dtype=np.int16)
        result = custom._compact_speech_block(samples, [(100, 150), (350, 410)], 0, len(samples))
        self.assertEqual(len(result), 110)
        self.assertEqual(result.tolist(), [1000]*50 + [2000]*60)

    def test_local_limit_preserves_generated_audio(self):
        app = SimpleNamespace(run_alignment_settings={'pauses': True, 'max_change':25}, queue=__import__('queue').Queue(), cancel_requested=False, current_process=None)
        import batch_tab
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'dub.wav'; path.write_bytes(b'original generation')
            with patch.object(custom, '_ffmpeg_path', return_value='ffmpeg'), patch.object(custom, '_audio_duration', side_effect=[10, 1]), patch.object(custom, 'match_original_expression', side_effect=custom.AlignmentLimitExceeded('limite local')):
                batch_tab.BatchApp.align_generated_audio(app, path, Path(folder)/'original.wav')
            self.assertEqual(path.read_bytes(), b'original generation')
            self.assertIn('limite local', app.queue.get()[1])

    def test_moves_blocks_preserves_tail_and_matches_total_duration(self):
        class Audio:
            def __init__(self, data, **kwargs): self.raw_data = data
            @classmethod
            def from_file(cls, path):
                with wave.open(str(path)) as stream: return cls(stream.readframes(stream.getnframes()))
            def set_frame_rate(self, value): return self
            def set_channels(self, value): return self
            def set_sample_width(self, value): return self
            def export(self, path, **kwargs):
                with wave.open(path if hasattr(path, 'write') else str(path), 'wb') as stream:
                    stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
                    stream.writeframes(self.raw_data)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src = np.zeros(48000, dtype=np.int16); src[4800:14400] = 2000; src[28800:40800] = 3000
            dub = np.zeros(48000, dtype=np.int16); dub[0:12000] = 1000; dub[24000:] = 4000
            original, generated, target = root/'original.wav', root/'dub.wav', root/'out.wav'
            Audio(src.tobytes()).export(original); Audio(dub.tobytes()).export(generated)
            before = generated.read_bytes()
            speeds=[]
            def run(command, **kwargs):
                data = np.frombuffer(Audio.from_file(command[command.index('-i')+1]).raw_data, dtype=np.int16)
                speed = float(command[command.index('-af')+1].split('=')[1])
                speeds.append(speed)
                data = np.interp(np.linspace(0, len(data)-1, round(len(data)/speed)), np.arange(len(data)), data).astype(np.int16)
                Audio(data.tobytes()).export(command[-1])
                return SimpleNamespace(returncode=0)
            with patch.dict('sys.modules', {'pydub': SimpleNamespace(AudioSegment=Audio)}), patch.object(custom, '_silero_speech_regions', side_effect=RuntimeError('not installed')), patch.object(custom.subprocess, 'run', side_effect=run):
                self.assertTrue(custom._align_speech_regions(generated, original, target, 'ffmpeg', 150))
            result = np.frombuffer(Audio.from_file(target).raw_data, dtype=np.int16)
            self.assertEqual(len(result), len(src))
            self.assertTrue(np.all(result[:4000] == 0))
            self.assertTrue(np.all(result[18000:22000] == 0))
            self.assertTrue(all(speed==1 for speed in speeds))
            self.assertEqual(result[40500], 4000)
            self.assertEqual(generated.read_bytes(), before)

    def test_merges_nearest_pause_without_reordering(self):
        self.assertEqual(custom._merge_speech_regions([(0, 10), (12, 20), (40, 50)], 2), [(0, 20), (40, 50)])

