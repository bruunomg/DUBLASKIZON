"""Exercise the actual adapter worker with a fake model, without GPU or downloads."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import wave
import numpy as np
import qwen_backend as backend


class QwenTests(unittest.TestCase):
    def test_language_and_mode_validation(self):
        backend.validate('Portuguese');backend.validate('ru')
        for lang,mode in [('unknown','clone'),('pt','design'),('pt','auto')]:
            with self.assertRaises(ValueError):backend.validate(lang,mode)

    def test_system_voice_output_is_a_valid_windows_filename(self):
        from text_to_speech_tab import output_location
        with tempfile.TemporaryDirectory() as folder:
            output=output_location(folder,'system',None,'QWEN_SPEAKER:Ryan')
            self.assertNotIn(':',output.name)

    def test_verified_qwen_reactions_join_the_existing_reference_bank(self):
        import native_emotions
        donor=Path('verified-grito.wav')
        with patch('qwen_backend.emotional_references',return_value={'grito':donor}):
            refs=native_emotions.native_references('feminina')
        self.assertEqual(refs['grito'],donor)
        self.assertTrue(refs['neutro'].is_file())

    def test_shared_dispatch_preserves_other_backends(self):
        import batch_tab
        with patch('qwen_backend.inference_command',return_value=['qwen']) as qwen,patch('batch_tab.find_omnivoice_command',return_value=['omni']):
            self.assertEqual(batch_tab.find_voice_command(backend.MODEL),['qwen'])
            self.assertEqual(batch_tab.find_voice_command('edwixx/omnivoice-brpt-v15'),['omni'])
            qwen.assert_called_once()
        self.assertEqual(batch_tab.DEFAULT_MODEL_CHOICES[0][1],'edwixx/omnivoice-brpt-v15')
        self.assertIn(backend.MODEL,dict((v,k) for k,v in batch_tab.DEFAULT_MODEL_CHOICES))

    def test_manifest_only_exposes_current_verified_audio_inside_cache(self):
        with tempfile.TemporaryDirectory() as folder,patch('qwen_backend.root',return_value=Path(folder)):
            root=Path(folder)/'emotion-previews';root.mkdir();audio=root/'calmo.wav';audio.write_bytes(b'valid-audio')
            item={'file':audio.name,'sha256':hashlib.sha256(audio.read_bytes()).hexdigest()}
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'version':backend.VERSION,'voices':{'masculina':{'calmo':item,'grito':{'file':'../outside.wav','sha256':'wrong'}}}}))
            self.assertEqual(backend.emotional_references(),{'calmo':audio})
            audio.write_bytes(b'corrupt');self.assertEqual(backend.emotional_references(),{})

    def _worker(self,folder,args):
        model=Mock()
        samples=np.linspace(-.1,.1,2400,dtype=np.float32)
        model.generate_custom_voice.return_value=([samples],24000)
        model.generate_voice_clone.return_value=([samples],24000)
        model.create_voice_clone_prompt.return_value='clone-prompt'
        factory=Mock();factory.from_pretrained.return_value=model
        def save(path,samples,sr,subtype):
            with wave.open(str(path),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(sr)
                wav.writeframes((np.asarray(samples)*32767).astype('<i2').tobytes())
        modules={'qwen_tts':SimpleNamespace(Qwen3TTSModel=factory),
                 'torch':SimpleNamespace(bfloat16='bf16',float32='fp32',cuda=SimpleNamespace(is_available=lambda:False,empty_cache=lambda:None)),
                 'soundfile':SimpleNamespace(write=save),
                 'librosa':SimpleNamespace(load=lambda *a,**k:(samples,24000)),
                 'huggingface_hub':SimpleNamespace(snapshot_download=lambda *a,**k:folder)}
        with patch.dict('sys.modules',modules),patch('sys.argv',['worker','--cache-root',folder,*args]),contextlib.redirect_stdout(io.StringIO()):
            exec(compile(backend.WORKER,'QwenWorker','exec'),{'__name__':'__main__'})
        return model

    def test_custom_voice_forwards_instruction_and_speaker(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'fala.wav'
            model=self._worker(folder,['--text','Olá! Tudo bem?','--output',str(output),'--instruct','QWEN_SPEAKER:Vivian Speak calmly.'])
            self.assertEqual(model.generate_custom_voice.call_count,2)
            call=model.generate_custom_voice.call_args.kwargs
            self.assertEqual(call['speaker'],'Vivian');self.assertEqual(call['language'],'Portuguese')
            self.assertIn('Speak calmly',call['instruct']);model.generate_voice_clone.assert_not_called()
            with wave.open(str(output)) as wav:self.assertEqual(wav.getnframes(),8400)

    def test_clone_preserves_reference_codes_and_does_not_use_target_text_as_transcript(self):
        with tempfile.TemporaryDirectory() as folder:
            ref=Path(folder)/'ref.wav';ref.write_bytes(b'reference')
            output=Path(folder)/'fala.wav'
            model=self._worker(folder,['--text','Texto novo','--ref_audio',str(ref),'--ref_text','Texto da referência','--output',str(output)])
            self.assertFalse(model.create_voice_clone_prompt.call_args.kwargs['x_vector_only_mode'])
            self.assertEqual(model.create_voice_clone_prompt.call_args.kwargs['ref_text'],'Texto da referência')
            self.assertEqual(model.generate_voice_clone.call_args.kwargs['voice_clone_prompt'],'clone-prompt')
            model.generate_custom_voice.assert_not_called();self.assertTrue(output.is_file())

    def test_generated_previews_resume_without_generating_duplicates(self):
        with tempfile.TemporaryDirectory() as folder,patch('qwen_backend.root',return_value=Path(folder)):
            bank=Path(folder)/'emotion-previews'
            self.assertEqual(self._worker(folder,['--emotion-bank',str(bank)]).generate_custom_voice.call_count,10)
            self.assertEqual(set(backend.emotional_references()),set(backend.STYLES))
            self._worker(folder,['--emotion-bank',str(bank)]).generate_custom_voice.assert_not_called()

    def test_empty_text_fails_before_model_import_or_output(self):
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):self._worker(folder,['--text',' ','--output',str(Path(folder)/'empty.wav')])
            self.assertFalse((Path(folder)/'empty.wav').exists())


if __name__=='__main__':unittest.main()
