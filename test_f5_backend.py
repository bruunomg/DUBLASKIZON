import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import wave
from types import SimpleNamespace as NS, ModuleType
import unittest
from unittest.mock import Mock, patch

import batch_tab
import dependency_setup as setup
import f5_backend as f5
import i18n


class F5Tests(unittest.TestCase):
    def test_review_f5_keeps_backup_and_destination(self):
        import review_tab as review
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);target=root/'dublado'/'scene.wav';target.parent.mkdir();target.write_bytes(b'old')
            reference=root/'ref.wav';reference.write_bytes(b'reference')
            app=review.ReviewApp.__new__(review.ReviewApp)
            app.root=NS(after=Mock());app.config={'model':f5.MODEL,'language':'Russian','instruct':''}
            def run(command,**kwargs):
                self.assertEqual(command[0],'f5')
                self.assertEqual(command[command.index('--ref_audio')+1],str(reference))
                Path(command[command.index('--output')+1]).write_bytes(b'new')
                return NS(returncode=0,stdout='Audio saved')
            app._run_cancellable_generation=run
            with patch.object(review,'REVISIONS_DIR',root/'revisoes'),patch.object(review,'CUSTOM_OUTPUT_DIR',root/'custom'),patch.object(batch_tab,'find_voice_command',return_value=['f5']):
                app._run_generation('scene','Привет!',target,target,reference)
            self.assertEqual(target.read_bytes(),b'new')
            self.assertEqual((root/'revisoes'/'scene_v01.wav').read_bytes(),b'old')

    def test_f5_parts_publish_separately(self):
        import scene_parts
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);reference=root/'ref.wav';reference.write_bytes(b'reference')
            context={'root':root,'scene':'scene','source':'dublado','config':{'model':f5.MODEL,'language':'Russian','instruct':''}}
            def run(command,cancel):
                self.assertEqual(command[0],'f5')
                with wave.open(command[command.index('--output')+1],'wb') as wav:
                    wav.setparams((1,2,24000,0,'NONE','not compressed'));wav.writeframes(b'\1\0'*2400)
            with patch.object(f5,'inference_command',return_value=['f5']):
                result=scene_parts.generate_part(context,'Привет!',reference,threading.Event(),run)
            self.assertTrue(result['audio'].is_file())
            self.assertEqual(result['text'].read_text(encoding='utf-8').strip(),'Привет!')
            self.assertEqual(reference.read_bytes(),b'reference')

    def test_model_selection_all_languages(self):
        for language in ('pt','en','ru','es'):
            app=NS(model_var=NS(get=lambda:i18n.tr(f5.LABEL,language)+' [cache local]'),model_choices=batch_tab.DEFAULT_MODEL_CHOICES)
            self.assertEqual(batch_tab.BatchApp.selected_model_id(app),f5.MODEL)

    def test_dispatch_does_not_use_omni_for_f5(self):
        with patch.object(f5,'inference_command',return_value=['f5']) as new,patch.object(batch_tab,'find_omnivoice_command',return_value=['omni']) as old:
            self.assertEqual(batch_tab.find_voice_command(f5.MODEL),['f5'])
            old.assert_not_called()
            self.assertEqual(batch_tab.find_voice_command(batch_tab.MODEL),['omni'])
            new.assert_called_once()

    def test_validate_language_and_mode(self):
        for language in ('Russian','English','ru','en'):f5.validate(language)
        for language,mode in [('Portuguese','clone'),('Russian','design'),('Russian','auto')]:
            with self.assertRaises(ValueError):f5.validate(language,mode)

    def test_batch_keeps_russian_reference_and_model(self):
        app=NS(scene_translation_language='Russian',selected_r_pronunciation='unchanged',infer_prefix=['f5'],
               selected_model=f5.MODEL,selected_mode='clone',selected_instruct='',audio_by_stem={'scene':Path('reference.wav')})
        cmd=batch_tab.BatchApp.build_infer_command(app,'scene','Привет!',Path('dub.wav'))
        self.assertEqual(cmd[0],'f5')
        self.assertEqual(cmd[cmd.index('--model')+1],f5.MODEL)
        self.assertEqual(cmd[cmd.index('--ref_audio')+1],'reference.wav')
        self.assertEqual(cmd[cmd.index('--text')+1],'Привет!')

    def test_runtime_rejects_escape_and_keeps_omni_pointer(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(setup,'runtime_root',return_value=Path(temp)):
            root=Path(temp);(root/'active.json').write_text('{"python":"omni"}')
            (root/'f5-active.json').write_text('{"python":"../outside.exe"}')
            self.assertIsNone(f5.runtime()[0])
            self.assertEqual((root/'active.json').read_text(),'{"python":"omni"}')

    def test_failed_install_does_not_activate_or_replace_omni(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(setup,'runtime_root',return_value=Path(temp)):
            root=Path(temp);old=root/'active.json';old.write_text('old omni')
            job=NS(ensure_base_python=lambda:root/'base.exe',run=Mock(side_effect=RuntimeError('pip failed')),write=Mock())
            with self.assertRaisesRegex(RuntimeError,'pip failed'):f5.install(job,'cpu')
            self.assertFalse((root/'f5-active.json').exists())
            self.assertEqual(old.read_text(),'old omni')

    def test_download_routes_required_models_even_without_optional_whisper(self):
        job=setup.SetupJob.__new__(setup.SetupJob)
        with patch.object(f5,'download') as download:
            job.download_models(f5.MODEL,False,True)
            download.assert_called_once_with(job,True)
        with patch.object(f5,'test') as test:
            job.test_model(f5.MODEL,False)
            test.assert_called_once_with(job)

    def test_download_filters_and_reuses_cache(self):
        downloads=[]
        hub=ModuleType('huggingface_hub')
        hub.HfApi=lambda **k:NS(model_info=lambda *a,**kw:NS(sha='abc',siblings=[
            NS(rfilename='model_last.pt',size=3380000000),NS(rfilename='model_last.safetensors',size=1350000000),
            NS(rfilename='vocab.txt',size=13800),NS(rfilename='loss.svg',size=9000000)]))
        hub.try_to_load_from_cache=lambda *a,**k:__file__
        # Strict 0.36 public signature: the previous **kwargs mock hid the bug.
        hub.hf_hub_download=lambda repo,name,*,endpoint:downloads.append((repo,name))
        fake_tqdm=ModuleType('huggingface_hub.utils.tqdm');fake_tqdm.tqdm=type('Bar',(),{})
        args=['download',json.dumps({f5.MODEL:f5.FILES[f5.MODEL]}),'0']
        with patch.dict(sys.modules,{'huggingface_hub':hub,'huggingface_hub.utils.tqdm':fake_tqdm}),patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()) as out:
            exec(f5.DOWNLOAD_WORKER,{})
        self.assertEqual(downloads,[(f5.MODEL,'model_last.safetensors'),(f5.MODEL,'vocab.txt')])
        self.assertIn('"missing": 0',out.getvalue())
        downloads.clear();args[-1]='1'
        with patch.dict(sys.modules,{'huggingface_hub':hub,'huggingface_hub.utils.tqdm':fake_tqdm}),patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
            exec(f5.DOWNLOAD_WORKER,{})
        self.assertFalse(downloads)

    def test_worker_transcribes_reference_before_synthesis_and_uses_custom_vocab(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('config.yaml','pytorch_model.bin','model.safetensors','reference.wav','vocab.txt'):(root/name).touch()
            hub=ModuleType('huggingface_hub');hub.hf_hub_download=lambda repo,name,**k:str(root/name)
            hub.snapshot_download=lambda *a,**k:str(root)
            events=[]
            utils=NS(initialize_asr_pipeline=lambda **k:events.append(('asr',k)),
                     preprocess_ref_audio_text=lambda audio,text:(events.append(('ref',audio,text)) or ('cropped.wav','original words')),
                     infer_process=lambda *a,**k:(events.append(('generate',a,k)) or ([.1,.2],24000,None)))
            api=ModuleType('f5_tts.api')
            api.F5TTS=lambda **k:(events.append(('model',k)) or NS(ema_model='weights',vocoder='vocoder',mel_spec_type='vocos'))
            infer=ModuleType('f5_tts.infer');infer.utils_infer=utils
            torch=ModuleType('torch');torch.float32='fp32';torch.cuda=NS(is_available=lambda:False)
            sf=ModuleType('soundfile');sf.write=Mock()
            pipelines=ModuleType('transformers.pipelines');pipelines.automatic_speech_recognition=NS()
            np=ModuleType('numpy');np.isfinite=lambda x:NS(all=lambda:True)
            args=['worker','--ref_audio',str(root/'reference.wav'),'--text','Привет!','--output',str(root/'out.wav')]
            with patch.dict(sys.modules,{'huggingface_hub':hub,'f5_tts.api':api,'f5_tts.infer':infer,'torch':torch,'soundfile':sf,'numpy':np,'transformers.pipelines':pipelines}),patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
                exec(f5.WORKER,{})
            self.assertEqual([e[0] for e in events],['asr','ref','model','generate'])
            self.assertEqual(events[0][1]['device'],'cpu')
            self.assertEqual(events[1][2],'')
            self.assertEqual(events[2][1]['model'],'F5TTS_Base')
            self.assertEqual(events[2][1]['vocab_file'],str(root/'vocab.txt'))
            self.assertEqual(events[3][1][:3],('cropped.wav','original words','Привет!'))
            self.assertIsNone(utils.asr_pipe)
            sf.write.assert_called_once_with(str(root/'out.wav'),[.1,.2],24000,subtype='PCM_16')


if __name__=='__main__':unittest.main()
