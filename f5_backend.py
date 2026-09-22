"""Isolated F5-TTS Russian adapter; never installs into the OmniVoice environment."""
from pathlib import Path
import json
import os
import time

MODEL = 'hotstone228/F5-TTS-Russian'
LABEL = 'F5-TTS Russian — russo / inglês (uso não comercial)'
VOCODER = 'charactr/vocos-mel-24khz'
ASR = 'openai/whisper-large-v3-turbo'
VERSION = '1.1.22'
FILES = {MODEL: ['model_last.safetensors', 'vocab.txt', 'README.md', 'setting.json'],
         VOCODER: ['config.yaml', 'pytorch_model.bin'],
         ASR: ['*.json', '*.safetensors', '*.txt', '*.model']}


def runtime():
    from dependency_setup import runtime_root
    root = runtime_root().resolve()
    try:
        data = json.loads((root / 'f5-active.json').read_text(encoding='utf-8'))
        python = (root / data['python']).resolve()
        if python.is_relative_to(root) and python.is_file():
            return python, data
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None, {}


def validate(language, mode='clone'):
    if str(language).casefold() not in ('ru', 'russian', 'русский', 'russo', 'en', 'english', 'inglês'):
        raise ValueError('F5-TTS Russian: selecione Russo ou Inglês em Idioma da voz / saída da tradução.')
    if mode != 'clone':
        raise ValueError('F5-TTS Russian requer Voice Cloning e um áudio de referência. Voice Design não é suportado.')


def inference_command():
    python, data = runtime()
    if not python:
        raise RuntimeError('Selecione hotstone228/F5-TTS-Russian em REQUISITOS e use 1. INSTALAR / REPARAR, 2. BAIXAR MODELOS e 3. TESTAR MODELO.')
    from batch_tab import find_ffmpeg_directory
    ffmpeg = find_ffmpeg_directory()
    # Force UTF-8 so f5_tts print of Russian gen_text never hits cp1252.
    prelude = "import os,sys;os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';"
    prelude += "os.environ['PYTHONIOENCODING']='utf-8';os.environ['HF_ENDPOINT']='https://huggingface.co';"
    prelude += "hasattr(sys.stdout,'reconfigure') and sys.stdout.reconfigure(encoding='utf-8',errors='replace');"
    prelude += "hasattr(sys.stderr,'reconfigure') and sys.stderr.reconfigure(encoding='utf-8',errors='replace');"
    if ffmpeg:
        prelude += f"os.environ['PATH']={str(ffmpeg)!r}+os.pathsep+os.environ.get('PATH','');"
    return [str(python), '-u', '-c', prelude + '\n' + WORKER,
            '--device', 'cuda' if data.get('variant') == 'cu128' else 'cpu']


def install(job, variant):
    from dependency_setup import runtime_root
    if variant not in ('cpu', 'cu128'):
        raise ValueError('Processamento inválido.')
    if os.name != 'nt':
        raise RuntimeError('A preparação automática do F5-TTS requer Windows x64.')
    python, data = runtime()
    if python and data.get('variant') == variant and data.get('version') == VERSION:
        try:
            job.run([python, '-c', 'from f5_tts.api import F5TTS;import torch,torchaudio;print("F5-TTS já instalado")'])
            job.write('[OK] Ambiente F5-TTS já preparado; sem nova instalação.')
            return
        except (OSError, RuntimeError):
            pass
    root = runtime_root()
    base = job.ensure_base_python()
    envdir = root / ('f5-env-' + str(time.time_ns()))
    job.total_steps = 9
    job.run([base, '-m', 'venv', envdir])
    python = envdir / 'Scripts' / 'python.exe'
    pip = [python, '-m', 'pip', 'install', '--retries', '3', '--timeout', '60']
    job.run([*pip, '--index-url', 'https://pypi.org/simple', '--upgrade', 'pip'])
    pip += ['--progress-bar', 'raw']
    job.run([*pip, '--index-url', f'https://download.pytorch.org/whl/{variant}',
             'torch==2.8.0', 'torchaudio==2.8.0'], timeout=7200)
    constraints = envdir / 'constraints.txt'
    constraints.write_text('torch==2.8.0\ntorchaudio==2.8.0\ntorchcodec==0.7.0\ntransformers==4.57.6\nhuggingface-hub==0.36.2\ngradio==6.17.3\n', encoding='utf-8')
    job.run([*pip, '--index-url', 'https://pypi.org/simple', '-c', constraints,
             'f5-tts==' + VERSION, 'audioop-lts'], timeout=7200)
    job.run([python, '-m', 'pip', 'check'])
    job.run([python, '-c', 'from f5_tts.api import F5TTS;import torch,torchaudio;'
             + ("assert torch.cuda.is_available();print(torch.zeros(1,device='cuda')+1)" if variant == 'cu128' else 'print(torch.zeros(1)+1)')], timeout=180)
    job.checkpoint()
    pending = root / ('f5-active-' + str(time.time_ns()) + '.pending.json')
    pending.write_text(json.dumps({'python': python.relative_to(root).as_posix(),
                                   'variant': variant, 'version': VERSION}), encoding='utf-8')
    pending.replace(root / 'f5-active.json')
    job.write('[OK] F5-TTS preparado em ambiente separado. OmniVoice preservado. Baixe os modelos e teste o carregamento.')


