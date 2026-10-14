import tempfile
import unittest
import sys
import wave
import struct
import math
from pathlib import Path
from unittest.mock import patch

import numpy as np

import audio_frequency_separator_tab as separator


class FrequencySeparatorTests(unittest.TestCase):
    def test_stage_one_places_each_audio_in_own_named_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);sub=root/'personagem';sub.mkdir()
            (sub/'fala.wav').write_bytes(b'wav');(sub/'efeito.ogg').write_bytes(b'ogg');(sub/'nota.txt').write_text('x')
            result=separator.organize_audio_in_named_folders(root)
            self.assertEqual(result,{'moved':2,'already':0})
            self.assertTrue((sub/'fala'/'fala.wav').is_file());self.assertTrue((sub/'efeito'/'efeito.ogg').is_file())
            self.assertTrue((sub/'nota.txt').is_file())

    def test_stage_three_restores_pt_wav_and_removes_completed_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);scene=root/'fala';pt=scene/'WAV PT-BR';en=scene/'WAV INGLES';pt.mkdir(parents=True);en.mkdir()
            (scene/'fala.ogg').write_bytes(b'ogg');(pt/'fala.wav').write_bytes(b'pt');(en/'fala.wav').write_bytes(b'en')
            result=separator.restore_dubbed_audio_positions(root)
            self.assertEqual(result,{'moved':1,'skipped':0,'removed':1})
            self.assertTrue((root/'fala.wav').is_file());self.assertFalse(scene.exists())

    def test_stage_three_preserves_scene_when_destination_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);scene=root/'fala';pt=scene/'WAV PT-BR';pt.mkdir(parents=True)
            (scene/'fala.ogg').write_bytes(b'ogg');(pt/'fala.wav').write_bytes(b'novo');(root/'fala.wav').write_bytes(b'existente')
            result=separator.restore_dubbed_audio_positions(root)
            self.assertEqual(result,{'moved':0,'skipped':1,'removed':0})
            self.assertTrue(scene.is_dir());self.assertEqual((root/'fala.wav').read_bytes(),b'existente')

    def test_fifth_step_copies_unpaired_hierarchy_and_protects_paired_scene(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as output:
            root=Path(directory);destination=Path(output)
            paired=root/'capitulo'/'cena_ok';(paired/'WAV INGLES').mkdir(parents=True);(paired/'WAV PT-BR').mkdir()
            (paired/'cena.ogg').write_bytes(b'ogg');(paired/'WAV INGLES'/'cena.wav').write_bytes(b'en');(paired/'WAV PT-BR'/'cena.wav').write_bytes(b'pt')
            incomplete=root/'capitulo'/'cena_sem_par';(incomplete/'WAV INGLES').mkdir(parents=True);(incomplete/'WAV INGLES'/'restante.wav').write_bytes(b'x')
            copied=separator.copy_unpaired_results(root,destination)
            self.assertEqual(copied['copied'],1)
            self.assertTrue((destination/'capitulo'/'cena_sem_par'/'WAV INGLES'/'restante.wav').is_file())
            self.assertFalse((destination/'capitulo'/'cena_ok'/'cena.ogg').exists())
            cleaned=separator.remove_unpaired_results(root)
            self.assertEqual(cleaned['deleted'],1)
            self.assertTrue((paired/'cena.ogg').is_file());self.assertTrue((paired/'WAV INGLES'/'cena.wav').is_file());self.assertTrue((paired/'WAV PT-BR'/'cena.wav').is_file())
            self.assertFalse(incomplete.exists())

    def test_frozen_build_uses_managed_mfcc_process(self):
        import dependency_setup
        with tempfile.TemporaryDirectory() as directory:
            wav = Path(directory) / 'tom.wav'
            with wave.open(str(wav), 'wb') as output:
                output.setnchannels(1); output.setsampwidth(2); output.setframerate(22050)
                output.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 440 * i / 22050))) for i in range(2205)))
            separator._FEATURE_CLIENT = None
            with patch.object(sys, 'frozen', True, create=True), patch.object(dependency_setup, 'managed_python', return_value=Path(sys.executable)):
                feature, duration = separator.audio_features(wav)
            self.assertEqual(len(feature), 20)
            self.assertGreater(duration, 0)
            separator._FEATURE_CLIENT.close(); separator._FEATURE_CLIENT = None

    def test_frozen_managed_mfcc_reads_unicode_path(self):
        import dependency_setup
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'Só VOZ selecionada'
            folder.mkdir()
            wav = folder / 'áudio inglês.wav'
            with wave.open(str(wav), 'wb') as output:
                output.setnchannels(1); output.setsampwidth(2); output.setframerate(22050)
                output.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 440 * i / 22050))) for i in range(2205)))
            separator._FEATURE_CLIENT = None
            with patch.object(sys, 'frozen', True, create=True), patch.object(dependency_setup, 'managed_python', return_value=Path(sys.executable)):
                feature, duration = separator.audio_features(wav)
            self.assertEqual(len(feature), 20)
            self.assertGreater(duration, 0)
            separator._FEATURE_CLIENT.close(); separator._FEATURE_CLIENT = None

    def test_final_filter_keeps_closest_pair_and_deletes_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            en, pt = root / 'WAV INGLES', root / 'WAV PT-BR'
            en.mkdir(); pt.mkdir()
            ogg = root / 'cena.ogg'; ogg.write_bytes(b'ogg')
            for name in ('melhor.wav', 'repetido_nome_diferente.wav', 'distante.wav'):
                (en / name).write_bytes(b'en'); (pt / name).write_bytes(b'pt')
            features = {
                'cena.ogg': np.array([1.0, 0.0]),
                'melhor.wav': np.array([1.0, 0.0]),
                'repetido_nome_diferente.wav': np.array([0.99, 0.01]),
                'distante.wav': np.array([0.0, 1.0]),
            }
            with patch.object(separator, 'audio_features', side_effect=lambda path: (features[path.name], 1.0)):
                result = separator.filter_final_results(root)
            self.assertEqual(result, {'kept': 1, 'deleted_en': 2, 'deleted_pt': 2})
            self.assertTrue((en / 'melhor.wav').is_file())
            self.assertTrue((pt / 'melhor.wav').is_file())
            self.assertEqual([p.name for p in en.glob('*.wav')], ['melhor.wav'])
            self.assertEqual([p.name for p in pt.glob('*.wav')], ['melhor.wav'])

    def test_result_filter_removes_only_mismatched_en_and_same_name_pt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            en, pt = root / 'WAV INGLES', root / 'WAV PT-BR'
            en.mkdir(); pt.mkdir()
            (root / 'cena.ogg').write_bytes(b'ogg')
            for name in ('correto.wav', 'errado.wav'):
                (en / name).write_bytes(b'en'); (pt / name).write_bytes(b'pt')
            features = {
                'cena.ogg': np.array([1.0, 0.0]),
                'correto.wav': np.array([1.0, 0.0]),
                'errado.wav': np.array([0.0, 1.0]),
            }
            with patch.object(separator, 'audio_features', side_effect=lambda path: (features[path.name], 1.0)):
                result = separator.remove_mismatched_results(root, similarity_threshold=.95)
            self.assertEqual(result, {'kept': 1, 'deleted_en': 1, 'deleted_pt': 1})
            self.assertTrue((en / 'correto.wav').is_file())
            self.assertTrue((pt / 'correto.wav').is_file())
            self.assertFalse((en / 'errado.wav').exists())
            self.assertFalse((pt / 'errado.wav').exists())

    def test_second_pass_only_moves_file_left_by_duration_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav_en = root / 'en'
            wav_pt = root / 'pt'
            ogg = root / 'ogg'
            for folder in (wav_en / 'personagem', wav_pt / 'personagem', ogg / 'cena'):
                folder.mkdir(parents=True)

            files = {
                wav_en / 'personagem' / 'curto.wav',
                wav_en / 'personagem' / 'longo.wav',
                wav_pt / 'personagem' / 'curto.wav',
                wav_pt / 'personagem' / 'longo.wav',
                ogg / 'cena' / 'alvo_curto.ogg',
                ogg / 'cena' / 'alvo_longo.ogg',
            }
            for path in files:
                path.write_bytes(b'audio')

            features = {
                'curto.wav': (np.array([1.0, 0.0]), 1.00),
                'longo.wav': (np.array([0.0, 1.0]), 4.00),
                'alvo_curto.ogg': (np.array([1.0, 0.0]), 1.05),
                'alvo_longo.ogg': (np.array([0.0, 1.0]), 2.00),
            }
            with patch.object(separator, 'audio_features', side_effect=lambda path: features[path.name]):
                first = separator.run_matching_pass(wav_en, wav_pt, ogg, require_duration=True)
                self.assertEqual(first['moved_en'], 1)
                self.assertEqual(first['moved_pt'], 1)
                self.assertFalse((wav_en / 'personagem' / 'curto.wav').exists())
                self.assertTrue((wav_en / 'personagem' / 'longo.wav').exists())
                self.assertTrue((ogg / 'cena' / 'WAV INGLES' / 'curto.wav').is_file())
                self.assertTrue((ogg / 'cena' / 'WAV PT-BR' / 'curto.wav').is_file())

                second = separator.run_matching_pass(wav_en, wav_pt, ogg, require_duration=False)
                self.assertEqual(second['moved_en'], 1)
                self.assertEqual(second['moved_pt'], 1)
                self.assertFalse((wav_en / 'personagem' / 'longo.wav').exists())
                self.assertTrue((ogg / 'cena' / 'WAV INGLES' / 'longo.wav').is_file())
                self.assertTrue((ogg / 'cena' / 'WAV PT-BR' / 'longo.wav').is_file())

    def test_collision_keeps_both_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            en, pt, ogg = root / 'en', root / 'pt', root / 'ogg'
            en.mkdir(); pt.mkdir(); ogg.mkdir()
            (en / 'fala.wav').write_bytes(b'en')
            (pt / 'fala.wav').write_bytes(b'pt')
            (ogg / 'fala.ogg').write_bytes(b'ogg')
            output = ogg / 'WAV INGLES'
            output.mkdir()
            (output / 'fala.wav').write_bytes(b'old')
            with patch.object(separator, 'audio_features', return_value=(np.array([1.0, 0.0]), 1.0)):
                result = separator.run_matching_pass(en, pt, ogg)
            self.assertEqual(result['moved_en'], 1)
            self.assertTrue((output / 'fala.wav').is_file())
            self.assertTrue((output / 'fala_2.wav').is_file())


if __name__ == '__main__':
    unittest.main()
