"""Fish S1-mini: runtime isolado, sem bibliotecas de IA dentro do executável."""
import json
import os
import time
import re
from pathlib import Path

MODEL = 'fishaudio/s1-mini'
SOURCE_COMMIT = 'ef1af2079182ca38623c54b2dd4b934204e9dfd0'
MODEL_PAGE = 'https://huggingface.co/fishaudio/s1-mini'
EMOTIONS = {'alegre':'(joyful)', 'rindo':'(laughing)', 'triste':'(sad)',
            'sussurro':'(whispering)', 'suspiro':'(sighing)', 'surpreso':'(surprised)',
            'duvida':'(confused)', 'descontente':'(unhappy)',
            'grito':'(shouting)', 'grito_forte':'(screaming)', 'choro':'(sobbing)',
            'choro_intenso':'(crying loudly)', 'raiva':'(angry)', 'medo':'(scared)',
            'animado':'(excited)', 'suave':'(soft tone)', 'nervoso':'(nervous)',
            'calmo':'(relaxed)', 'sarcastico':'(sarcastic)', 'ofegante':'(panting)'}
NONVERBAL_EMOTIONS={'(laughing)','(sighing)','(sobbing)','(crying loudly)','(panting)'}

def speech_segments(text, limit=160):
    """Mantém o estilo por frase e separa reações não verbais da fala."""
    tags='|'.join(re.escape(value) for value in EMOTIONS.values())
    parts=re.split('('+tags+')',text)
    style='';result=[]
    for part in parts:
        if part in NONVERBAL_EMOTIONS:
            result.append(part);continue
        if part in EMOTIONS.values():
            style=part;continue
        if not part.strip():continue
        words=part.split();chunk=[];length=0
        for word in words:
            if chunk and length+len(word)+1>limit:
                result.append((style+' '+' '.join(chunk)).strip());chunk=[];length=0
            chunk.append(word);length+=len(word)+1
            if len(chunk)>=2 and word.endswith(('.','!','?',';',':')):
                result.append((style+' '+' '.join(chunk)).strip());chunk=[];length=0
        if chunk:result.append((style+' '+' '.join(chunk)).strip())
    return result


def runtime():
    from dependency_setup import runtime_root
    root = runtime_root()
    try:
        data = json.loads((root/'fish-active.json').read_text(encoding='utf-8'))
        python = (root/data['python']).resolve()
        python.relative_to(root.resolve())
        if python.is_file(): return python, data.get('variant','cpu')
    except (OSError, ValueError, KeyError): pass
    return None, 'cpu'

def model_directory():
    from dependency_setup import runtime_root
    root = runtime_root()
    try:
        path = Path((root/'fish-model.txt').read_text(encoding='utf-8').strip()).resolve()
        path.relative_to((root/'fish-models').resolve())
        if all((path/name).is_file() and (path/name).stat().st_size > 0 for name in ('model.pth','codec.pth','config.json','tokenizer.tiktoken','special_tokens.json')):
            return path
    except (OSError,ValueError): pass
    return None

