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
                     'soundfile':types.SimpleNamespace(info=lambda p:types.SimpleNamespace(samplerate=24000,duration=1),read=lambda *a,**k:(np.ones((24000,1),dtype='float32'),24000)),
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

    def test_long_reference_is_bounded_even_without_sentence_timestamps(self):
        import tempfile,types,os
        from pathlib import Path
        from unittest.mock import patch
        import numpy as np
        class Engine:
            def create_voice_clone_prompt(self,audio,text=None,preprocess=True):return (audio,text,preprocess)
        engine=Engine();responses=iter(['This','This','Esta é uma referência com voz clara.'])
        engine._asr_pipe=lambda *a,**k:{'text':next(responses),'chunks':[]}
        reads=[]
        def read(path,**kwargs):
            reads.append(kwargs['frames']);return np.ones((kwargs['frames'],1),dtype='float32'),16000
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'original.wav';source.write_bytes(b'original')
            modules={'omnivoice.models.omnivoice':types.SimpleNamespace(OmniVoice=Engine),
                     'soundfile':types.SimpleNamespace(info=lambda p:types.SimpleNamespace(samplerate=16000,duration=180),read=read,write=lambda *a,**k:Path(a[0]).write_bytes(b'cache')),
                     'librosa':types.SimpleNamespace(resample=lambda value,**kwargs:value)}
            with patch.dict('sys.modules',modules),patch.dict(os.environ,{'LOCALAPPDATA':folder}):
                exec(WORKER_CODE,{})
                audio,text,preprocess=engine.create_voice_clone_prompt(source,'Transcrição de três minutos.')
            self.assertEqual(reads,[320000,128000])
            self.assertEqual(len(audio[0]),128000)
            self.assertEqual(source.read_bytes(),b'original')
            self.assertTrue(text)

    def test_long_chinese_reference_uses_validated_excerpt_and_preserves_original(self):
        import tempfile,types,os
        from pathlib import Path
        from unittest.mock import patch
        import numpy as np
        class Engine:
            def create_voice_clone_prompt(self,audio,text=None,preprocess=True):return (audio,text,preprocess)
        engine=Engine();responses=iter(['This','This','星星偷走了太阳，世界就要崩溃了，我们该怎么办？'])
        engine._asr_pipe=lambda *a,**k:{'text':next(responses),'chunks':[]}
        def read(path,**kwargs):
            positive=np.ones(kwargs['frames'],dtype='float32')*.1
            return np.column_stack((positive,-positive)),16000
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'original.wav';source.write_bytes(b'original')
            modules={'omnivoice.models.omnivoice':types.SimpleNamespace(OmniVoice=Engine),
                     'soundfile':types.SimpleNamespace(info=lambda p:types.SimpleNamespace(samplerate=16000,duration=71),read=read,write=lambda *a,**k:Path(a[0]).write_bytes(b'cache')),
                     'librosa':types.SimpleNamespace(resample=lambda value,**kwargs:value)}
            with patch.dict('sys.modules',modules),patch.dict(os.environ,{'LOCALAPPDATA':folder}):
                exec(WORKER_CODE,{})
                audio,text,preprocess=engine.create_voice_clone_prompt(source)
            self.assertTrue(text.startswith('星星'));self.assertGreater(float(np.max(np.abs(audio[0]))),.09)
            self.assertEqual(len(audio[0]),128000);self.assertFalse(preprocess);self.assertEqual(source.read_bytes(),b'original')

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