def download(job, sizes_only=False):
    python, _ = runtime()
    if not python:
        raise RuntimeError('Instale primeiro o ambiente F5-TTS pelo botão 1, com esse modelo selecionado.')
    job.total_steps = 1
    job.run([python, '-u', '-c', DOWNLOAD_WORKER, json.dumps(FILES), '1' if sizes_only else '0'],
            timeout=900 if sizes_only else 14400)
    job.write('[OK] Consulta concluída.' if sizes_only else '[OK] F5-TTS, Vocos e Whisper disponíveis. Use TESTAR MODELO.')


def test(job):
    job.total_steps = 1
    job.run([*inference_command(), '--test'], timeout=900)


DOWNLOAD_WORKER = r'''
import sys,json,time,fnmatch
from pathlib import Path
from huggingface_hub import HfApi,hf_hub_download,try_to_load_from_cache
import importlib
progress_module=importlib.import_module('huggingface_hub.utils.tqdm')
tqdm=progress_module.tqdm
plans=[]
for repo,patterns in json.loads(sys.argv[1]).items():
    print('Consultando tamanhos e cache: '+repo,flush=True)
    info=HfApi(endpoint='https://huggingface.co').model_info(repo,files_metadata=True)
    files=[]
    for f in info.siblings:
        if not any(fnmatch.fnmatch(f.rfilename,p) for p in patterns):continue
        cached=try_to_load_from_cache(repo,f.rfilename,revision=info.sha)
        exists=isinstance(cached,str) and Path(cached).is_file()
        files.append((f.rfilename,f.size or 0,exists))
    if not files:raise RuntimeError('Nenhum arquivo encontrado: '+repo)
    print('DUBLASKIZON_TRANSFER '+json.dumps(dict(kind='size',name=repo,total=sum(f[1] for f in files),missing=sum(f[1] for f in files if not f[2]))),flush=True)
    plans.append((repo,info.sha,files))
print('DUBLASKIZON_TRANSFER '+json.dumps(dict(kind='size',name='TOTAL DOS MODELOS',total=sum(f[1] for _,_,fs in plans for f in fs),missing=sum(f[1] for _,_,fs in plans for f in fs if not f[2]))),flush=True)
if sys.argv[2]!='1':
    class Bar(tqdm):
        def __init__(self,*args,**kwargs):
            kwargs['disable']=False
            super().__init__(*args,**kwargs)
        def display(self,*args,**kwargs):
            now=time.monotonic()
            if now-getattr(self,'last_report',0)<.2:return
            self.last_report=now
            print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name=getattr(self,'desc','Arquivo'),current=int(getattr(self,'n',0)),total=int(getattr(self,'total',0) or 0))),flush=True)
    # Hub 0.36 uses this factory for HTTP and Xet byte progress. The public
    # hf_hub_download API has no tqdm_class parameter in this pinned version.
    # This hook lives only in the disposable download subprocess.
    progress_module.tqdm=Bar
    for repo,revision,files in plans:
        for name,size,cached in files:
            if cached:print('DUBLASKIZON_TRANSFER '+json.dumps(dict(kind='cache',name=repo+'/'+name)),flush=True)
            # Resolve main through the official cache API; download only the selected files.
            hf_hub_download(repo,name,endpoint='https://huggingface.co')
            print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name=name,current=size,total=size)),flush=True)
'''