def install(job, variant):
    from dependency_setup import runtime_root
    root = runtime_root()
    mode = 'cu128' if variant == 'cu128' else 'cpu'
    current,current_mode=runtime()
    if current and current_mode==mode:
        job.write('Verificando Fish já instalado; nenhum download iniciado…')
        check=("import torch,torchaudio,transformers,numpy;from pathlib import Path;"
               "from fish_speech.inference_engine import TTSInferenceEngine;"
               "from fish_speech.models.dac import inference as codec_module;"
               "assert torch.__version__.split('+')[0]=='2.8.0';"
               "assert torchaudio.__version__.split('+')[0]=='2.8.0';"
               "assert transformers.__version__=='4.51.3';assert numpy.__version__=='1.26.4';"
               "assert 'fish-speech-"+SOURCE_COMMIT+"' in str(Path(codec_module.__file__).resolve());"
               "assert (Path(codec_module.__file__).resolve().parents[2]/'configs'/'modded_dac_vq.yaml').is_file();"
               + ("assert torch.version.cuda=='12.8';assert torch.cuda.is_available();print(torch.ones(1,device='cuda'));" if mode=='cu128' else "assert torch.version.cuda is None;")
               + "print('Fish: versões, código oficial e importação OK')")
        try:
            job.run([current,'-c',check],timeout=180)
            job.run([current,'-m','pip','check'],timeout=180)
        except (RuntimeError,OSError,TimeoutError) as exc:
            job.checkpoint()
            job.write('Ambiente Fish precisa de reparo ou atualização: '+str(exc))
        else:
            job.write('[OK] Fish já instalado e compatível com esta versão. Nenhum pacote foi baixado ou reinstalado. Use o botão 2 apenas para verificar os modelos e o botão 3 para testá-los.')
            return
    # Legacy S1 requires numpy 1.26, which has no Python 3.13 wheels.
    python = job.ensure_amd_python()
    env = root/('fish-env-'+str(time.time_ns()))
    job.run([python,'-m','venv',env])
    exe = env/'Scripts'/'python.exe'
    if mode != variant: job.write('Fish S1-mini: este perfil usa CPU. A aceleração AMD continua disponível no motor já instalado.')
    pip = [exe,'-m','pip','install','--retries','3','--timeout','60','--progress-bar','raw']
    job.run([*pip,'--index-url','https://pypi.org/simple','--upgrade','pip'])
    job.run([*pip,'--index-url','https://download.pytorch.org/whl/'+mode,'torch==2.8.0','torchaudio==2.8.0'],timeout=7200)
    constraints = env/'constraints.txt'
    constraints.write_text('torch==2.8.0\ntorchaudio==2.8.0\nnumpy==1.26.4\ntransformers==4.51.3\n',encoding='utf-8')
    job.run([*pip,'--index-url','https://pypi.org/simple','-c',constraints,
             'numpy==1.26.4','transformers==4.51.3','huggingface_hub>=0.30,<1',
             'soundfile','librosa>=0.10,<0.12','hydra-core>=1.3,<1.4','lightning>=2.1,<2.6',
             'einops','rich','loguru','loralib','tiktoken>=0.8','pydantic==2.9.2',
             'cachetools','ormsgpack','pyrootutils','descript-audio-codec==1.0.0'],timeout=7200)
    # Editable install retains the official codec YAML files and subpackages.
    source_root=root/('fish-source-'+str(time.time_ns()))
    fetch="import urllib.request,zipfile,io,sys;from pathlib import Path;root=Path(sys.argv[1]);root.mkdir();data=urllib.request.urlopen(sys.argv[2],timeout=120).read();z=zipfile.ZipFile(io.BytesIO(data));assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist());z.extractall(root)"
    job.run([exe,'-u','-c',fetch,source_root,'https://github.com/fishaudio/fish-speech/archive/'+SOURCE_COMMIT+'.zip'],timeout=300)
    source=source_root/('fish-speech-'+SOURCE_COMMIT)
    job.run([*pip,'--index-url','https://pypi.org/simple','-c',constraints,'-e',source],timeout=7200)
    job.run([exe,'-m','pip','check'])
    # fish-speech declares training/server dependencies not used by inference;
    # install them too so package metadata remains consistent.
    job.run([exe,'-c','from fish_speech.inference_engine import TTSInferenceEngine;from fish_speech.models.dac.inference import load_model;print("Fish: importação validada")'],timeout=180)
    if mode == 'cu128':
        job.run([exe,'-c','import torch;assert torch.cuda.is_available(), "CUDA indisponível";print(torch.ones(1,device="cuda"))'])
    pending=root/'fish-active.pending.json'
    pending.write_text(json.dumps({'python':exe.relative_to(root).as_posix(),'variant':mode}),encoding='utf-8')
    pending.replace(root/'fish-active.json')
    job.write('[OK] Fish instalado em ambiente separado. Aceite os termos oficiais antes de baixar o modelo.')

