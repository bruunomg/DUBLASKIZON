import ast
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
import audio_translation as translation
import batch_tab


class Tests(unittest.TestCase):
    def test_dialog_disables_unused_model_when_engine_changes(self):
        import tkinter as tk
        from tkinter import ttk
        from contextlib import ExitStack
        widgets=[]
        class Widget:
            def __init__(self,*args,**kwargs):self.kw=kwargs;self.value=kwargs.get('value');self.callbacks=[];widgets.append(self)
            def get(self):return self.value
            def set(self,value):
                self.value=value
                for callback in self.callbacks:callback()
            def trace_add(self,event,callback):self.callbacks.append(callback)
            def configure(self,**kwargs):self.kw.update(kwargs)
            def state(self,*args):pass
            def pack(self,*args,**kwargs):pass
            def grid(self,*args,**kwargs):pass
            def columnconfigure(self,*args,**kwargs):pass
            def title(self,*args):pass
            def geometry(self,*args):pass
            def minsize(self,*args):pass
            def transient(self,*args):pass
            def grab_set(self):pass
            def protocol(self,*args):pass
            def winfo_exists(self):return True
            def after(self,*args):pass
            def lookup(self,*args):return '#202938'
            def yview(self,*args):pass
            def wait_window(inner):
                engine=next(w for w in widgets if w.value=='faster-whisper')
                faster=next(w for w in widgets if w.kw.get('textvariable') and w.kw['textvariable'].get()=='small')
                whisper=next(w for w in widgets if w.kw.get('textvariable') and w.kw['textvariable'].get()=='medium')
                self.assertEqual(faster.kw['state'],'readonly');self.assertEqual(whisper.kw['state'],'disabled')
                engine.set('openai-whisper')
                self.assertEqual(faster.kw['state'],'disabled');self.assertEqual(whisper.kw['state'],'readonly')
        with ExitStack() as stack:
            for module,names in ((tk,('Toplevel','StringVar','Text')),(ttk,('Style','Frame','Label','Combobox','Button','Progressbar','LabelFrame','Scrollbar'))):
                for name in names:stack.enter_context(patch.object(module,name,Widget))
            translation.choose_settings(None)

    def test_ollama_running_is_reused(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"models":[]}')),patch('subprocess.Popen') as launch:
            self.assertEqual(translation.ensure_ollama(lambda text:None),{'models':[]})
            launch.assert_not_called()

    def test_ollama_closed_starts_local_server(self):
        from urllib.error import URLError
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/'ollama.exe';exe.write_bytes(b'exe')
            with patch('urllib.request.urlopen',side_effect=[URLError('refused'),io.BytesIO(b'{"models":[]}')]),patch('shutil.which',return_value=str(exe)),patch('subprocess.Popen') as launch:
                self.assertEqual(translation.ensure_ollama(lambda text:None),{'models':[]})
                self.assertEqual(launch.call_args.args[0],[str(exe),'serve'])
                self.assertEqual(launch.call_args.kwargs['env']['OLLAMA_HOST'],'127.0.0.1:11434')

    def test_ollama_missing_has_actionable_error(self):
        from urllib.error import URLError
        with patch('urllib.request.urlopen',side_effect=URLError('refused')),patch('shutil.which',return_value=None),patch.object(Path,'is_file',return_value=False),patch('subprocess.Popen') as launch:
            with self.assertRaisesRegex(RuntimeError,'OLLAMA OFICIAL'):translation.ensure_ollama()
            launch.assert_not_called()

    def test_download_bytes_and_unknown_total(self):
        events=[];reporter=translation.DownloadProgress(lambda text:None,lambda *args:events.append(args))
        reporter('Progress 1048576 of 2097152\n')
        self.assertEqual(events[-1],('download',50,'1.0 MB / 2.0 MB'))
        reporter('Progress 1048576 of 0\n')
        self.assertEqual(events[-1][1],0)
        self.assertIn('total não informado',events[-1][2])

    def test_separate_python_install_without_omnivoice_pointer(self):
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'python.exe';base.write_bytes(b'python')
            commands=[];events=[]
            class Job:
                def __init__(self,*args,**kwargs):pass
                def checkpoint(self):pass
                def run(self,args,**kwargs):
                    commands.append(args)
                    if 'venv' in args:
                        directory=Path(args[-1]);(directory/'Scripts').mkdir(parents=True)
                        (directory/'Scripts'/'python.exe').write_bytes(b'python')
            with patch.object(translation,'runtime_root',return_value=root),patch.object(translation,'python_candidates',return_value=[base]),patch.object(translation,'SetupJob',Job):
                translation.install_dependencies(translation.settings(),lambda text:None,threading.Event(),lambda *args:events.append(args))
            self.assertTrue((root/'translation-active.json').exists())
            self.assertFalse((root/'active.json').exists())
            self.assertTrue(any('raw' in command for command in commands))
            self.assertEqual(events[-1][1],100)

    def test_existing_translation_environment_is_reused_without_install(self):
        import threading
        commands=[];messages=[]
        class Job:
            def __init__(self,*args,**kwargs):pass
            def checkpoint(self):pass
            def run(self,args,**kwargs):commands.append(args)
        with patch.object(translation,'translation_python',return_value=Path('ready/python.exe')),patch.object(translation,'SetupJob',Job),patch.object(translation,'python_candidates',side_effect=AssertionError('must reuse existing')):
            translation.install_dependencies(translation.settings(),messages.append,threading.Event())
        self.assertFalse(any('venv' in c or 'pip' in c for c in commands))
        self.assertTrue(any(translation.PREPARE_WORKER in c for c in commands))
        self.assertTrue(any('Reutilizando' in line for line in messages))

    def test_preparation_reuses_cached_model_and_ollama(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for name in ('config.json','model.bin','tokenizer.json'):(folder/name).write_bytes(b'cached')
            calls=[];lines=[]
            def model(name,**kwargs):
                calls.append(kwargs);self.assertTrue(kwargs.get('local_files_only'));return str(folder)
            utils=ModuleType('faster_whisper.utils');utils.download_model=model
            faster=ModuleType('faster_whisper');faster.utils=utils
            config=translation.settings({'translator':'translategemma-local'})
            modules={'faster_whisper':faster,'faster_whisper.utils':utils,'tqdm.auto':SimpleNamespace(tqdm=object)}
            with patch.dict(sys.modules,modules),patch.object(sys,'argv',['worker',json.dumps(config)]),patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"models":[{"name":"translategemma:4b"}]}')),patch('builtins.print',side_effect=lambda *a,**k:lines.append(str(a[0]))):
                exec(translation.PREPARE_WORKER,{})
            self.assertEqual(len(calls),1)
            self.assertEqual(sum('JÁ DISPONÍVEL:' in line for line in lines),2)

    def test_settings_and_missing_audio_queue(self):
        self.assertEqual(translation.settings()['repository'],'')
        self.assertEqual(translation.settings({'translator':'qwen-game-local'})['repository'],'qwen2.5:7b')
        self.assertEqual(translation.settings({'translator':'translategemma-local'})['repository'],'translategemma:4b')
        app=batch_tab.BatchApp.__new__(batch_tab.BatchApp) if hasattr(batch_tab,'BatchApp') else None
        if app is None:
            cls=next(value for value in vars(batch_tab).values() if isinstance(value,type) and hasattr(value,'available_translation_stems'))
            app=cls.__new__(cls)
        app.audio_by_stem={'one':1,'two':2};app.text_by_stem={'one':1}
        app.auto_translation_var=SimpleNamespace(get=lambda:'0')
        self.assertEqual(app.available_translation_stems(),['one'])
        app.auto_translation_var=SimpleNamespace(get=lambda:'1')
        self.assertEqual(app.available_translation_stems(),['one','two'])

    def worker(self, engine, backend, text='Hello there', same_language=False, gpu_failure=None):
        with tempfile.TemporaryDirectory() as tmp:
            request=Path(tmp)/'request.json';result=Path(tmp)/'result.json'
            config=translation.settings(dict(engine=engine,translator=backend,language='Português (Brasil)'))
            if gpu_failure:config['device']='cuda'
            request.write_text(json.dumps({'audio':'scene.wav','settings':config}),encoding='utf-8')
            language='pt' if same_language else 'en'
            faster=SimpleNamespace(WhisperModel=lambda *a,**k:SimpleNamespace(transcribe=lambda *a,**k:([SimpleNamespace(text=text,end=2)],SimpleNamespace(language=language))))
            devices=[]
            if gpu_failure:
                def model(*args,**kwargs):
                    device=kwargs['device'];devices.append((device,kwargs['compute_type']))
                    def segments():
                        if device=='cuda':
                            yield SimpleNamespace(text='PARCIAL QUE NÃO PODE SER DUPLICADO',end=1)
                            raise RuntimeError(gpu_failure)
                        yield SimpleNamespace(text=text,end=2)
                    return SimpleNamespace(transcribe=lambda *a,**k:(segments(),SimpleNamespace(language=language)))
                faster.WhisperModel=model
            whisper=SimpleNamespace(load_model=lambda *a,**k:SimpleNamespace(transcribe=lambda *a,**k:{'text':text,'language':language}))
            argos=ModuleType('argostranslate');package=ModuleType('argostranslate.package');translate=ModuleType('argostranslate.translate')
            translate.get_installed_languages=lambda:[SimpleNamespace(code='en',get_translation=lambda other:SimpleNamespace(translate=lambda text:'Olá')),SimpleNamespace(code='pt')]
            argos.package=package;argos.translate=translate
            calls=[]
            def urlopen(request,**kwargs):
                url=request if isinstance(request,str) else request.full_url
                calls.append(url)
                if url.endswith('/tags'):data={'models':[{'name':config['repository']}]}
                else:
                    body=json.loads(request.data);self.assertEqual(body['model'],config['repository']);self.assertEqual(body['keep_alive'],0)
                    data={'response':'Olá','done_reason':'stop'}
                return io.BytesIO(json.dumps(data).encode())
            modules={'faster_whisper':faster,'whisper':whisper,'argostranslate':argos,'argostranslate.package':package,'argostranslate.translate':translate}
            if gpu_failure:modules['torch']=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:False))
            with patch.dict(sys.modules,modules),patch.object(sys,'argv',['worker',str(request),str(result)]),patch('urllib.request.urlopen',side_effect=urlopen),patch('builtins.print'):
                exec(compile(translation.WORKER,'translation_worker','exec'),{})
            data=json.loads(result.read_text(encoding='utf-8'))
            self.assertEqual(data['translation'],text if same_language else 'Olá')
            self.assertEqual(data['transcript'],text)
            if gpu_failure:self.assertEqual(devices,[('cuda','float16'),('cpu','int8')])
            if backend!='argos' and not same_language:self.assertEqual(len(calls),2)

    def test_two_recognizers_and_three_translators(self):
        for engine in ('faster-whisper','openai-whisper'):
            for backend in translation.TRANSLATORS:
                with self.subTest(engine=engine,backend=backend):self.worker(engine,backend)

    def test_same_language_bypasses_translator(self):
        self.worker('faster-whisper','qwen-game-local',text='Olá',same_language=True)

    def test_cuda_dll_failure_during_iteration_restarts_whole_scene_on_cpu(self):
        self.worker('faster-whisper','argos',gpu_failure='Library cublas64_12.dll is not found or cannot be loaded')

    def test_unrelated_error_does_not_trigger_cpu_retry(self):
        with self.assertRaisesRegex(RuntimeError,'invalid audio'):
            self.worker('faster-whisper','argos',gpu_failure='invalid audio')

    def test_no_speech_stops(self):
        with self.assertRaisesRegex(RuntimeError,'detectada fala'):
            self.worker('faster-whisper','argos',text='')

    def test_existing_txt_never_starts_transcription(self):
        with tempfile.TemporaryDirectory() as tmp:
            text=Path(tmp)/'scene.txt';text.write_text('Texto meu',encoding='utf-8')
            with patch.object(translation,'translation_python',side_effect=AssertionError('must not start')):
                value=translation.generate_text('audio.wav',text,tmp,'scene',{},lambda text:None)
            self.assertEqual(value,('Texto meu','Portuguese'))

    def test_generated_files_force_and_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);text=root/'TXT TEXTO PORTUGUES'/'scene.txt';text.parent.mkdir();audio=root/'scene.wav';audio.write_bytes(b'audio')
            def launch(args,**kwargs):
                kwargs['stdout'].write(b'DUBLASKIZON_PHASE {"stage":"transcribe","fraction":0.5}\nDUBLASKIZON_PHASE {"stage":"translate","fraction":1}\n')
                kwargs['stdout'].flush()
                Path(args[-1]).write_text(json.dumps({'translation':'Olá','transcript':'Hello','source_language':'en','target':'pt'}),encoding='utf-8')
                return SimpleNamespace(returncode=0,poll=lambda:0)
            with patch.object(translation,'translation_python',return_value=Path(sys.executable)),patch.object(translation.subprocess,'Popen',side_effect=launch),patch.object(batch_tab,'find_ffmpeg_directory',return_value=None):
                phases=[]
                self.assertEqual(translation.generate_text(audio,text,root,'scene',{},lambda text:None,on_progress=lambda *args:phases.append(args))[0],'Olá')
                self.assertEqual(phases,[('transcribe',.5),('translate',1)])
                self.assertEqual(text.read_text(encoding='utf-8').strip(),'Olá')
                text.write_text('Minha tradução',encoding='utf-8')
                results=[]
                translation.generate_text(audio,text,root,'scene',{},lambda text:None,force=True,on_result=lambda *args:results.append(args))
                self.assertEqual(text.read_text(encoding='utf-8'),'Minha tradução')
                self.assertEqual(results[0][1].read_text(encoding='utf-8').strip(),'Olá')
                text.write_text('',encoding='utf-8')
                translation.generate_text(audio,text,root,'scene',{},lambda text:None)
                self.assertEqual(text.read_text(encoding='utf-8').strip(),'Olá')
                with self.assertRaisesRegex(RuntimeError,'cancelada'):
                    translation.generate_text(audio,text,root,'scene',{},lambda text:None,cancelled=lambda:True,force=True)
                with self.assertRaises(ValueError):
                    translation.generate_text(audio,text,root,'../scene',{},lambda text:None,force=True)

    def test_worker_source_is_valid(self):
        ast.parse(translation.WORKER)
        ast.parse(translation.PREPARE_WORKER)

    def test_redub_transcribes_original_and_keeps_chosen_voice(self):
        import review_tab
        import queue
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp);original=project/'original.wav';voice=project/'voice.wav'
            original.write_bytes(b'original');voice.write_bytes(b'voice')
            target=project/'dublado'/'scene.wav'
            app=review_tab.ReviewApp.__new__(review_tab.ReviewApp)
            app.root=SimpleNamespace(after=lambda *args:None)
            app.config={'model':'model','language':'Portuguese','instruct':''}
            app.regen_translation_settings=translation.settings({'language':'Inglês'})
            app.regen_stage_events=queue.Queue();app.audio_by_stem={'scene':original}
            def translated(audio,*args,**kwargs):
                self.assertEqual(audio,original);self.assertTrue(kwargs['force'])
                return 'Translated dialogue','English'
            def synth(command,*args,**kwargs):
                self.assertEqual(command[command.index('--ref_audio')+1],str(voice))
                self.assertEqual(command[command.index('--text')+1],'Translated dialogue')
                self.assertEqual(command[command.index('--language')+1],'English')
                Path(command[command.index('--output')+1]).write_bytes(b'finished')
                return SimpleNamespace(returncode=0,stdout='ok')
            with patch.object(review_tab,'ROOT',project),patch.object(review_tab,'TEXT_DIR',project/'txt'),patch.object(review_tab,'REVISIONS_DIR',project/'revisoes'),patch.object(review_tab,'CUSTOM_OUTPUT_DIR',project/'custom'),patch.object(review_tab,'find_omnivoice_command',return_value=['omnivoice']),patch.object(translation,'generate_text',side_effect=translated),patch.object(review_tab,'run_observed',side_effect=synth):
                app._run_generation('scene','old text',target,target,voice)
            self.assertEqual(target.read_bytes(),b'finished')


if __name__=='__main__':unittest.main()