WORKER = r'''
import argparse,gc,sys,os
# Windows console (cp1252) cannot print Cyrillic from f5_tts.utils_infer.
# Force UTF-8 on stdout/stderr before any library print of gen_text.
os.environ.setdefault("PYTHONIOENCODING","utf-8")
if hasattr(sys.stdout,"reconfigure"):
    try:sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    except Exception:pass
if hasattr(sys.stderr,"reconfigure"):
    try:sys.stderr.reconfigure(encoding="utf-8",errors="replace")
    except Exception:pass
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--model',default='hotstone228/F5-TTS-Russian')
p.add_argument('--text',default='');p.add_argument('--language',default='Russian')
p.add_argument('--instruct',default='');p.add_argument('--ref_audio');p.add_argument('--output')
p.add_argument('--device',choices=('cpu','cuda'),default='cpu');p.add_argument('--test',action='store_true')
a=p.parse_args()
if a.model!='hotstone228/F5-TTS-Russian':p.error('Modelo F5-TTS desconhecido')
if a.language.casefold() not in ('ru','russian','en','english'):p.error('F5-TTS Russian suporta saída russa ou inglesa')
if not a.test and (not a.ref_audio or not a.output or not a.text.strip()):p.error('Informe referência, texto e saída')
from huggingface_hub import hf_hub_download,snapshot_download
print('Loading F5-TTS Russian / Vocos',flush=True)
try:
    checkpoint=hf_hub_download(a.model,'model_last.safetensors',local_files_only=True)
    vocab=hf_hub_download(a.model,'vocab.txt',local_files_only=True)
    vocoder=snapshot_download('charactr/vocos-mel-24khz',local_files_only=True)
    for name in ('config.yaml','pytorch_model.bin'):
        if not (Path(vocoder)/name).is_file():raise FileNotFoundError(name)
    asr=snapshot_download('openai/whisper-large-v3-turbo',local_files_only=True)
    if not list(Path(asr).glob('*.safetensors')):raise FileNotFoundError('Whisper')
except Exception as exc:
    raise RuntimeError('Modelos F5-TTS incompletos. Selecione F5-TTS Russian em REQUISITOS e use BAIXAR MODELOS.') from exc
import torch
from f5_tts.api import F5TTS
from f5_tts.infer import utils_infer as utils
# Transformers 4.57 probes TorchCodec even for a plain WAV filename. F5 only
# needs the existing FFmpeg/NumPy decoder, not TorchCodec or shared FFmpeg DLLs.
# Select that path in this subprocess, including already installed v64 runtimes.
from transformers.pipelines import automatic_speech_recognition as asr_module
asr_module.is_torchcodec_available=lambda:False
if a.device=='cuda' and not torch.cuda.is_available():raise RuntimeError('NVIDIA indisponível; prepare o ambiente F5-TTS em CPU nos REQUISITOS.')
if not a.test:
    if not Path(a.ref_audio).is_file():raise FileNotFoundError(a.ref_audio)
    print('Transcribing reference audio (CPU; antes de carregar a síntese)',flush=True)
    # Transcribe the exact cropped voice sample, never pass the translated target as reference text.
    utils.initialize_asr_pipeline(device='cpu',dtype=torch.float32)
    ref_file,ref_text=utils.preprocess_ref_audio_text(a.ref_audio,'')
    utils.asr_pipe=None
    gc.collect()
    if not ref_text.strip(' .'):raise RuntimeError('A referência não contém fala reconhecível.')
engine=F5TTS(model='F5TTS_Base',ckpt_file=checkpoint,vocab_file=vocab,
             vocoder_local_path=vocoder,device=a.device)
print('Model loaded: F5-TTS Russian / '+a.device,flush=True)
if a.test:
    print('MODELO CARREGADO; geração de fala ainda não testada',flush=True)
else:
    if a.instruct:print('F5-TTS usa a voz de referência; descrições de Voice Design não se aplicam.',flush=True)
    print('Generating audio',flush=True)
    # The upstream worker otherwise synthesizes every text chunk concurrently on one GPU.
    from concurrent.futures import ThreadPoolExecutor
    from functools import partial
    utils.ThreadPoolExecutor=partial(ThreadPoolExecutor,max_workers=1)
    wav,sr,_=utils.infer_process(ref_file,ref_text,a.text,engine.ema_model,engine.vocoder,engine.mel_spec_type,device=a.device)
    import numpy as np,soundfile as sf
    if wav is None or not len(wav) or not np.isfinite(wav).all():raise RuntimeError('F5-TTS não produziu áudio válido.')
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    sf.write(a.output,wav,sr,subtype='PCM_16')
    print('Audio saved: '+a.output,flush=True)
'''
