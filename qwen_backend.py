"""Official Qwen3-TTS adapter. Heavy dependencies only run in an isolated process."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil

MODEL='Qwen/Qwen3-TTS-12Hz-1.7B-Base'
CUSTOM_MODEL='Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'
TOKENIZER='Qwen/Qwen3-TTS-Tokenizer-12Hz'
ASR='openai/whisper-small'
LABEL='Qwen3-TTS 1.7B — português / clonagem de voz'
VERSION='qwen-tts-0.1.1-torch271-v1'
FILES={repo:['*.json','*.safetensors','*.txt','*.model'] for repo in (MODEL,CUSTOM_MODEL,TOKENIZER,ASR)}
LANGUAGES={'pt':'Portuguese','pt-br':'Portuguese','português':'Portuguese','portuguese':'Portuguese',
           'en':'English','english':'English','ru':'Russian','russian':'Russian','es':'Spanish','spanish':'Spanish',
           'fr':'French','french':'French','de':'German','german':'German','it':'Italian','italian':'Italian',
           'ja':'Japanese','japanese':'Japanese','ko':'Korean','korean':'Korean','zh':'Chinese','chinese':'Chinese'}
NEW_EXPRESSIONS=(('CALMO 😌','calmo'),('ANIMADO 🤩','animado'),('MEDO 😨','medo'),('GRITO 😠','grito'),('CHORO 😢','choro'))
STYLES={'calmo':'Speak softly, calmly and reassuringly, with a measured pace.',
        'animado':'Speak with enthusiastic, excited and energetic delivery.',
        'medo':'Speak with a frightened, anxious and hesitant delivery.',
        'grito':'Shout the words loudly and urgently with a forceful projected voice.',
        'choro':'Speak sadly, close to tears, with a trembling emotional voice.'}

def root() -> Path:
    from dependency_setup import runtime_root
    return runtime_root()/'qwen'

def runtime():
    base=root().resolve()
    try:
        data=json.loads((base/'active.json').read_text(encoding='utf-8'))
        python=(base/data['python']).resolve()
        if python.is_relative_to(base) and python.is_file():return python,data
    except (OSError,ValueError,KeyError,TypeError):pass
    return None,{}

def validate(language,mode='clone'):
    if str(language).casefold() not in LANGUAGES:raise ValueError('Idioma não suportado pelo Qwen3-TTS.')
    if mode!='clone':raise ValueError('O Qwen Base clona um áudio de referência. Use Voice Cloning; as vozes de instrução estão em Texto para Fala.')

def install(job,variant='cpu'):
    # Do not install another backend's GPU packages into Qwen or claim DirectML support.
    if variant not in ('cpu','cu128'):
        job.write('Qwen: este perfil AMD/DirectML usará CPU. Os ambientes AMD existentes serão preservados.')
        variant='cpu'
    base=root();base.mkdir(parents=True,exist_ok=True)
    python,data=runtime()
    check='import torch,torchaudio,datasets;from qwen_tts import Qwen3TTSModel;print(torch.__version__)'
    if python and data.get('version')==VERSION and data.get('variant')==variant:
        try:
            job.run([python,'-c',check],timeout=180);job.write('[OK] Qwen existente reutilizado.');return
        except (OSError,RuntimeError):
            job.write('Ambiente Qwen incompleto; reparando apenas este ambiente.')
    if os.name=='nt':host=job.ensure_amd_python()
    else:
        host=shutil.which('python3.12')
        if not host:raise RuntimeError('Instale Python 3.12 pelo gerenciador oficial da distribuição.')
    env=base/('env-'+VERSION+'-'+variant)
    python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():job.run([host,'-m','venv',env])
    pip=[python,'-m','pip','install','--index-url','https://pypi.org/simple','--retries','3','--timeout','60','--progress-bar','raw']
    job.run([*pip,'--upgrade','pip'],timeout=300)
    job.run([*pip,'--index-url','https://download.pytorch.org/whl/'+variant,'torch==2.7.1','torchaudio==2.7.1'],timeout=7200)
    constraints=env/'constraints.txt'
    constraints.write_text('torch==2.7.1\ntorchaudio==2.7.1\ntransformers==4.57.3\naccelerate==1.12.0\nnumpy==1.26.4\nhuggingface-hub==0.36.2\n',encoding='utf-8')
    job.run([*pip,'-c',constraints,'qwen-tts==0.1.1','datasets<4','numpy==1.26.4','huggingface-hub==0.36.2','soundfile>=0.13'],timeout=7200)
    job.run([python,'-m','pip','check']);job.run([python,'-c',check],timeout=180)
    pending=base/'active.pending.json'
    pending.write_text(json.dumps({'python':python.relative_to(base).as_posix(),'version':VERSION,'variant':variant}),encoding='utf-8')
    pending.replace(base/'active.json')
    job.write('[OK] Qwen preparado em ambiente próprio. Baixe modelos e teste antes de dublar.')

def download(job,sizes_only=False):
    python,_=runtime()
    if not python:raise RuntimeError('Selecione Qwen3-TTS em REQUISITOS e execute o botão 1.')
    from f5_backend import DOWNLOAD_WORKER
    cache=root()/'models'
    prelude="import os;os.environ['HF_HUB_CACHE']="+repr(str(cache.resolve()))+";\n"
    job.run([python,'-u','-c',prelude+DOWNLOAD_WORKER,json.dumps(FILES),'1' if sizes_only else '0'],timeout=900 if sizes_only else 14400)
    job.write('[OK] Consulta concluída.' if sizes_only else '[OK] Base, CustomVoice, tokenizer e ASR disponíveis; arquivos existentes reutilizados.')

def inference_command():
    python,data=runtime()
    if not python:raise RuntimeError('Prepare Qwen3-TTS nos botões 1, 2 e 3 de REQUISITOS.')
    from batch_tab import find_ffmpeg_directory
    cache=root()/'models'
    prelude="import os;os.environ['HF_HUB_CACHE']="+repr(str(cache.resolve()))+";os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';\n"
    ff=find_ffmpeg_directory()
    if ff:prelude+="os.environ['PATH']="+repr(str(ff))+"+os.pathsep+os.environ.get('PATH','');\n"
    return [str(python),'-u','-c',prelude+WORKER,'--device','cuda' if data.get('variant')=='cu128' else 'cpu','--cache-root',str(root())]

def test(job,project_root=None):
    job.run([*inference_command(),'--test'],timeout=1200)
    reference=None
    if project_root:
        folder=Path(project_root)/'WAV ORIGINAIS'
        if folder.is_dir():reference=next((p for p in folder.rglob('*.wav') if p.is_file()),None)
    ref_args=[]
    if not reference:
        reference=root()/'test-reference.wav'
        text='Olá, esta é a voz de referência para o teste.'
        job.run([*inference_command(),'--model',CUSTOM_MODEL,'--text',text,'--instruct','QWEN_SPEAKER:Ryan','--output',reference],timeout=1800)
        ref_args=['--ref_text',text]
    output=root()/'test.wav'
    job.run([*inference_command(),'--model',MODEL,'--ref_audio',reference,*ref_args,'--text','Teste de dublagem em português.','--output',output],timeout=1800)
    import wave
    with wave.open(str(output)) as wav:
        if wav.getnframes()==0:raise RuntimeError('Teste Qwen retornou WAV vazio.')
        duration=wav.getnframes()/wav.getframerate()
    job.write(f'[OK] Síntese e clonagem testadas: {duration:.2f}s. Ouça o teste para avaliar pronúncia e qualidade: {output}')

def emotional_references(voice='masculina') -> dict[str,Path]:
    folder=(root()/'emotion-previews').resolve()
    refs={}
    try:data=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return refs
    if data.get('version')!=VERSION:return refs
    for key,item in data.get('voices',{}).get(voice,{}).items():
        if key not in STYLES:continue
        try:
            path=(folder/item['file']).resolve()
            if path.is_relative_to(folder) and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']:refs[key]=path
        except (OSError,KeyError,TypeError):continue
    return refs

def prepare_emotions(job):
    job.run([*inference_command(),'--emotion-bank',str(root()/'emotion-previews')],timeout=3600)
    job.write('Prévias Qwen geradas por instrução. Ouça para avaliar a interpretação antes de usar na fala.')

WORKER=r'''
import argparse,gc,hashlib,json,re,tempfile
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--model',default='Qwen/Qwen3-TTS-12Hz-1.7B-Base');p.add_argument('--text',default='')
p.add_argument('--language',default='Portuguese');p.add_argument('--instruct',default='')
p.add_argument('--ref_audio');p.add_argument('--ref_text',default='');p.add_argument('--output')
p.add_argument('--device',choices=('cpu','cuda'),default='cpu');p.add_argument('--cache-root',required=True)
p.add_argument('--test',action='store_true');p.add_argument('--emotion-bank')
a=p.parse_args()
BASE='Qwen/Qwen3-TTS-12Hz-1.7B-Base';CUSTOM='Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'
if a.model not in (BASE,CUSTOM):p.error('Modelo Qwen desconhecido')
langs={'pt':'Portuguese','pt-br':'Portuguese','português':'Portuguese','portuguese':'Portuguese','en':'English','english':'English','ru':'Russian','russian':'Russian','es':'Spanish','spanish':'Spanish','fr':'French','french':'French','de':'German','german':'German','it':'Italian','italian':'Italian','ja':'Japanese','japanese':'Japanese','ko':'Korean','korean':'Korean','zh':'Chinese','chinese':'Chinese'}
if a.language.casefold() not in langs:p.error('Idioma Qwen não suportado')
language=langs[a.language.casefold()]
if not a.test and not a.emotion_bank and (not a.text.strip() or not a.output):p.error('Texto e saída são obrigatórios')
from huggingface_hub import snapshot_download
import numpy as np,soundfile as sf,torch,librosa
from qwen_tts import Qwen3TTSModel
device='cuda:0' if a.device=='cuda' and torch.cuda.is_available() else 'cpu'
dtype=torch.bfloat16 if device.startswith('cuda') else torch.float32
def load(repo):
 print('Loading Qwen: '+repo+' / '+device,flush=True)
 path=snapshot_download(repo,local_files_only=True)
 model=Qwen3TTSModel.from_pretrained(path,device_map=device,dtype=dtype,attn_implementation='sdpa')
 print('Model loaded',flush=True);return model
def save(wavs,rate,path):
 if len(wavs)!=1:raise RuntimeError('Qwen não retornou exatamente um áudio')
 audio=np.asarray(wavs[0],dtype=np.float32)
 if not audio.size or not np.isfinite(audio).all():raise RuntimeError('Qwen retornou áudio vazio ou inválido')
 peak=float(np.max(np.abs(audio)))
 if peak>.99:audio=audio*(.99/peak)
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(suffix='.wav',dir=path.parent,delete=False) as handle:tmp=Path(handle.name)
 try:sf.write(tmp,audio,rate,subtype='PCM_24');tmp.replace(path)
 finally:tmp.unlink(missing_ok=True)
 print('Audio saved: '+str(path),flush=True)
if a.test:
 m=load(BASE);del m;gc.collect()
 if device.startswith('cuda'):torch.cuda.empty_cache()
 m=load(CUSTOM);print('Qwen Base e CustomVoice carregados; síntese ainda não testada',flush=True)
elif a.emotion_bank:
 styles={'calmo':'Speak softly, calmly and reassuringly, with a measured pace.','animado':'Speak with enthusiastic, excited and energetic delivery.','medo':'Speak with a frightened, anxious and hesitant delivery.','grito':'Shout the words loudly and urgently with a forceful projected voice.','choro':'Speak sadly, close to tears, with a trembling emotional voice.'}
 folder=Path(a.emotion_bank);folder.mkdir(parents=True,exist_ok=True)
 manifest=folder/'manifest.json';data={'version':'qwen-tts-0.1.1-torch271-v1','voices':{}}
 if manifest.is_file():
  try:data=json.loads(manifest.read_text(encoding='utf-8'))
  except (ValueError,OSError):pass
 if data.get('version')!='qwen-tts-0.1.1-torch271-v1':data={'version':'qwen-tts-0.1.1-torch271-v1','voices':{}}
 m=load(CUSTOM)
 for voice,speaker in (('masculina','Ryan'),('feminina','Vivian')):
  records=data.setdefault('voices',{}).setdefault(voice,{})
  for emotion,instruction in styles.items():
   path=folder/(voice+'_'+emotion+'.wav');record=records.get(emotion,{})
   if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==record.get('sha256'):
    print('Prévia existente reutilizada: '+voice+' / '+emotion,flush=True);continue
   print('Synthesizing prévia '+voice+' / '+emotion,flush=True)
   wavs,sr=m.generate_custom_voice(text='André, venha aqui. Eu preciso conversar com você agora.',language='Portuguese',speaker=speaker,instruct=instruction,max_new_tokens=1024)
   save(wavs,sr,path);records[emotion]={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'transcript':'André, venha aqui. Eu preciso conversar com você agora.','instruction':instruction}
   pending=manifest.with_suffix('.pending.json');pending.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');pending.replace(manifest)
else:
 reference=None;transcript=''
 if a.ref_audio:
  reference=Path(a.ref_audio)
  if not reference.is_file():raise FileNotFoundError('Áudio de referência ausente')
  print('Reference audio: preparando / transcribing',flush=True)
  audio,rate=librosa.load(reference,sr=None,mono=True)
  if not len(audio):raise RuntimeError('Referência vazia')
  transcript=a.ref_text.strip()
  # Never use the text to be generated as the reference transcript.
  cache=Path(a.cache_root)/'reference-transcripts';cache.mkdir(parents=True,exist_ok=True)
  digest=hashlib.sha256(reference.read_bytes()).hexdigest();cached=cache/(digest+'.txt')
  if not transcript and cached.is_file():transcript=cached.read_text(encoding='utf-8').strip()
  if not transcript:
   from transformers import pipeline
   asr=snapshot_download('openai/whisper-small',local_files_only=True)
   recognizer=pipeline('automatic-speech-recognition',model=asr,device=-1,torch_dtype=torch.float32)
   pcm=librosa.resample(audio,orig_sr=rate,target_sr=16000)
   transcript=recognizer({'array':pcm,'sampling_rate':16000},chunk_length_s=30)['text'].strip()
   del recognizer;gc.collect()
   if not transcript:raise RuntimeError('Não foi possível transcrever a referência; nenhuma síntese foi iniciada')
   cached.write_text(transcript,encoding='utf-8')
  m=load(BASE)
  if a.instruct.strip():print('Qwen Base transfere a interpretação da referência; instruções livres de emoção não são aplicadas neste modo.',flush=True)
  prompt=m.create_voice_clone_prompt(ref_audio=(audio,rate),ref_text=transcript,x_vector_only_mode=False)
 else:
  m=load(CUSTOM);speaker='Vivian' if ('female' in a.instruct.lower() or 'QWEN_SPEAKER:Vivian' in a.instruct) else 'Ryan'
 print('Synthesizing / generating audio',flush=True)
 # Chunk long texts; never pretend a token-limited segment is complete.
 chunks=re.split(r'(?<=[.!?])\s+',a.text.strip());sentences=[]
 for text in chunks:
  while len(text)>350:
   at=text.rfind(' ',0,350)
   if at<1:at=350
   sentences.append(text[:at]);text=text[at:].strip()
  if text:sentences.append(text)
 clips=[];sr=None
 for index,text in enumerate(sentences):
  print('Synthesizing trecho '+str(index+1)+'/'+str(len(sentences)),flush=True)
  if reference:wavs,rate=m.generate_voice_clone(text=text,language=language,voice_clone_prompt=prompt,max_new_tokens=2048)
  else:wavs,rate=m.generate_custom_voice(text=text,language=language,speaker=speaker,instruct=a.instruct.replace('QWEN_SPEAKER:Vivian','').replace('QWEN_SPEAKER:Ryan',''),max_new_tokens=2048)
  if len(wavs)!=1 or not len(wavs[0]):raise RuntimeError('Trecho Qwen vazio')
  if len(wavs[0])/rate>=2048/12-1:raise RuntimeError('Trecho atingiu limite de geração; nenhum resultado parcial será salvo')
  if sr is not None and sr!=rate:raise RuntimeError('Taxas de áudio incompatíveis')
  sr=rate
  if clips:clips.append(np.zeros(round(sr*.15),dtype=np.float32))
  clips.append(wavs[0])
  print(str(round((index+1)*100/len(sentences),1))+'%| Qwen trechos concluídos',flush=True)
 save([np.concatenate(clips)],sr,a.output)
'''
