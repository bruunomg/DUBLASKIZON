import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fish_backend as fish
from text_to_speech_tab import render_expression_text

# Historical backend checks remain independent of the removed TTS UI engine.
def render_fish_text(source):
    import re
    def replace(match):
        return fish.EMOTIONS.get(match.group(2).strip().casefold(),'') if match.group(1).casefold()=='expressao' else ''
    return re.sub(r'\[\[(EXPRESSAO|VOZ):([^\]]+)\]\]',replace,source,flags=re.IGNORECASE).strip(),[]


class FishTests(unittest.TestCase):
    def _verify_generated_sample(self,heard):
        import io,re,difflib,unicodedata
        import numpy as np
        from types import SimpleNamespace
        from contextlib import redirect_stdout
        from unittest.mock import Mock
        code='    def tokens'+fish.INFERENCE_WORKER.split('    def tokens',1)[1].split("'''",1)[0]
        import textwrap
        code=textwrap.dedent(code)
        engine=Mock();engine.inference.return_value=[SimpleNamespace(code='final',audio=(24000,np.zeros(1000)),error=None)]
        verifier=Mock();verifier.transcribe.return_value=([SimpleNamespace(text=heard)],None)
        sf=Mock();log=io.StringIO()
        scope=dict(re=re,difflib=difflib,unicodedata=unicodedata,np=np,sf=sf,engine=engine,verifier=verifier,
                   librosa=SimpleNamespace(resample=lambda audio,**kw:audio),refs=[],ServeTTSRequest=lambda **kw:SimpleNamespace(**kw),
                   data={'segments':['ei! André! vem aqui'],'output':'test.wav','seed':1})
        with redirect_stdout(log):
            try:exec(code,scope)
            except RuntimeError as exc:return sf,engine,log.getvalue(),exc
        return sf,engine,log.getvalue(),None

    def test_borderline_recognition_is_saved_for_review_after_retries(self):
        sf,engine,log,error=self._verify_generated_sample('Ei, André, venga aqui!')
        self.assertIsNone(error)
        self.assertEqual(engine.inference.call_count,4)
        sf.write.assert_called_once()
        self.assertIn('PARA CONFERIR, não confirmada como completa',log)

    def test_missing_end_is_not_saved_as_finished_audio(self):
        sf,engine,log,error=self._verify_generated_sample('Ei! André!')
        self.assertIsInstance(error,RuntimeError)
        self.assertEqual(engine.inference.call_count,4)
        sf.write.assert_not_called()

    def test_short_punctuation_keeps_every_phrase_for_generation(self):
        self.assertEqual(fish.speech_segments('ei! André! vem aqui'),['ei! André!','vem aqui'])
        self.assertEqual(fish.speech_segments('(shouting) ei! André! vem aqui'),['(shouting) ei! André!','(shouting) vem aqui'])
    def test_s1_reference_and_new_text_share_speaker_identifier(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,MagicMock
        code='def generate_s1'+fish.INFERENCE_WORKER.split('def generate_s1',1)[1].split('q=queue.Queue()',1)[0]
        sequence=Mock();encoded=Mock();encoded.to.return_value=encoded;encoded.size.return_value=100
        sequence.encode_for_inference.return_value=encoded
        result=MagicMock();result.__getitem__.return_value.clone.return_value='codes'
        generate=Mock(return_value=result)
        scope=dict(ContentSequence=Mock(return_value=sequence),TextPart=lambda **k:SimpleNamespace(**k),
                   VQPart=lambda **k:SimpleNamespace(**k),torch=SimpleNamespace(tensor=lambda v,**k:v),
                   generate=generate,GenerateResponse=lambda **k:SimpleNamespace(**k))
        exec(code,scope)
        reference=Mock();reference.cpu.return_value='reference codes'
        model=SimpleNamespace(tokenizer='tokenizer',config=SimpleNamespace(num_codebooks=10,max_seq_len=8192))
        responses=list(scope['generate_s1'](model=model,decode_one_token='decode',device='cpu',text='(whispering) Texto novo.',prompt_text=['Fala da referência.'],prompt_tokens=[reference]))
        calls=sequence.append.call_args_list
        self.assertEqual(calls[0].kwargs,{'add_end':True,'speaker':0})
        self.assertEqual(calls[1].kwargs,{'speaker':0})
        self.assertEqual(calls[0].args[0][0].text,'Fala da referência.')
        self.assertEqual(calls[1].args[0].text,'(whispering) Texto novo.')
        self.assertEqual([r.action for r in responses],['sample','next'])

    def test_more_official_reactions_keep_following_words(self):
        text=render_fish_text('[[EXPRESSAO:grito]] Saia daqui! [[EXPRESSAO:choro]] Eu preciso de ajuda.')[0]
        self.assertEqual(fish.speech_segments(text),['(shouting) Saia daqui!','(sobbing)','(shouting) Eu preciso de ajuda.'])
        self.assertEqual(render_fish_text('[[EXPRESSAO:grito_forte]] Socorro!')[0],'(screaming) Socorro!')
        self.assertEqual(render_fish_text('[[EXPRESSAO:choro_intenso]]')[0],'(crying loudly)')

    def test_user_whisper_and_sigh_are_separate_without_losing_words(self):
        text=render_fish_text('[[EXPRESSAO:sussurro]] ei! André! [[EXPRESSAO:suspiro]] vem aqui')[0]
        self.assertEqual(fish.speech_segments(text),['(whispering) ei! André!','(sighing)','(whispering) vem aqui'])
        self.assertEqual(fish.speech_segments(render_fish_text('[[EXPRESSAO:sussurro]] olha! veja se eles ja foram embora')[0]),['(whispering) olha! veja se eles ja foram embora'])

    def test_long_text_repeats_emotion_and_preserves_all_words(self):
        original=' '.join('palavra'+str(i) for i in range(150))
        parts=fish.speech_segments('(sad) '+original)
        self.assertGreater(len(parts),1)
        self.assertTrue(all(part.startswith('(sad) ') for part in parts))
        self.assertEqual(' '.join(part.removeprefix('(sad) ') for part in parts),original)

    def test_auto_reference_transcription_keeps_requested_text_and_reuses_cache(self):
        import sys,io
        import numpy as np
        from contextlib import redirect_stdout
        from types import SimpleNamespace
        from unittest.mock import Mock
        code=fish.INFERENCE_WORKER.split('# The reference transcript',1)[1].split("os.environ['HF_HUB_OFFLINE']='1'\nos.environ['TRANSFORMERS_OFFLINE']='1'\nfrom huggingface_hub",1)[0]
        code='# The reference transcript'+code
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);reference=root/'voice.wav';reference.write_bytes(b'reference recording')
            recognizer=Mock()
            recognizer.transcribe.return_value=([SimpleNamespace(text='Esta é a referência.')],None)
            factory=Mock(return_value=recognizer)
            payload={'reference':str(reference),'reference_text':'','asr_root':str(root/'cache'),'text':'(joyful) Quero falar algo totalmente diferente!'}
            fake_sf=SimpleNamespace(read=lambda *a,**k:(np.zeros((1000,1),dtype=np.float32),16000))
            with patch.dict(sys.modules,{'faster_whisper':SimpleNamespace(WhisperModel=factory),'librosa':SimpleNamespace()}),patch.dict('os.environ',{}),redirect_stdout(io.StringIO()):
                scope={'data':payload,'Path':Path,'sf':fake_sf,'os':__import__('os')}
                exec(code,scope)
                self.assertEqual(payload['reference_text'],'Esta é a referência.')
                self.assertEqual(payload['text'],'(joyful) Quero falar algo totalmente diferente!')
                self.assertIsInstance(recognizer.transcribe.call_args.args[0],np.ndarray)
                payload['reference_text']=''
                exec(code,scope)
            factory.assert_called_once()
            self.assertEqual(payload['reference_text'],'Esta é a referência.')

    def test_authorization_survives_generic_setup_process_error(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);log=root/'setup.log'
            log.write_text('DUBLASKIZON_FISH_AUTH_REQUIRED: autentique sua conta',encoding='utf-8')
            job=Mock(log=log);job.run.side_effect=RuntimeError('Comando falhou (código 42)')
            with patch('dependency_setup.runtime_root',return_value=root),patch.object(fish,'runtime',return_value=(root/'python.exe','cpu')):
                with self.assertRaisesRegex(RuntimeError,'Autorize o acesso'):fish.download(job)
            log.write_text('Connection timed out',encoding='utf-8')
            with patch('dependency_setup.runtime_root',return_value=root),patch.object(fish,'runtime',return_value=(root/'python.exe','cpu')):
                with self.assertRaisesRegex(RuntimeError,'Comando falhou'):fish.download(job)

    def test_missing_file_download_supports_hub_without_tqdm_class_parameter(self):
        import io,sys
        from contextlib import redirect_stdout
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);calls=[]
            info=SimpleNamespace(sha='new-revision',siblings=[SimpleNamespace(rfilename='model.pth',size=7)])
            # Real Hub 0.36 API: intentionally no **kwargs or tqdm_class.
            def strict_download(repo_id,filename,*,revision,token,cache_dir,force_download):
                calls.append((repo_id,filename,force_download))
                cached=root/filename;cached.write_bytes(b'weights');return str(cached)
            hub=SimpleNamespace(HfApi=lambda:SimpleNamespace(model_info=lambda *a,**k:info),
                                hf_hub_download=strict_download,try_to_load_from_cache=lambda *a,**k:None,
                                snapshot_download=lambda *a,**k:str(root/'snapshot'))
            with patch.dict(sys.modules,{'huggingface_hub':hub,'tqdm.auto':SimpleNamespace(tqdm=object),'huggingface_hub.utils.tqdm':SimpleNamespace(tqdm=object),'huggingface_hub.file_download':SimpleNamespace(tqdm=object)}),patch.object(sys,'argv',['download',str(root),'0','']),redirect_stdout(io.StringIO()):
                exec(compile(fish.DOWNLOAD_WORKER,'download-worker','exec'),{})
            self.assertEqual(calls,[('fishaudio/s1-mini','model.pth',False)])
            self.assertEqual((root/'model.pth').read_bytes(),b'weights')

    def test_verification_handles_namespace_package_with_no_file(self):
        import sys
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            package=root/('fish-speech-'+fish.SOURCE_COMMIT)/'fish_speech'
            codec=package/'models'/'dac'/'inference.py';codec.parent.mkdir(parents=True);codec.touch()
            config=package/'configs'/'modded_dac_vq.yaml';config.parent.mkdir();config.touch()
            modules={'torch':SimpleNamespace(__version__='2.8.0+cu128',version=SimpleNamespace(cuda='12.8'),cuda=SimpleNamespace(is_available=lambda:True),ones=lambda *a,**k:1),
                     'torchaudio':SimpleNamespace(__version__='2.8.0+cu128'),'transformers':SimpleNamespace(__version__='4.51.3'),'numpy':SimpleNamespace(__version__='1.26.4'),
                     'fish_speech':SimpleNamespace(__file__=None),
                     'fish_speech.inference_engine':SimpleNamespace(TTSInferenceEngine=object),
                     'fish_speech.models.dac':SimpleNamespace(inference=SimpleNamespace(__file__=str(codec)))}
            class Job:
                def write(self,text):pass
                def checkpoint(self):pass
                def run(self,args,**kwargs):
                    if '-c' in args:exec(args[args.index('-c')+1],{})
                def ensure_amd_python(self):raise AssertionError('Reinstalação indevida de namespace válido')
            with patch.dict(sys.modules,modules),patch('dependency_setup.runtime_root',return_value=root),patch.object(fish,'runtime',return_value=(root/'python.exe','cu128')):
                fish.install(Job(),'cu128')

    def test_cached_model_does_not_download_files_again(self):
        import io,sys
        from contextlib import redirect_stdout
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cached=root/'cached.pth';cached.write_bytes(b'weights')
            info=SimpleNamespace(sha='current-revision',siblings=[SimpleNamespace(rfilename='model.pth',size=7)])
            download=Mock()
            hub=SimpleNamespace(HfApi=lambda:SimpleNamespace(model_info=lambda *a,**k:info),
                                hf_hub_download=download,try_to_load_from_cache=lambda *a,**k:str(cached),
                                snapshot_download=Mock(return_value=str(root/'snapshot')))
            with patch.dict(sys.modules,{'huggingface_hub':hub,'tqdm.auto':SimpleNamespace(tqdm=object),'huggingface_hub.utils.tqdm':SimpleNamespace(tqdm=object),'huggingface_hub.file_download':SimpleNamespace(tqdm=object)}),patch.object(sys,'argv',['download',str(root),'0','']),redirect_stdout(io.StringIO()) as logs:
                exec(compile(fish.DOWNLOAD_WORKER,'download-worker','exec'),{})
            download.assert_not_called()
            self.assertIn('nenhum arquivo baixado',logs.getvalue())
            self.assertEqual((root/'fish-model.txt').read_text(encoding='utf-8'),str(root/'snapshot'))

    def test_compatible_install_does_not_create_environment_or_download(self):
        from unittest.mock import Mock
        job=Mock()
        with tempfile.TemporaryDirectory() as folder,patch('dependency_setup.runtime_root',return_value=Path(folder)),patch.object(fish,'runtime',return_value=(Path('existing.exe'),'cu128')):
            fish.install(job,'cu128')
            job.ensure_amd_python.assert_not_called()
            self.assertEqual(job.run.call_count,2)
            for call in job.run.call_args_list:
                self.assertNotIn('install',call.args[0])
                self.assertNotIn('venv',call.args[0])
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_broken_or_changed_environment_is_not_silently_reused(self):
        from unittest.mock import Mock
        for selected,current_mode,failed in [('cpu','cu128',False),('cu128','cu128',True)]:
            job=Mock()
            job.ensure_amd_python.side_effect=ValueError('new install requested')
            if failed:job.run.side_effect=RuntimeError('broken import')
            with tempfile.TemporaryDirectory() as folder,patch('dependency_setup.runtime_root',return_value=Path(folder)),patch.object(fish,'runtime',return_value=(Path('existing.exe'),current_mode)):
                with self.assertRaisesRegex(ValueError,'new install'):fish.install(job,selected)
                job.ensure_amd_python.assert_called_once()

    def test_emotions_remain_at_cursor_and_do_not_change_omnivoice(self):
        source='Olá [[EXPRESSAO:triste]] não vá. [[EXPRESSAO:alegre]] Você voltou!'
        self.assertEqual(render_fish_text(source)[0],'Olá (sad) não vá. (joyful) Você voltou!')
        self.assertEqual(render_expression_text(source)[0],'Olá não vá. Você voltou!')
        self.assertEqual(render_fish_text('[[EXPRESSAO:sussurro]] Segredo [[EXPRESSAO:rindo]]')[0], '(whispering) Segredo (laughing)')

    def test_missing_environment_does_not_create_request(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(fish,'runtime',return_value=(None,'cpu')),patch.object(fish,'model_directory',return_value=None):
            output=Path(folder)/'scene.wav'
            with self.assertRaisesRegex(RuntimeError,'REQUISITOS'):fish.command({'text':'Olá'},output)
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_request_supports_long_text_and_keeps_real_output(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(fish,'runtime',return_value=(Path('python.exe'),'cpu')),patch.object(fish,'model_directory',return_value=Path('model')):
            output=Path(folder)/'scene.wav';output.write_bytes(b'original')
            long_text='Olá! '*15000
            args,request=fish.command({'text':long_text,'reference':'ref.wav','reference_text':'Minha referência'},output)
            self.assertNotIn(long_text,args)
            self.assertEqual(json.loads(request.read_text(encoding='utf-8'))['text'],long_text)
            self.assertEqual(output.read_bytes(),b'original')
            compile(fish.INFERENCE_WORKER,'fish-worker','exec')
            compile(fish.DOWNLOAD_WORKER,'fish-download','exec')

    def test_runtime_pointer_cannot_target_external_python(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'runtime';root.mkdir()
            external=Path(folder)/'external.exe';external.write_bytes(b'python')
            (root/'fish-active.json').write_text(json.dumps({'python':str(external)}),encoding='utf-8')
            with patch('dependency_setup.runtime_root',return_value=root):
                self.assertEqual(fish.runtime(),(None,'cpu'))


if __name__=='__main__':unittest.main()
