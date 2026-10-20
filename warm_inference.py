"""Reuse an isolated OmniVoice worker within one batch; release it afterwards.

The host uses only the standard library. Quality parameters and verification
remain in the original command, executed unchanged in the managed environment.
"""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path
import subprocess
import uuid


SERVER_CODE = r'''
import gc, hashlib, json, os, sys, traceback
import torch
# Leave CPU capacity for the interface, playback and Windows.
if hasattr(torch,'set_num_threads'):torch.set_num_threads(max(1,min(4,(os.cpu_count() or 2)//2)))
from omnivoice.models.omnivoice import OmniVoice
_load = OmniVoice.from_pretrained
_generate = OmniVoice.generate
_prompt = OmniVoice.create_voice_clone_prompt
_load_asr = getattr(OmniVoice, 'load_asr_model', None)
_models = {}
_prompts = {}

def gpu_asr_has_headroom():
    try:
        if not torch.cuda.is_available():return False
        free,total=torch.cuda.mem_get_info()
        # Whisper plus transient tensors retain at least ~1.5 GiB headroom.
        return total>=7*1024**3 and free>=3*1024**3
    except (AttributeError,RuntimeError):return False

def limited_vram(device):
    if not str(device).startswith('cuda'): return False
    return (os.environ.get('DUBLASKIZON_LOW_VRAM') == '1' or
            torch.cuda.get_device_properties(device).total_memory <= 7 * 1024**3)

class StagedASR:
    # Transfer weights only; the same FP16 Whisper still runs on CUDA.
    def __init__(self, owner, pipe, device):
        self.owner, self.pipe, self.device = owner, pipe, device
    def __getattr__(self, name): return getattr(self.pipe, name)
    def session(self):
        from contextlib import contextmanager
        @contextmanager
        def resident():
            self.owner.to('cpu')
            torch.cuda.empty_cache()
            try:
                self.pipe.model.to(self.device)
                self._resident=True
                yield
            finally:
                self._resident=False
                self.pipe.model.to('cpu')
                torch.cuda.empty_cache()
                self.owner.to(self.device)
        return resident()
    def __call__(self, *args, **kwargs):
        if self.__dict__.get('_resident',False):return self.pipe(*args,**kwargs)
        self.owner.to('cpu')
        torch.cuda.empty_cache()
        try:
            self.pipe.model.to(self.device)
            return self.pipe(*args, **kwargs)
        finally:
            self.pipe.model.to('cpu')
            torch.cuda.empty_cache()
            self.owner.to(self.device)

def load_asr(self, model_name=None, device=None):
    if os.environ.get('DUBLASKIZON_ASR_CPU')=='1':
        result=_load_asr(self,model_name,'cpu')
        if getattr(self,'_asr_pipe',None) is not None:self._asr_pipe._dublaskizon_cpu_recovery=True
        return result
    target = device or self._asr_device or self.device
    if not limited_vram(target):
        return _load_asr(self, model_name, device)
    synthesis_device = self.device
    self.to('cpu')
    torch.cuda.empty_cache()
    try:
        _load_asr(self, model_name, target)
        self._asr_pipe.model.to('cpu')
        self._asr_pipe = StagedASR(self, self._asr_pipe, synthesis_device)
        print('DESEMPENHO: GPU de pouca memória — síntese e Whisper alternados; modelos e qualidade preservados.', flush=True)
    finally:
        torch.cuda.empty_cache()
        self.to(synthesis_device)

def report_state():
    data={'model_ready':bool(_models),'asr_ready':any(getattr(m,'_asr_pipe',None) is not None for m in _models.values())}
    try:
        data['gpu_allocated']=torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
        data['gpu_reserved']=torch.cuda.memory_reserved() if torch.cuda.is_available() else 0
    except Exception:pass
    print('DUBLASKIZON_WORKER_STATE '+json.dumps(data),flush=True)

def load(cls, *args, **kwargs):
    key = repr((args, sorted(kwargs.items())))
    if key not in _models:
        _models.clear()
        _prompts.clear()
        report_state()
        gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()
        _models[key] = _load(*args, **kwargs)
    else:
        print('DESEMPENHO: OmniVoice e conferência reutilizados nesta fila.', flush=True)
    report_state()
    return _models[key]

def prompt(self, ref_audio, ref_text=None, preprocess_prompt=True):
    key = None
    if isinstance(ref_audio, (str, os.PathLike)):
        path = os.path.abspath(ref_audio)
        stat = os.stat(path)
        key = (path, stat.st_size, stat.st_mtime_ns, ref_text, preprocess_prompt)
    elif isinstance(ref_audio, tuple) and hasattr(ref_audio[0], 'tobytes'):
        audio, rate = ref_audio
        key = (hashlib.sha256(audio.tobytes()).hexdigest(), rate, ref_text, preprocess_prompt)
    if key is not None and key in _prompts:
        print('DESEMPENHO: referência da voz reutilizada.', flush=True)
        return _prompts[key]
    result = _prompt(self, ref_audio, ref_text, preprocess_prompt)
    if key is not None:
        if len(_prompts) >= 4: _prompts.pop(next(iter(_prompts)))
        _prompts[key] = result
    return result

OmniVoice.from_pretrained = classmethod(load)
if _load_asr is not None: OmniVoice.load_asr_model = load_asr
for line in sys.stdin:
    request = json.loads(line)
    if request.get('close'): break
    rc = 0
    try:
        args=request['args']
        reference_long=False
        if '--ref_audio' in args:
            try:
                import soundfile as sf
                reference_long=sf.info(args[args.index('--ref_audio')+1]).duration>20
            except (OSError,RuntimeError,ImportError):pass
        long_text=('--text' in args and len(args[args.index('--text')+1].split())>=120) or ('--duration' in args and float(args[args.index('--duration')+1])>=45)
        force_asr_cpu='DUBLASKIZON_ASR_CPU_RECOVERY' in request['code'] or ((reference_long or long_text) and not gpu_asr_has_headroom())
        previous_asr_cpu=os.environ.get('DUBLASKIZON_ASR_CPU')
        if force_asr_cpu:os.environ['DUBLASKIZON_ASR_CPU']='1'
        safe_reference='DUBLASKIZON_SAFE_REFERENCE' in request['code']
        long_scene=force_asr_cpu
        if (reference_long or long_text) and not force_asr_cpu:print('DESEMPENHO: conferência na GPU com memória livre suficiente; proteções de referência e duração ativas.',flush=True)
        previous_low_vram=os.environ.get('DUBLASKIZON_LOW_VRAM')
        if long_scene:
            os.environ['DUBLASKIZON_LOW_VRAM']='1'
            for cached_model in _models.values():
                pipe=getattr(cached_model,'_asr_pipe',None)
                if force_asr_cpu and pipe is not None:
                    while isinstance(pipe,StagedASR):pipe=pipe.pipe
                    pipe.model.to(device='cpu',dtype=torch.float32)
                    pipe.device=torch.device('cpu')
                    pipe._dublaskizon_cpu_recovery=True
                    cached_model._asr_pipe=pipe
                elif pipe is not None and not getattr(pipe,'_dublaskizon_cpu_recovery',False) and not isinstance(pipe,StagedASR) and str(getattr(cached_model,'device','cpu')).startswith('cuda'):
                    pipe.model.to('cpu')
                    cached_model._asr_pipe=StagedASR(cached_model,pipe,cached_model.device)
            if torch.cuda.is_available():torch.cuda.empty_cache()
            print('ESTABILIDADE: áudio longo — reconhecimento na CPU e síntese na GPU; sem transferências repetidas dos modelos.',flush=True)
        # Each embedded adapter must wrap the base once, never a previous wrapper.
        OmniVoice.generate = _generate
        OmniVoice.create_voice_clone_prompt = prompt
        sys.argv = ['-c', *request['args']]
        with torch.inference_mode():
            scene_namespace = {'__name__': '__main__'}
            exec(compile(request['code'], '<dublaskizon-scene>', 'exec'), scene_namespace)
            if 'OmniVoice.generate = _verified_generate' in request['code'] and not (scene_namespace.get('_DUBLASKIZON_TEXT_COMPLETE') or scene_namespace.get('_DUBLASKIZON_TEXT_AVAILABLE')):
                raise RuntimeError('A cena não confirmou o texto inteiro; saída não publicada.')
    except SystemExit as error:
        rc = error.code if isinstance(error.code, int) else 1
    except BaseException as error:
        rc = 1
        traceback.print_exc()
        if 'out of memory' in str(error).lower():
            _models.clear(); _prompts.clear(); gc.collect()
            if torch.cuda.is_available(): torch.cuda.empty_cache()
    finally:
        OmniVoice.generate = _generate
        if 'scene_namespace' in globals():scene_namespace.clear()
        gc.collect()
        if torch.cuda.is_available():torch.cuda.empty_cache()
        if 'previous_asr_cpu' in globals():
            if previous_asr_cpu is None:os.environ.pop('DUBLASKIZON_ASR_CPU',None)
            else:os.environ['DUBLASKIZON_ASR_CPU']=previous_asr_cpu
        if 'previous_low_vram' in globals():
            if previous_low_vram is None:os.environ.pop('DUBLASKIZON_LOW_VRAM',None)
            else:os.environ['DUBLASKIZON_LOW_VRAM']=previous_low_vram
        report_state()
        print('\n' + request['marker'] + str(rc), flush=True)
_models.clear(); _prompts.clear()
'''


