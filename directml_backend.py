"""F5-TTS PT-BR isolado para GPUs DirectX 12 sem suporte ROCm."""
from pathlib import Path
import json
import os
import time

MODEL = 'firstpixel/F5-TTS-pt-br'
LABEL = 'F5-TTS PT-BR DirectML — RX 500 / DirectX 12 (experimental)'
VOCODER = 'charactr/vocos-mel-24khz'
ASR = 'openai/whisper-large-v3-turbo'
VERSION = 'directml-0.2.5-f5-1.1.22-v2'
DIRECTML_VERSION = '0.2.5.dev240914'
F5_VERSION = '1.1.22'
FILES = {MODEL: ['pt-br/model_last.safetensors', 'README.md'],
         VOCODER: ['config.yaml', 'pytorch_model.bin'],
         ASR: ['*.json', '*.safetensors', '*.txt', '*.model']}


def runtime():
    from dependency_setup import runtime_root
    root=runtime_root().resolve()
    try:
        data=json.loads((root/'directml-active.json').read_text(encoding='utf-8'))
        python=(root/data['python']).resolve()
        if python.is_relative_to(root) and python.is_file():return python,data
    except (OSError,ValueError,KeyError,TypeError):pass
    return None,{}


def validate(language,mode='clone'):
    if str(language).casefold() not in ('pt','pt-br','portuguese','português','português (brasil)','portuguese (brazil)'):
        raise ValueError('F5-TTS PT-BR DirectML aceita português. Selecione Português (Brasil).')
    if mode!='clone':raise ValueError('F5-TTS PT-BR DirectML requer Voice Cloning e um áudio de referência.')


def inference_command():
    python,data=runtime()
    if not python:raise RuntimeError('Selecione F5-TTS PT-BR DirectML em REQUISITOS e execute INSTALAR, BAIXAR MODELOS e TESTAR MODELO.')
    from batch_tab import find_ffmpeg_directory
    ffmpeg=find_ffmpeg_directory()
    prelude="import os;os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';"
    if ffmpeg:prelude+=f"os.environ['PATH']={str(ffmpeg)!r}+os.pathsep+os.environ.get('PATH','');"
    return [str(python),'-u','-c',prelude+'\n'+WORKER,'--device','dml']


def install(job,variant='directml'):
    from dependency_setup import runtime_root
    if variant!='directml':raise ValueError('O perfil DirectML requer o modo AMD antiga / DirectX 12.')
    if os.name!='nt':raise RuntimeError('DirectML para RX 500 requer Windows 10 1709 ou Windows 11 x64.')
    python,data=runtime()
    if python and data.get('version')==VERSION:
        try:
            job.run([python,'-c','import torch,torch_directml;d=torch_directml.device();print(torch.tensor([1.0],device=d)+1,torch_directml.device_name(0))'],timeout=180)
            job.write('[OK] Ambiente DirectML já preparado; sem reinstalação.');return
        except (OSError,RuntimeError):pass
    root=runtime_root();base=job.ensure_amd_python();envdir=root/('directml-env-'+str(time.time_ns()))
    job.total_steps=9;job.run([base,'-m','venv',envdir]);python=envdir/'Scripts'/'python.exe'
    pip=[python,'-m','pip','install','--retries','3','--timeout','60','--progress-bar','raw','--index-url','https://pypi.org/simple']
    job.run([python,'-m','pip','install','--index-url','https://pypi.org/simple','--upgrade','pip'])
    job.write('Instalando o motor oficial Microsoft DirectML em ambiente separado...')
    job.run([*pip,'torch-directml=='+DIRECTML_VERSION,'torchaudio==2.4.1'],timeout=7200)
    constraints=envdir/'constraints.txt'
    # torch-directml 0.2.5 is tied to torch 2.4.1. TorchCodec 0.0.3 is the
    # corresponding official generation; newer TorchCodec builds fail while
    # loading their DLLs with this older Torch.
    constraints.write_text('torch==2.4.1\ntorchaudio==2.4.1\ntorchcodec==0.0.3\n',encoding='utf-8')
    job.run([*pip,'-c',constraints,'f5-tts=='+F5_VERSION],timeout=7200)
    job.run([python,'-m','pip','check'])
    job.run([python,'-c','import torch,torch_directml;d=torch_directml.device();x=torch.tensor([1.0],device=d)+1;assert x.item()==2;print("DIRECTML:",torch_directml.device_name(0),x)'],timeout=180)
    pending=root/('directml-active-'+str(time.time_ns())+'.pending.json')
    pending.write_text(json.dumps({'python':python.relative_to(root).as_posix(),'variant':'directml','version':VERSION}),encoding='utf-8')
    pending.replace(root/'directml-active.json')
    job.write('[OK] DirectML validado. Baixe o modelo PT-BR e use TESTAR MODELO.')


def download(job,sizes_only=False):
    python,_=runtime()
    if not python:raise RuntimeError('Instale primeiro o ambiente DirectML pelo botão 1.')
    from f5_backend import DOWNLOAD_WORKER
    job.total_steps=1
    job.run([python,'-u','-c',DOWNLOAD_WORKER,json.dumps(FILES),'1' if sizes_only else '0'],timeout=900 if sizes_only else 14400)
    job.write('[OK] Consulta concluída.' if sizes_only else '[OK] Modelo português, Vocos e Whisper disponíveis. Use TESTAR MODELO.')


