"""Isolated, bounded Audacity/OpenVINO processing. Never opens a user's project."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import wave

KINDS = ('instrumental', 'vocals', 'suppression')
LABELS = {'instrumental':'ORIGINAL- sample-instrumental', 'vocals':'ORIGINAL- sample-vocals',
          'suppression':'ORIGINAL- sample-vocals Suppression'}
_LOCK = threading.Lock()

def scene_directory(root, original):
    original=Path(original).resolve()
    stat=original.stat()
    key=hashlib.sha256(f'{original}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()[:24]
    return Path(root).resolve()/'revisoes'/'audacity_openvino'/key

def outputs(root, original):
    try:
        folder=scene_directory(root,original)
        return {kind:folder/(kind+'.wav') for kind in KINDS if (folder/(kind+'.wav')).is_file()}
    except (OSError, TypeError):
        return {}

def validate_wave(path):
    with wave.open(str(path),'rb') as audio:
        if audio.getnframes()<=0 or audio.getframerate()<=0:
            raise ValueError('O Audacity exportou um áudio vazio.')
        return audio.getnframes()/audio.getframerate()

def prepare_bridge(report):
    """Copy installed binaries once, keeping application settings isolated."""
    if os.name!='nt':raise RuntimeError('Esta integração requer Audacity/OpenVINO no Windows.')
    from audacity_setup import installations
    candidates=installations()+[Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Audacity',
                Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Audacity']
    from audacity_setup import missing
    install=next((p for p in candidates if not missing(p,True)),None)
    if install is None:raise RuntimeError('Instale o Audacity com os plugins OpenVINO Music Separation e Noise Suppression.')
    signature=hashlib.sha256((str(install.resolve())+'|'+str((install/'Audacity.exe').stat().st_mtime_ns)+'|'+str((install/'modules/mod-openvino.dll').stat().st_mtime_ns)).encode()).hexdigest()[:24]
    base=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'DUBLASKIZON'/'audacity_openvino'/signature
    ready=base/'ready.json'
    if ready.is_file():return base
    report(5,'Preparando cópia isolada do Audacity (somente no primeiro uso)…')
    base.mkdir(parents=True,exist_ok=True)
    for file in install.iterdir():
        if file.is_file() and (file.suffix.lower()=='.dll' or file.name in
            {'Audacity.exe','crashpad_handler.exe','crashreporter.exe','EffectsMenuDefaults.xml'}):
            shutil.copy2(file,base/file.name)
    for name in ('modules','Nyquist'):
        shutil.copytree(install/name,base/name,dirs_exist_ok=True)
    models=base/'openvino-models';models.mkdir(exist_ok=True)
    for name in ('htdemucs_v4.xml','htdemucs_v4.bin','noise-suppression-denseunet-ll-0001.xml',
                 'noise-suppression-denseunet-ll-0001.bin','deepfilternet2','deepfilternet3'):
        src=install/'openvino-models'/name
        if src.is_dir():shutil.copytree(src,models/name,dirs_exist_ok=True)
        elif src.is_file():shutil.copy2(src,models/name)
    if not (models/'htdemucs_v4.xml').is_file():raise RuntimeError('Modelo Music Separation ausente no Audacity instalado.')
    prefs=base/'Portable Settings';prefs.mkdir(exist_ok=True)
    temp=base/'sessions';temp.mkdir(exist_ok=True)
    cfg=('PrefsVersion=1.1.1r1\nImporters=AUP,PCM,OGG,FLAC,MP3,LOF,WavPack,portsmf,FFmpeg,Opus\n'
         'Exporters=PCM,MP3,OGG,Opus,FLAC,WavPack,FFmpeg,MP2,CommandLine\n'
         '[Version]\nMajor=3\nMinor=7\nMicro=9\n[Module]\n')
    # Module timestamps avoid Audacity resetting a copied module to "new".
    modules=sorted((base/'modules').glob('*.dll'))
    cfg+=''.join(f'{p.stem}=1\n' for p in modules)
    cfg+='[ModulePath]\n'+''.join(f'{p.stem}={str(p).replace(chr(92),chr(92)*2)}\n' for p in modules)
    cfg+='[ModuleDateTime]\n'+''.join(f'{p.stem}={time.strftime("%Y-%m-%dT%H:%M:%S",time.localtime(p.stat().st_mtime))}\n' for p in modules)
    cfg+=f'[Directories]\nTempDir={temp.as_posix()}\n[GUI]\nShowWelcome=0\nShowSplashScreen=0\n'
    # Retain existing first-run choices without editing the user's configuration.
    usercfg=Path(os.environ.get('APPDATA',''))/'audacity/audacity.cfg'
    if usercfg.is_file():
        import re
        old=usercfg.read_text(encoding='utf-8-sig')
        old=re.sub(r'(?m)^mod-script-pipe=\d+$','mod-script-pipe=1',old)
        old=old.replace(str(install).replace('\\','\\\\'),str(base).replace('\\','\\\\'))
        old=re.sub(r'(?m)^TempDir=.*$',f'TempDir={temp.as_posix()}',old)
        cfg=old
    (prefs/'audacity.cfg').write_text(cfg,encoding='utf-8')
    ready.write_text(json.dumps({'installation':str(install)}),encoding='utf-8')
    return base

def audacity_running():
    result=subprocess.run(['tasklist','/fi','IMAGENAME eq Audacity.exe','/fo','csv','/nh'],
        capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=10)
    return any(row and row[0].lower()=='audacity.exe' for row in csv.reader(io.StringIO(result.stdout)))

def configure_session(base,session):
    """Known minimal scripting profile, with existing first-run choices retained."""
    import re
    cfgpath=base/'Portable Settings/audacity.cfg'
    previous=cfgpath.read_text(encoding='utf-8-sig')
    cfg='PrefsVersion=1.1.1r1\n'
    for key in ('SendAnonymousUsageInfo','InstanceId'):
        match=re.search(r'(?m)^'+key+r'=(.*)$',previous)
        if match:cfg+=key+'='+match.group(1)+'\n'
    cfg+='Importers=AUP,PCM,OGG,FLAC,MP3,LOF,WavPack,portsmf,FFmpeg,Opus\n'
    cfg+='Exporters=PCM,MP3,OGG,Opus,FLAC,WavPack,FFmpeg,MP2,CommandLine\n'
    cfg+='[Update]\nUpdateNoticeShown=1\n[Version]\nMajor=3\nMinor=7\nMicro=9\n[Module]\n'
    modules=sorted((base/'modules').glob('*.dll'))
    cfg+=''.join(f'{p.stem}=1\n' for p in modules)
    cfg+='[ModulePath]\n'+''.join(f'{p.stem}={str(p).replace(chr(92),chr(92)*2)}\n' for p in modules)
    cfg+='[ModuleDateTime]\n'+''.join(f'{p.stem}={time.strftime("%Y-%m-%dT%H:%M:%S",time.localtime(p.stat().st_mtime))}\n' for p in modules)
    cfg+=f'[Directories]\nTempDir={session.resolve().as_posix()}\n[GUI]\nShowWelcome=0\nShowSplashScreen=0\n'
    usercfg=Path(os.environ.get('APPDATA',''))/'audacity/audacity.cfg'
    if usercfg.is_file():
        cfg=usercfg.read_text(encoding='utf-8-sig')
        install=Path(json.loads((base/'ready.json').read_text(encoding='utf-8'))['installation'])
        cfg=cfg.replace(str(install).replace('\\','\\\\'),str(base).replace('\\','\\\\'))
        cfg=re.sub(r'(?m)^mod-script-pipe=\d+$','mod-script-pipe=1',cfg)
        cfg=re.sub(r'(?m)^TempDir=.*$',f'TempDir={session.resolve().as_posix()}',cfg)
        cfg=re.sub(r'(?m)^ShowSplashScreen=.*$','ShowSplashScreen=0',cfg)
        cfg=re.sub(r'(?ms)^\[(?:ActiveProjects|RecentFiles)\]\n.*?(?=^\[|\Z)','',cfg)
    cfgpath.write_text(cfg,encoding='utf-8')

class Pipe:
    def __init__(self, process, cancel, timeout=900):
        self.process,self.cancel,self.deadline=process,cancel,time.monotonic()+timeout
        self.writer=open(r'\\.\pipe\ToSrvPipe','w',encoding='utf-8')
        self.reader=open(r'\\.\pipe\FromSrvPipe',encoding='utf-8')
        self.closed=threading.Event();self.command_deadline=self.deadline
        def watch():
            while not self.closed.wait(.2):
                if self.cancel.is_set() or time.monotonic()>min(self.deadline,self.command_deadline):
                    if self.process.poll() is None:self.process.terminate()
                    return
        threading.Thread(target=watch,daemon=True).start()
    def check(self):
        if self.cancel.is_set():raise RuntimeError('Tratamento OpenVINO cancelado. Original preservado.')
        if time.monotonic()>self.deadline:raise TimeoutError('O tratamento excedeu o limite de 15 minutos. Original preservado.')
    def command(self,text,timeout=None):
        self.check();self.writer.write(text+'\r\n\0');self.writer.flush();answer=''
        deadline=min(self.deadline,time.monotonic()+(timeout if timeout is not None else 900 if text.startswith('Openvino') else 60))
        self.command_deadline=deadline
        while True:
            self.check()
            if time.monotonic()>deadline:raise TimeoutError('O Audacity não respondeu ao comando '+text.split(':')[0]+'. Original preservado.')
            line=self.reader.readline()
            if not line:raise RuntimeError('A conexão com o Audacity foi encerrada. Original preservado.')
            answer+=line
            if line=='\n' and len(answer)>1:break
        # Audacity localizes the completion sentence, but retains the OK token.
        import re
        if not re.search(r':\s*OK\s*$',answer):raise RuntimeError(text.split(':')[0]+': '+answer[-1200:])
        return answer
    def close(self):
        self.closed.set()
        try:self.writer.close()
        except OSError:pass
        try:self.reader.close()
        except OSError:pass

def wait_engine(process,cancel):
    import ctypes
    idle=ctypes.windll.user32.WaitForInputIdle
    idle.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    idle(int(process._handle),30000)
    if cancel.wait(20):raise RuntimeError('Tratamento cancelado.')

def process_original(root, original, suppression=False, cancel=None, report=lambda percent,text:None):
    """Run in a worker thread. Publish results only after successful export."""
    cancel=cancel or threading.Event()
    if not _LOCK.acquire(blocking=False):raise RuntimeError('Outro tratamento OpenVINO está em andamento.')
    process=pipe=None
    try:
        original=Path(original).resolve()
        if not original.is_file():raise FileNotFoundError('Áudio original não encontrado.')
        if audacity_running():raise RuntimeError('Salve e feche o Audacity antes do tratamento. O projeto aberto não será usado pela automação.')
        base=prepare_bridge(report)
        folder=scene_directory(root,original);folder.mkdir(parents=True,exist_ok=True)
        import uuid
        job=folder/('processo_'+uuid.uuid4().hex[:12])
        job.mkdir()
        source=job/('original'+original.suffix.lower());shutil.copy2(original,source)
        # Fresh temporary session per job avoids crash recovery dialogs after cancellation.
        session=job/'session';session.mkdir()
        configure_session(base,session)
        report(12,'Iniciando Audacity isolado…')
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=1 if os.environ.get('DUBLASKIZON_AUDACITY_DIAGNOSTIC')=='1' else 0
        process=subprocess.Popen([str(base/'Audacity.exe')],cwd=base,startupinfo=startup)
        # Wait for the GUI command dispatcher, not merely for the pipe to exist.
        wait_engine(process,cancel)
        deadline=time.monotonic()+60
        while pipe is None:
            if cancel.is_set():raise RuntimeError('Tratamento cancelado.')
            if process.poll() is not None:raise RuntimeError('Não foi possível iniciar a cópia isolada do Audacity. Feche outras instâncias e tente novamente.')
            try:pipe=Pipe(process,cancel)
            except OSError:
                if time.monotonic()>deadline:raise TimeoutError('O módulo mod-script-pipe não respondeu em 60 segundos.')
                time.sleep(.2)
        report(18,'Importando cópia do áudio original…')
        pipe.command('New:')
        pipe.command(f'Import2: Filename="{source.resolve().as_posix()}"')
        pipe.command('SelectAll:')
        report(25,'AUDACITY Music Separation: separando voz e instrumental…')
        pipe.command('OpenvinoMusicSeparation:')
        answer=pipe.command('GetInfo: Type=Tracks Format=JSON')
        tracks=json.JSONDecoder().raw_decode(answer.lstrip())[0]
        indices={}
        for i,track in enumerate(tracks):
            name=track.get('name','').casefold()
            if name.endswith('-instrumental'):indices['instrumental']=i
            if name.endswith('-vocals'):indices['vocals']=i
        if set(indices)!= {'instrumental','vocals'}:raise RuntimeError('O Audacity não retornou as faixas de voz e instrumental esperadas.')
        duration=max(float(t.get('end',0)) for t in tracks)
        for kind in ('instrumental','vocals'):
            pipe.command(f'Select: Track={indices[kind]} Start=0 End={duration}')
            channels=2 if tracks[indices[kind]].get('channels',1)==2 else 1
            pipe.command(f'Export2: Filename="{(job/(kind+".wav")).as_posix()}" NumChannels={channels}')
            validate_wave(job/(kind+'.wav'))
        report(65,'Voz e instrumental separados.')
        if suppression:
            pipe.command(f'Select: Track={indices["vocals"]} Start=0 End={duration}')
            report(70,'AUDACITY Noise Suppression: tratando somente a voz separada…')
            pipe.command('OpenvinoNoiseSuppression:')
            pipe.command(f'Export2: Filename="{(job/"suppression.wav").as_posix()}" NumChannels=1')
            validate_wave(job/'suppression.wav')
        if cancel.is_set():raise RuntimeError('Tratamento cancelado; resultados anteriores preservados.')
        for kind in KINDS:
            path=job/(kind+'.wav')
            if path.is_file():os.replace(path,folder/path.name)
        (folder/'origem.json').write_text(json.dumps({'original':str(original),'created':time.strftime('%Y-%m-%d %H:%M:%S'),
            'effects':['OpenvinoMusicSeparation']+(['OpenvinoNoiseSuppression'] if suppression else []),'mode':'CPU/default; vocals only suppression'},ensure_ascii=False,indent=2),encoding='utf-8')
        report(100,'Tratamento concluído. Original preservado.')
        return outputs(root,original)
    finally:
        if pipe:pipe.close()
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill()
        _LOCK.release()