class SceneProcess:
    """Subset of Popen used by the existing scene loops and cancel buttons."""
    def __init__(self, process, marker, state_callback=None):
        self.state_callback=state_callback
        self.process = process
        self.marker = marker
        self.returncode = None
        self.stdout = self._lines()
        self.pid = process.pid

    def _lines(self):
        for line in self.process.stdout:
            if line.startswith('DUBLASKIZON_WORKER_STATE ') and self.state_callback:
                try:self.state_callback(json.loads(line.split(' ',1)[1]))
                except (ValueError,TypeError):pass
            if line.startswith(self.marker):
                self.returncode = int(line[len(self.marker):].strip())
                return
            yield line
        self.returncode = self.process.wait() or 1

    def wait(self):
        if self.returncode is None:
            for _line in self.stdout:
                pass
        return self.returncode

    def poll(self):
        return self.returncode if self.returncode is not None else self.process.poll()

    def terminate(self):
        self.process.terminate()

    def kill(self):
        self.process.kill()


class WarmInference:
    def __init__(self):
        self.process = None
        self.key = None
        self.state = {}

    @staticmethod
    def eligible(command):
        if len(command) < 4 or command[2] != '-c' or '--model' not in command:
            return False
        model = command[command.index('--model') + 1]
        # Custom executables and other engines retain their original runner.
        return ('omnivoice' in model.lower() and
                'runtime' in Path(command[0]).parts and Path(command[0]).is_file())

    def start(self, command, **options):
        if not self.eligible(command):
            return subprocess.Popen(command, **options)
        environment=dict(options.get('env') or os.environ)
        environment.update(PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
        key = (command[0], tuple(sorted(environment.items())))
        if self.process is None or self.process.poll() is not None or key != self.key:
            self.close()
            worker_options = dict(options)
            worker_environment = dict(options.get('env') or os.environ)
            worker_environment.update(PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
            worker_options.update(stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, bufsize=1,
                                  encoding='utf-8', errors='replace', env=worker_environment)
            self.process = subprocess.Popen([command[0], '-u', '-c', SERVER_CODE], **worker_options)
            self.key = key
        marker = 'DUBLASKIZON_SCENE_END_' + uuid.uuid4().hex + ':'
        self.process.stdin.write(json.dumps({'args': command[4:], 'code': command[3], 'marker': marker}) + '\n')
        self.process.stdin.flush()
        return SceneProcess(self.process, marker, lambda value:setattr(self,'state',value))

    def close(self):
        process, self.process = self.process, None
        self.state = {}
        if process is None:
            return
        try:
            if process.poll() is None:
                process.stdin.write('{"close": true}\n')
                process.stdin.flush()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        except (OSError, ValueError):
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        finally:
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()


def warm_batch(function):
    """Keep ownership local to the batch; even exceptions close the worker."""
    @functools.wraps(function)
    def run(self, *args, **kwargs):
        if getattr(self,'share_review_memory_cache',False) and review_memory_cache.enabled:
            self._warm_inference=None
            return function(self,*args,**kwargs)
        review_memory_cache.evict_idle()
        pool = WarmInference()
        self._warm_inference = pool
        try:
            return function(self, *args, **kwargs)
        finally:
            pool.close()
            self._warm_inference = None
    return run

# Manual review cache: opt-in and separate from the batch-owned worker.
import threading
import time
import ctypes
import atexit
import tempfile
from contextlib import contextmanager


def available_memory():
    """Return (available, total) physical RAM on Windows; None elsewhere."""
    if os.name != 'nt':
        return None
    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong),
                    ('total',ctypes.c_ulonglong),('available',ctypes.c_ulonglong),
                    ('page_total',ctypes.c_ulonglong),('page_available',ctypes.c_ulonglong),
                    ('virtual_total',ctypes.c_ulonglong),('virtual_available',ctypes.c_ulonglong),
                    ('extended',ctypes.c_ulonglong)]
    status=MemoryStatus();status.length=ctypes.sizeof(status)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return int(status.available),int(status.total)
    return None