def test(job,project_root=None):
    """Valida o tensor, carrega o modelo e, havendo referência, gera um WAV real."""
    job.total_steps=1
    reference=None
    root=Path(project_root) if project_root else None
    if root and root.is_dir():
        source=root/'WAV ORIGINAIS'
        if source.is_dir():
            reference=next((p for p in source.rglob('*') if p.is_file() and p.suffix.casefold() in ('.wav','.mp3','.flac','.ogg','.m4a')),None)
    if reference:
        from dependency_setup import runtime_root
        output=runtime_root()/'directml-test-ptbr.wav'
        output.unlink(missing_ok=True)
        job.write('Teste real: gerando uma frase curta em português com uma referência do projeto.')
        job.run([*inference_command(),'--model',MODEL,'--text','Teste de dublagem em português.',
                 '--language','Portuguese','--ref_audio',reference,'--output',output],timeout=1800)
        if not output.is_file() or output.stat().st_size<1000:
            raise RuntimeError('O motor carregou, mas não produziu um WAV válido. O ambiente não será considerado pronto.')
        job.write('[OK] DirectML/CPU fallback validado com geração real em português: '+str(output))
    else:
        job.run([*inference_command(),'--test'],timeout=1200)
        job.write('AVISO: nenhum áudio de referência foi encontrado; faça a primeira geração com uma cena curta para validar a síntese completa.')


WORKER=r'''
import argparse,gc
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--model',default='firstpixel/F5-TTS-pt-br');p.add_argument('--text',default='')
p.add_argument('--language',default='Portuguese');p.add_argument('--instruct',default='');p.add_argument('--ref_audio');p.add_argument('--output')
p.add_argument('--device',choices=('dml','cpu'),default='dml');p.add_argument('--test',action='store_true');a=p.parse_args()
if a.model!='firstpixel/F5-TTS-pt-br':p.error('Modelo DirectML desconhecido')
if a.language.casefold() not in ('pt','pt-br','portuguese','português','português (brasil)','portuguese (brazil)'):p.error('Selecione Português (Brasil)')
if not a.test and (not a.ref_audio or not a.output or not a.text.strip()):p.error('Informe referência, texto e saída')
from huggingface_hub import hf_hub_download,snapshot_download
checkpoint=hf_hub_download(a.model,'pt-br/model_last.safetensors',local_files_only=True)
vocoder=snapshot_download('charactr/vocos-mel-24khz',local_files_only=True)
asr=snapshot_download('openai/whisper-large-v3-turbo',local_files_only=True)
for name in ('config.yaml','pytorch_model.bin'):
 if not (Path(vocoder)/name).is_file():raise RuntimeError('Vocos incompleto; use BAIXAR MODELOS.')
import torch
# F5 only needs the ordinary audio path here. Disable Transformers' optional
# TorchCodec probe before importing F5 so missing shared FFmpeg DLLs cannot
# prevent synthesis; pydub/soundfile use the FFmpeg supplied by Dublaskizon.
from transformers.utils import import_utils
import_utils._torchcodec_available=False
from transformers.pipelines import automatic_speech_recognition as asr_module
asr_module.is_torchcodec_available=lambda:False
from f5_tts.api import F5TTS
from f5_tts.infer import utils_infer as utils
def choose_device():
 if a.device=='cpu':return 'cpu','CPU solicitada'
 import torch_directml
 d=torch_directml.device();x=torch.tensor([1.0],device=d)+1
 if x.item()!=2:raise RuntimeError('Teste matemático DirectML inválido.')
 return d,'DirectML '+torch_directml.device_name(0)
device,label=choose_device();print('Motor selecionado: '+label,flush=True)
def load(where):return F5TTS(model='F5TTS_Base',ckpt_file=checkpoint,vocoder_local_path=vocoder,device=where)
try:engine=load(device)
except Exception as exc:
 if a.device!='dml':raise
 print('AVISO: DirectML não carregou o modelo ('+str(exc)+'). Tentando CPU para preservar a cena.',flush=True);gc.collect();device='cpu';engine=load(device);label='CPU fallback'
print('Model loaded: F5-TTS PT-BR / '+label,flush=True)
if a.test:
 print('DIRECTML TESTADO: tensor e carregamento do modelo concluídos.' if label.startswith('DirectML') else 'MODELO CARREGADO SOMENTE EM CPU; DirectML reprovado.',flush=True)
else:
 if not Path(a.ref_audio).is_file():raise FileNotFoundError(a.ref_audio)
 print('Transcribing reference audio on CPU',flush=True);utils.initialize_asr_pipeline(device='cpu',dtype=torch.float32)
 ref_file,ref_text=utils.preprocess_ref_audio_text(a.ref_audio,'');utils.asr_pipe=None;gc.collect()
 if not ref_text.strip(' .'):raise RuntimeError('A referência não contém fala reconhecível.')
 def generate(active_engine,active_device):
  from concurrent.futures import ThreadPoolExecutor
  from functools import partial
  utils.ThreadPoolExecutor=partial(ThreadPoolExecutor,max_workers=1)
  return utils.infer_process(ref_file,ref_text,a.text.lower(),active_engine.ema_model,active_engine.vocoder,active_engine.mel_spec_type,device=active_device)
 try:wav,sr,_=generate(engine,device)
 except Exception as exc:
  if label=='CPU fallback':raise
  print('AVISO: DirectML falhou durante a síntese ('+str(exc)+'). Repetindo esta cena na CPU.',flush=True)
  del engine;gc.collect();device='cpu';engine=load(device);wav,sr,_=generate(engine,device);label='CPU fallback'
 import numpy as np,soundfile as sf
 if wav is None or not len(wav) or not np.isfinite(wav).all():raise RuntimeError('F5-TTS não produziu áudio válido.')
 Path(a.output).parent.mkdir(parents=True,exist_ok=True);sf.write(a.output,wav,sr,subtype='PCM_16')
 print('Audio saved: '+a.output+' / '+label,flush=True)
'''