DOWNLOAD_WORKER = r'''
import sys,json
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download,hf_hub_download,try_to_load_from_cache
from tqdm.auto import tqdm
import time
root=Path(sys.argv[1]);sizes=sys.argv[2]=='1';token_file=Path(sys.argv[3]) if sys.argv[3] else None
token=None
if token_file:
    token=token_file.read_text(encoding='utf-8').strip() or None
info=HfApi().model_info('fishaudio/s1-mini',files_metadata=True,token=token)
total=sum(f.size or 0 for f in info.siblings)
print('Modelo Fish: %.2f GB (dependências não incluídas)'%(total/1000**3),flush=True)
plan=[]
for f in info.siblings:
    cached=try_to_load_from_cache('fishaudio/s1-mini',f.rfilename,revision=info.sha,cache_dir=root/'fish-models')
    valid=isinstance(cached,str) and Path(cached).is_file() and (f.size is None or Path(cached).stat().st_size==f.size)
    plan.append((f,valid,isinstance(cached,str) and not valid))
missing=sum(f.size or 0 for f,valid,_ in plan if not valid)
print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name='Fish S1-mini',kind='size',total=total,missing=missing)),flush=True)
print('Ainda falta baixar: %.2f GB; arquivos íntegros no cache serão reutilizados.'%(missing/1000**3),flush=True)
if not sizes:
    try:
        import importlib
        hub_progress=importlib.import_module('huggingface_hub.utils.tqdm')
        file_download=importlib.import_module('huggingface_hub.file_download')
        class Bar(hub_progress.tqdm):
            def __init__(self,*args,**kwargs):
                self.last_report=0
                kwargs['disable']=False
                super().__init__(*args,**kwargs)
            def display(self,*args,**kwargs):
                now=time.monotonic()
                if now-getattr(self,'last_report',0)<.2:return
                self.last_report=now
                print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name=getattr(self,'desc','Fish'),current=int(getattr(self,'n',0)),total=int(getattr(self,'total',0) or 0))),flush=True)
        # The pinned Hub <1 exposes no tqdm_class parameter on hf_hub_download.
        # Hook only this isolated download process, never the application's imports.
        hub_progress.tqdm=Bar
        file_download.tqdm=Bar
        for f,valid,repair in plan:
            cached=try_to_load_from_cache('fishaudio/s1-mini',f.rfilename,revision=info.sha,cache_dir=root/'fish-models')
            if valid:print('DUBLASKIZON_TRANSFER '+json.dumps(dict(kind='cache',name='Já no cache: '+f.rfilename)),flush=True)
            if not valid:
                hf_hub_download('fishaudio/s1-mini',f.rfilename,revision=info.sha,token=token,cache_dir=root/'fish-models',force_download=repair)
                print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name=f.rfilename,current=f.size or 0,total=f.size or 0)),flush=True)
        path=snapshot_download('fishaudio/s1-mini',revision=info.sha,token=token,cache_dir=root/'fish-models',local_files_only=True)
    except Exception as e:
        if not any(word in str(e).casefold() for word in ('401','403','gated','unauthorized','forbidden')):raise
        print('DUBLASKIZON_FISH_AUTH_REQUIRED: Aceite os termos oficiais do Fish e autentique sua conta Hugging Face.',flush=True)
        sys.exit(42)
    (root/'fish-model.txt').write_text(path,encoding='utf-8')
    print('Fish: modelo já atualizado no cache; nenhum arquivo baixado.' if all(valid for _,valid,_ in plan) else 'Fish: download dos arquivos necessários concluído.',flush=True)
'''