def memory_allows_cache():
    data=available_memory()
    return data is None or data[0] >= max(1024**3,int(data[1]*.10))


class LoggedScene:
    """Drain the persistent worker into the existing progress log, asynchronously."""
    def __init__(self, scene, output, finished):
        self.scene,self.pid=scene,scene.pid
        self.returncode=None
        self.done=threading.Event()
        def drain():
            code=1
            try:
                for line in scene.stdout:
                    write_log(output,line)
                code=scene.wait()
            except (OSError,ValueError,RuntimeError,TypeError):
                scene.terminate()
            finally:
                self.returncode=code
                # Release the cache lease before the caller can start another scene.
                finished(code)
                self.done.set()
        self.reader=threading.Thread(target=drain,daemon=True)
        self.reader.start()
    def poll(self):
        return self.returncode if self.done.is_set() else None
    def wait(self,timeout=None):
        if not self.done.wait(timeout):
            raise subprocess.TimeoutExpired('redublagem em memória',timeout)
        return self.returncode
    def terminate(self):self.scene.terminate()
    def kill(self):self.scene.kill()


def write_log(output,text):
    # run_observed opens a binary log; some callers/tests use a text stream.
    try:output.write(text)
    except TypeError:output.write(text.encode('utf-8',errors='replace'))
    output.flush()


