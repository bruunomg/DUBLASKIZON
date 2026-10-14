import unittest
from voice_reference import select_complete_reference, protect_reference_command, WORKER_CODE


class ReferenceTests(unittest.TestCase):
    def test_preserved_reference_cache_reuses_text_and_invalidates_changed_audio(self):
        import tempfile,types,os
        from pathlib import Path
        from unittest.mock import patch
        import numpy as np
        calls=[]
        class Engine:
            def create_voice_clone_prompt(self,audio,text=None,preprocess=True):return (audio,text,preprocess)
        engine=Engine()
        engine._asr_pipe=lambda *a,**k:(calls.append(k) or {'text':'Frase curta.','chunks':[]})
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'reference.wav';source.write_bytes(b'original recording')
            modules={'omnivoice.models.omnivoice':types.SimpleNamespace(OmniVoice=Engine),
                     'soundfile':types.SimpleNamespace(read=lambda *a,**k:(np.ones((24000,1),dtype='float32'),24000)),
                     'librosa':types.SimpleNamespace(resample=lambda value,**kwargs:value)}
            with patch.dict('sys.modules',modules),patch.dict(os.environ,{'LOCALAPPDATA':folder}):
                namespace={};exec(WORKER_CODE,namespace)
                first=engine.create_voice_clone_prompt(source)
                self.assertEqual(first,engine.create_voice_clone_prompt(source))
                self.assertEqual(len(calls),1)
                self.assertEqual(source.read_bytes(),b'original recording')
                source.write_bytes(b'changed recording')
                engine.create_voice_clone_prompt(source)
                self.assertEqual(len(calls),2)

    def test_complete_sentence_before_cut_off_tail(self):
        words = [
            {'text': ' Eu sabia.', 'timestamp': (0, 1.7)},
            {'text': ' Eu devia ter vindo de calça branca.', 'timestamp': (2, 3.98)},
            {'text': ' Devem', 'timestamp': (4.34, 4.7)},
            {'text': ' sonho.', 'timestamp': (14.98, 14.98)},
        ]
        end, text = select_complete_reference(words, 15.003)
        self.assertAlmostEqual(end, 4.13)
        self.assertEqual(text, 'Eu sabia. Eu devia ter vindo de calça branca.')

    def test_do_not_cut_continuous_words_or_incomplete_tail(self):
        self.assertIsNone(select_complete_reference([
            {'text': ' Frase.', 'timestamp': (0, 4)},
            {'text': ' Outra', 'timestamp': (4.02, 5)},
            {'text': ' sonho.', 'timestamp': (5, 5)},
        ], 5.01))

    def test_no_timestamp_is_safe(self):
        self.assertIsNone(select_complete_reference([
            {'text': ' Frase.', 'timestamp': (None, None)}], 15))

    def test_no_specific_word_is_removed(self):
        self.assertEqual(select_complete_reference([
            {'text': ' Este é meu sonho.', 'timestamp': (0, 4)}], 5)[1], 'Este é meu sonho.')

    def test_only_managed_omnivoice_is_wrapped(self):
        command = ['python', '-u', '-c', 'print(1)', '--text', 'Sonho!']
        for model in ['Qwen/Qwen3-TTS', 'hotstone228/F5-TTS-Russian']:
            self.assertEqual(protect_reference_command(command, model), command)
        result = protect_reference_command(command, 'edwixx/omnivoice-brpt-v15')
        self.assertEqual(result[4:], command[4:])
        self.assertEqual(command[3], 'print(1)')
        compile(result[3], '<worker>', 'exec')


if __name__ == '__main__':
    unittest.main()