def download(job, sizes_only=False, token_file=''):
    from dependency_setup import runtime_root
    python,_ = runtime()
    if not python: raise RuntimeError('Selecione Fish S1-mini e execute o botão 1 primeiro.')
    try:
        job.run([python,'-u','-c',DOWNLOAD_WORKER,str(runtime_root()),'1' if sizes_only else '0',str(token_file)],timeout=14400)
    except RuntimeError as exc:
        # SetupJob reports a generic nonzero exit; recover the worker's diagnosis.
        try:report=Path(job.log).read_text(encoding='utf-8',errors='replace')[-20000:]
        except (OSError,TypeError,AttributeError):report=''
        if any(marker in report.casefold() for marker in ('dublaskizon_fish_auth_required','gatedrepoerror','401 client error','403 client error')):
            raise RuntimeError('Autorize o acesso: aceite os termos em https://huggingface.co/fishaudio/s1-mini e autentique sua conta. Use INFORMAR CHAVE DO FISH E BAIXAR para informar seu token de leitura. Não reinstale as dependências; elas já estão prontas.') from None
        raise

INFERENCE_WORKER = r'''
import sys,json,queue,threading,os
os.environ['HF_HUB_OFFLINE']='0'
os.environ['TRANSFORMERS_OFFLINE']='0'
from pathlib import Path
import torch,soundfile as sf
data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
# The reference transcript describes the sample voice, never the requested new text.
if data.get('reference') and not data.get('reference_text','').strip():
    import hashlib,gc
    reference=Path(data['reference'])
    asr_root=Path(data['asr_root']);asr_root.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(reference.read_bytes()).hexdigest()
    cached=asr_root/(key+'.txt')
    transcript=cached.read_text(encoding='utf-8').strip() if cached.is_file() else ''
    if not transcript:
        print('Transcrevendo automaticamente a voz de referência (primeiro uso pode baixar Whisper base)…',flush=True)
        import numpy as np,librosa
        from faster_whisper import WhisperModel
        audio,sr=sf.read(str(reference),dtype='float32',always_2d=True)
        audio=audio.mean(axis=1)
        if sr!=16000:audio=librosa.resample(audio,orig_sr=sr,target_sr=16000)
        # Decode ourselves to avoid the PyAV metadata_errors incompatibility.
        os.environ['HF_HUB_OFFLINE']='0'
        os.environ['TRANSFORMERS_OFFLINE']='0'
        asr=WhisperModel('base',device='cpu',compute_type='int8',download_root=str(asr_root/'models'))
        segments,_=asr.transcribe(np.asarray(audio,dtype=np.float32),vad_filter=False,beam_size=5)
        transcript=' '.join(segment.text.strip() for segment in segments).strip()
        del asr;gc.collect()
        os.environ['HF_HUB_OFFLINE']='1'
        os.environ['TRANSFORMERS_OFFLINE']='1'
        if not transcript:raise RuntimeError('Não foi possível reconhecer fala na referência. Escolha uma gravação com voz clara ou informe sua transcrição no campo opcional.')
        cached.write_text(transcript,encoding='utf-8')
    else:print('Transcrição da referência reutilizada do cache.',flush=True)
    data['reference_text']=transcript
    print('Referência pronta. Gerando o texto novo com a voz selecionada.',flush=True)

os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
from huggingface_hub import constants as hf_constants
hf_constants.HF_HUB_OFFLINE=True
from fish_speech.models.text2semantic.inference import load_model,generate,GenerateResponse,WrappedGenerateResponse
from fish_speech.content_sequence import ContentSequence,TextPart,VQPart
from fish_speech.models.dac.inference import load_model as load_decoder
from fish_speech.inference_engine import TTSInferenceEngine
from fish_speech.utils.schema import ServeTTSRequest,ServeReferenceAudio
device='cuda' if data['variant']=='cu128' else 'cpu'
if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA indisponível; reinstale Fish no perfil CPU ou atualize o driver NVIDIA.')
precision=(torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if device=='cuda' else torch.float32
print('Carregando Fish S1-mini em '+device,flush=True)
model,decode=load_model(data['model'],device,precision,compile=False)
with torch.device(device):
    model.setup_caches(max_batch_size=1,max_seq_len=model.config.max_seq_len,dtype=next(model.parameters()).dtype)
# S1 protocol: the reference and requested speech belong to the same speaker.
# Matches the official fishaudio/s1-mini Space's ContentSequence prompt layout.
def generate_s1(*,model,decode_one_token,device,text,prompt_text=None,prompt_tokens=None,max_new_tokens=4096,temperature=.7,top_p=.8,repetition_penalty=1.1,**unused):
    sequence=ContentSequence(modality='interleave')
    for reference_text,reference_tokens in zip(prompt_text or [],prompt_tokens or []):
        sequence.append([TextPart(text=reference_text),VQPart(codes=reference_tokens.cpu())],add_end=True,speaker=0)
    sequence.append(TextPart(text=text),speaker=0)
    encoded=sequence.encode_for_inference(model.tokenizer,num_codebooks=model.config.num_codebooks).to(device)
    count=encoded.size(1)
    if count>model.config.max_seq_len-2048:raise ValueError('Referência longa demais. Escolha uma amostra de voz menor.')
    result=generate(model=model,prompt=encoded,max_new_tokens=max_new_tokens,decode_one_token=decode_one_token,
                    temperature=torch.tensor(temperature,device=device),top_p=torch.tensor(top_p,device=device),
                    repetition_penalty=torch.tensor(repetition_penalty,device=device))
    yield GenerateResponse(action='sample',codes=result[1:,count:-1].clone(),text=text)
    yield GenerateResponse(action='next')

q=queue.Queue()
def serve():
    while True:
        item=q.get()
        if item is None:return
        try:
            options=dict(item.request);options['iterative_prompt']=False
            for chunk in generate_s1(model=model,decode_one_token=decode,**options):
                item.response_queue.put(WrappedGenerateResponse(status='success',response=chunk))
        except Exception as e:item.response_queue.put(WrappedGenerateResponse(status='error',response=e))
threading.Thread(target=serve,daemon=True).start()
decoder=load_decoder('modded_dac_vq',Path(data['model'])/'codec.pth',device=device)
engine=TTSInferenceEngine(llama_queue=q,decoder_model=decoder,precision=precision,compile=False)
print('Fish carregado; '+('teste concluído.' if data.get('test') else 'gerando fala…'),flush=True)
if not data.get('test'):
    refs=[]
    if data.get('reference'):
        refs=[ServeReferenceAudio(audio=Path(data['reference']).read_bytes(),text=data['reference_text'])]
    import numpy as np,librosa,re,difflib,unicodedata
    from faster_whisper import WhisperModel
    os.environ['HF_HUB_OFFLINE']='0';hf_constants.HF_HUB_OFFLINE=False
    print('Preparando verificação da fala com Whisper base (modelo reutilizado quando presente)…',flush=True)
    verifier=WhisperModel('base',device='cpu',compute_type='int8',download_root=str(Path(data['asr_root'])/'models'))
    os.environ['HF_HUB_OFFLINE']='1';hf_constants.HF_HUB_OFFLINE=True
    def tokens(text):
        text=re.sub(r'\([^)]*\)',' ',text)
        text=''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))
        return re.findall(r'\w+',text)
    complete=[];rate=None
    segments=data['segments']
    if not segments:raise RuntimeError('Escreva palavras para gerar a fala ou escolha uma reação sonora.')
    for index,part in enumerate(segments,1):
        print('PARTE %d/%d — comando enviado: %s'%(index,len(segments),part),flush=True)
        expected=tokens(part);accepted=False;best=None
        for attempt in range(1,5):
            request=ServeTTSRequest(text=part,references=refs,normalize=False,streaming=False,format='wav',max_new_tokens=4096,temperature=0.7 if attempt==1 else 0.8,seed=(data.get('seed',1200)+index*5+attempt)%2147483647)
            generated=None
            for result in engine.inference(request):
                if result.code=='error':raise RuntimeError(str(result.error))
                if result.code=='final' and result.audio is not None:rate,generated=result.audio
            if generated is None or not len(generated):raise RuntimeError('Fish não retornou áudio para a parte '+str(index))
            if not expected:accepted=True
            else:
                check=librosa.resample(np.asarray(generated,dtype=np.float32),orig_sr=rate,target_sr=16000)
                transcript,_=verifier.transcribe(check,language='pt',vad_filter=False,beam_size=5)
                heard=' '.join(segment.text.strip() for segment in transcript)
                actual=tokens(heard)
                # Ordered fuzzy alignment tolerates whisper recognition inflections
                # (eles/ele, foram/for) while still checking the end of the phrase.
                row=[0]*(len(actual)+1)
                for word in expected:
                    previous=row;row=[0]
                    for column,heard_word in enumerate(actual,1):
                        similar=difflib.SequenceMatcher(None,word,heard_word).ratio()>=.75
                        row.append(max(row[-1],previous[column],previous[column-1]+int(similar)))
                coverage=row[-1]/len(expected)
                ending=any(difflib.SequenceMatcher(None,expected[-1],word).ratio()>=.75 for word in actual[-4:])
                if best is None or coverage>best[0]:best=(coverage,ending,generated,rate,heard)
                accepted=coverage>=.8 and ending
                if len(expected)<=3:
                    # Very short whispered interjections cannot be reliably verified by ASR.
                    accepted=bool(actual) and ending and coverage>=.5
                    if accepted and coverage<.8:
                        print('AVISO: verificação inconclusiva de frase curta; uma palavra ou interjeição pode não ter sido reconhecida. Confira esta parte ouvindo o resultado.',flush=True)
                print('VERIFICAÇÃO %d/%d — %.0f%% de correspondência aproximada; ouvido: %s'%(index,len(segments),coverage*100,heard),flush=True)
            if accepted:break
            print('Fala não confirmada como completa. Regerando esta parte (tentativa %d/4)…'%(attempt+1) if attempt<4 else 'Parte não confirmada após quatro tentativas.',flush=True)
        if not accepted and best and best[0]>=.65 and best[1]:
            generated,rate=best[2],best[3]
            print('AVISO: verificação inconclusiva — parte %d salva PARA CONFERIR, não confirmada como completa. Correspondência aproximada %.0f%%; ouvido: %s'%(index,best[0]*100,best[4]),flush=True)
            accepted=True
        if not accepted:raise RuntimeError('A parte %d não foi confirmada como completa após quatro tentativas. Nenhum resultado parcial foi salvo como final. Confira o texto e a referência; a verificação automática também pode errar.'%index)
        if complete:complete.append(np.zeros(int(rate*.08),dtype=np.float32))
        complete.append(np.asarray(generated,dtype=np.float32))
        print('PARTE %d/%d concluída.'%(index,len(segments)),flush=True)
    sf.write(data['output'],np.concatenate(complete),rate,subtype='PCM_16')
    print('Fala salva.',flush=True)
'''

def command(payload, output):
    python,variant=runtime();model=model_directory()
    if not python or not model:raise RuntimeError('Prepare Fish S1-mini em REQUISITOS: selecione o modelo e execute 1, 2 e 3.')
    from dependency_setup import runtime_root
    import secrets
    data=dict(payload,variant=variant,model=str(model),output=str(output),asr_root=str(runtime_root()/'fish-reference-transcripts'),segments=speech_segments(payload.get('text','')),seed=secrets.randbelow(2147483647))
    request=Path(output).with_suffix('.fish-request.json')
    request.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    return [str(python),'-u','-c',INFERENCE_WORKER,str(request)],request

def test(job):
    from dependency_setup import runtime_root
    request=runtime_root()/'fish-test.wav'
    args,path=command({'test':True},request)
    try:job.run(args,timeout=1800)
    finally:path.unlink(missing_ok=True)
    job.write('[OK] Fish carregado. A geração e a emoção precisam ser conferidas com uma fala real.')