class ReviewMemoryCache:
    """One resident manual-review engine, no concurrent access or quality changes."""
    def __init__(self, settings_path=None):
        self.settings_path=Path(settings_path) if settings_path else Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Dublaskizon/runtime/review-memory-settings.json'
        self.config={'profile_version':2,'idle_minutes':0,'min_scenes':1,'keep_while_review':True,'reserve_mb':1024}
        try:
            saved=json.loads(self.settings_path.read_text(encoding='utf-8'))
            if isinstance(saved,dict) and saved.get('profile_version')==2:
                saved['reserve_mb']=max(1024,int(saved.get('reserve_mb',1024)))
                self.config.update(self.validate_config(saved))
        except (OSError,ValueError,TypeError):pass
        self.review_context=False
        self.completed_scenes=0
        self.preparing=False
        self.preloading=False
        self.preload_process=None
        self.preload_done=threading.Event();self.preload_done.set()
        self.low_ram_since=None
        self.last_reason='Aguardando primeira redublagem'
        self.lock=threading.RLock()
        self.enabled=False
        self.active=False
        self.pool=WarmInference()
        self.last_used=time.monotonic()
        self.stop_monitor=threading.Event()
        self.monitor=None
    @staticmethod
    def validate_config(values):
        if not isinstance(values,dict):raise ValueError('Regulagens de memória inválidas.')
        config={}
        for key,default,low,high in [('idle_minutes',0,0,1440),('min_scenes',1,1,100),('reserve_mb',1024,1024,8192)]:
            value=int(values.get(key,default))
            if not low<=value<=high:raise ValueError('Regulagem fora do limite: '+key)
            config[key]=value
        config['profile_version']=2
        config['keep_while_review']=bool(values.get('keep_while_review',True))
        return config
    def configure(self, values):
        config=self.validate_config(values)
        self.settings_path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.settings_path.with_name(self.settings_path.name+'.'+uuid.uuid4().hex+'.tmp')
        temporary.write_text(json.dumps(config,indent=2),encoding='utf-8')
        os.replace(temporary,self.settings_path)
        with self.lock:self.config=config
    def memory_ok(self):
        data=available_memory()
        return data is None or data[0]>=self.config['reserve_mb']*1024**2
    def snapshot(self):
        with self.lock:
            process=self.pool.process
            alive=process is not None and process.poll() is None
            state=dict(self.pool.state) if alive else {}
            return dict(enabled=self.enabled,active=self.active,preparing=self.preparing,preloading=self.preloading,
                        pid=process.pid if alive else None,review_context=self.review_context,
                        completed=self.completed_scenes,reason=self.last_reason,**state)
    def set_review_context(self, active):
        with self.lock:self.review_context=bool(active)
    @contextmanager
    def translation_session(self, cancelled=lambda:False):
        while self.preloading:
            if cancelled():raise RuntimeError('Transcrição/tradução cancelada.')
            self.preload_done.wait(.1)
        if cancelled():raise RuntimeError('Transcrição/tradução cancelada.')
        with self.lock:
            if self.active or self.preparing:
                raise RuntimeError('Aguarde a geração ou transcrição/tradução em andamento terminar.')
            self.preparing=True
        try:
            self.evict_idle('Liberado para transcrição/tradução; recarrega ao redublar')
            yield
        finally:
            with self.lock:self.preparing=False
    def set_enabled(self, enabled):
        with self.lock:
            self.enabled=bool(enabled)
            if self.enabled and self.monitor is None:
                self.monitor=threading.Thread(target=self._watch,daemon=True)
                self.monitor.start()
        if not enabled:
            process=self.preload_process if self.preloading else None
            if process is not None:
                try:process.terminate()
                except OSError:pass
            threading.Thread(target=self.evict_idle,daemon=True).start()
    def evict_idle(self, reason='Liberado para outra operação'):
        with self.lock:
            if self.active:return
            pool,self.pool=self.pool,WarmInference()
            self.last_reason=reason
        pool.close()
    def _watch(self):
        while not self.stop_monitor.wait(10):
            self.check_retention()
    def check_retention(self):
        if not self.memory_ok():
            now=time.monotonic()
            if self.low_ram_since is None:self.low_ram_since=now
            data=available_memory()
            if now-self.low_ram_since>=30 or (data is not None and data[0]<768*1024**2):
                self.evict_idle('Liberado por RAM criticamente baixa')
        else:
            self.low_ram_since=None
        if self.memory_ok() and self.config['idle_minutes'] and time.monotonic()-self.last_used>self.config['idle_minutes']*60:
            if not (self.review_context and self.config['keep_while_review']):
                self.evict_idle('Liberado pelo tempo de inatividade configurado')
    def _finished(self, returncode=0, count_scene=True):
        with self.lock:
            self.active=False
            self.last_used=time.monotonic()
            if returncode==0 and count_scene:self.completed_scenes+=1
            release=not self.enabled or (count_scene and not self.review_context and self.completed_scenes<self.config['min_scenes'])
            reason='Desativado' if not self.enabled else ('Liberado por pouca RAM disponível' if not self.memory_ok() else 'Aguardando sequência configurada de redublagens')
        if release:self.evict_idle(reason)
        else:self.check_retention()
    def start(self,command,**options):
        is_preload=options.pop('_preload',False)
        with self.lock:
            if self.preparing:raise RuntimeError('Aguarde a transcrição/tradução antes de iniciar a síntese.')
        if not WarmInference.eligible(command) or options.get('stdout') in (None,subprocess.PIPE,subprocess.DEVNULL):
            self.evict_idle()
            return subprocess.Popen(command,**options)
        with self.lock:
            if self.active:
                raise RuntimeError('Aguarde a redublagem em andamento antes de iniciar outra.')
            enabled=self.enabled
        if not enabled:
            self.evict_idle()
            return subprocess.Popen(command,**options)
        if not self.memory_ok():
            self.evict_idle('Liberado por pouca RAM disponível')
            write_log(options['stdout'],'MEMÓRIA: RAM disponível baixa; motor não será mantido carregado.\n')
            return subprocess.Popen(command,**options)
        with self.lock:
            if self.active:
                raise RuntimeError('Aguarde a redublagem em andamento antes de iniciar outra.')
            self.active=True
            pool=self.pool
        try:
            output=options['stdout']
            write_log(output,'MEMÓRIA: motor OmniVoice mantido entre redublagens; parâmetros e conferência preservados.\n')
            scene=pool.start(command,**options)
            return LoggedScene(scene,output,lambda code:self._finished(code,count_scene=not is_preload))
        except BaseException:
            self._finished(1)
            raise
    def preload(self, model):
        with self.lock:
            if not self.enabled or self.active or self.preparing or self.preloading:return
            self.preloading=True;self.preload_done.clear()
        def worker():
            try:
                command=preload_command(model)
                if not command:raise RuntimeError('Pré-carga disponível para OmniVoice instalado no ambiente gerenciado.')
                environment={**os.environ,'PYTHONUNBUFFERED':'1','PYTHONIOENCODING':'utf-8'}
                options={'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)} if os.name=='nt' else {}
                with tempfile.TemporaryFile('w+b') as output:
                    scene=self.start(command,stdout=output,text=True,env=environment,_preload=True,**options)
                    self.preload_process=scene
                    if not self.enabled:scene.terminate()
                    try:code=scene.wait(timeout=180)
                    except subprocess.TimeoutExpired:
                        scene.kill();scene.wait(timeout=5)
                        raise RuntimeError('Pré-carga interrompida após 3 minutos; tente preparar novamente.')
                    if code:
                        output.seek(0)
                        raise RuntimeError(output.read().decode('utf-8',errors='replace')[-400:])
            except Exception as exc:
                self.last_reason='Falha na pré-carga: '+str(exc).replace('\n',' ')[-220:]
            finally:
                self.preload_process=None
                self.preloading=False;self.preload_done.set()
        threading.Thread(target=worker,daemon=True).start()

    def shutdown(self):
        self.stop_monitor.set()
        with self.lock:
            self.enabled=False
            pool,self.pool=self.pool,WarmInference()
        pool.close()


def preload_command(model):
    if 'omnivoice' not in model.lower():return None
    from batch_tab import find_voice_command
    prefix=find_voice_command(model)
    if not prefix or len(prefix)<4 or prefix[2]!='-c':return None
    code="""import sys,os,torch
from omnivoice.models.omnivoice import OmniVoice
from omnivoice.utils.common import get_best_device
import huggingface_hub.constants as constants
previous=constants.HF_HUB_OFFLINE
constants.HF_HUB_OFFLINE=True
try:
    model=OmniVoice.from_pretrained(sys.argv[sys.argv.index('--model')+1],device_map=get_best_device(),dtype=torch.float16)
    model.load_asr_model()
finally:
    constants.HF_HUB_OFFLINE=previous
"""
    return [*prefix[:3],code,'--model',model]


review_memory_cache=ReviewMemoryCache()
atexit.register(review_memory_cache.shutdown)
