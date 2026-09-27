"""Official dependency bootstrap. Importable without Tk or third-party packages."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

PYTHON_VERSION = "3.13.15"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-amd64.exe"
PYTHON_SHA256 = "edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403"
AMD_PYTHON_VERSION = "3.12.10"
AMD_PYTHON_URL = f"https://www.python.org/ftp/python/{AMD_PYTHON_VERSION}/python-{AMD_PYTHON_VERSION}-amd64.exe"
AMD_PYTHON_SHA256 = "67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb"
AMD_SUPPORTED_GPUS = ("RX 9070 XT", "RX 9070", "AI PRO R9700", "RX 9060 XT",
                      "RX 7900 XTX", "PRO W7900 DUAL SLOT", "PRO W7900", "RX 7700", "RX 7600",
                      "RYZEN AI MAX+ 395", "RYZEN AI MAX 390", "RYZEN AI MAX 385",
                      "RYZEN AI 9 HX 375", "RYZEN AI 9 HX 370", "RYZEN AI 9 365",
                      "RYZEN AI 9 HX 475", "RYZEN AI 9 HX 470", "RYZEN AI 9 465")
DIRECTML_RX500 = ("RX 590", "RX 580", "RX 570", "RX 560")
MODELS = ("edwixx/omnivoice-brpt-v15", "k2-fsa/OmniVoice")
CODEC = "eustlb/higgs-audio-v2-tokenizer"
WHISPER = "openai/whisper-large-v3-turbo"


def byte_size(value):
    value=max(0,int(value))
    return f"{value/1_000_000_000:.2f} GB" if value>=1_000_000_000 else f"{value/1_000_000:.1f} MB"


def _windows_display_names():
    """Read adapter names without PowerShell, WMI or third-party modules."""
    if os.name != 'nt':return []
    try:
        import ctypes
        class DISPLAY_DEVICE(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('DeviceName',ctypes.c_wchar*32),('DeviceString',ctypes.c_wchar*128),
                      ('StateFlags',ctypes.c_ulong),('DeviceID',ctypes.c_wchar*128),('DeviceKey',ctypes.c_wchar*128)]
        result=[];index=0
        while True:
            item=DISPLAY_DEVICE();item.cb=ctypes.sizeof(item)
            if not ctypes.windll.user32.EnumDisplayDevicesW(None,index,ctypes.byref(item),0):break
            if item.DeviceString:result.append(item.DeviceString.strip())
            index+=1
        return list(dict.fromkeys(result))
    except (AttributeError,OSError,ValueError):return []


def amd_gpu_supported(name):
    normalized=' '.join(str(name).upper().replace('AMD RADEON','').split())
    return next((model for model in AMD_SUPPORTED_GPUS if model in normalized),None)


def rx7600_system_issue():
    if os.name!='nt':return 'O perfil RX 7600 requer Windows 11 25H2.'
    version=sys.getwindowsversion()
    if version.major<10 or version.build<26200:
        return f'ROCm 10.0 requer Windows 11 25H2 (build 26200 ou mais recente); este Windows é build {version.build}.'
    return ''


def detect_processing():
    cpu=platform.processor() or "Processador x64"
    if os.name=='nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                cpu=winreg.QueryValueEx(key,'ProcessorNameString')[0].strip()
        except OSError:pass
    candidates=[shutil.which('nvidia-smi'),Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'/'nvidia-smi.exe']
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():continue
        try:
            result=subprocess.run([str(candidate),'--query-gpu=name,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8,**process_options())
            if result.returncode==0 and result.stdout.strip():
                return {'variant':'cu128','cpu':cpu,'gpu':result.stdout.strip().replace('\n','; ')+' (memória em MiB)'}
        except (OSError,subprocess.SubprocessError):pass
    displays=_windows_display_names()
    legacy=next((name for name in displays if any(model in name.upper() for model in DIRECTML_RX500)),None)
    if legacy and sys.getwindowsversion().major>=10:
        return {'variant':'directml','cpu':cpu,'gpu':legacy+' (DirectML / DirectX 12; teste real obrigatório)'}
    rx7600=next((name for name in displays if 'RX 7600' in name.upper()),None)
    if rx7600:
        issue=rx7600_system_issue()
        if issue:return {'variant':'cpu','cpu':cpu,'gpu':rx7600+' — '+issue+' Usar CPU até atualizar.'}
        return {'variant':'rocm100-gfx1102','cpu':cpu,'gpu':rx7600+' (ROCm 10.0 / gfx1102 compatível; requer Adrenalin 26.8.1)'}
    amd=next(((name,amd_gpu_supported(name)) for name in [*displays,cpu] if amd_gpu_supported(name)),None)
    if amd and sys.getwindowsversion().major >= 10 and sys.getwindowsversion().build >= 22000:
        return {'variant':'rocm721','cpu':cpu,'gpu':amd[0]+' (ROCm 7.2.1 compatível: '+amd[1]+')'}
    amd_name=next((name for name in displays if 'AMD' in name.upper() or 'RADEON' in name.upper()),None)
    detail=(amd_name+' — fora da lista oficial do ROCm Windows; usar CPU.' if amd_name else
            'NVIDIA/AMD ROCm utilizável não detectada; usar CPU (AMD ou Intel).')
    return {'variant':'cpu','cpu':cpu,'gpu':detail}


class TransferParser:
    """Decode complete progress lines, including subprocess chunks split mid-number."""
    def __init__(self, callback):
        self.callback=callback;self.pending='';self.name='Pacote'

    def feed(self,text,final=False):
        self.pending+=text.replace('\r','\n')
        lines=self.pending.split('\n');self.pending=lines.pop()
        if final:lines.append(self.pending);self.pending=''
        for line in lines:
            line=line.strip()
            if line.startswith('Downloading '):self.name=line[12:]
            if line.startswith(('Using cached ','Requirement already satisfied:')):
                self.callback({'kind':'cache','name':line.replace('Using cached ','Já disponível no cache: ',1).replace('Requirement already satisfied:','Já instalado:',1)})
            if line.startswith('Installing collected packages:'):
                self.callback({'kind':'activity','name':'Downloads disponíveis; instalando os pacotes no disco…'})
            match=re.fullmatch(r'Progress (\d+) of (\d+)',line)
            if match:self.callback({'name':self.name,'current':int(match[1]),'total':int(match[2])})
            elif line.startswith('DUBLASKIZON_TRANSFER '):
                try:self.callback(json.loads(line.split(' ',1)[1]))
                except (ValueError,TypeError):pass
            else:
                size=re.search(r'(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\s+(kB|MB|GB)',line)
                if size:
                    factor={'kB':1000,'MB':1000000,'GB':1000000000}[size[3]]
                    self.callback({'name':self.name,'current':int(float(size[1])*factor),'total':int(float(size[2])*factor)})


MODEL_DOWNLOAD_WORKER = r'''
import sys,json,time
from huggingface_hub import snapshot_download,hf_hub_download
from tqdm.auto import tqdm
repos=json.loads(sys.argv[1]);only_sizes=sys.argv[2]=='1'
plans=[]
for repo in repos:
    print('Consultando tamanhos e cache: '+repo,flush=True)
    files=snapshot_download(repo,endpoint='https://huggingface.co',max_workers=2,dry_run=True)
    full=sum(f.file_size or 0 for f in files);missing=sum(f.file_size or 0 for f in files if f.will_download)
    unknown=sum(f.file_size is None for f in files)
    print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name=repo,kind='size',total=full,missing=missing,unknown=unknown)),flush=True)
    plans.append((repo,files))
full=sum(f.file_size or 0 for _,files in plans for f in files)
missing=sum(f.file_size or 0 for _,files in plans for f in files if f.will_download)
unknown=sum(f.file_size is None for _,files in plans for f in files)
print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name='TOTAL DOS MODELOS',kind='size',total=full,missing=missing,unknown=unknown)),flush=True)
if not only_sizes:
    class Bar(tqdm):
        def __init__(self,*args,**kwargs):
            self.last_report=0
            kwargs['disable']=False
            super().__init__(*args,**kwargs)
        def display(self,*args,**kwargs):
            now=time.monotonic()
            if now-getattr(self,'last_report',0)<.2:return
            self.last_report=now
            print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name=getattr(self,'desc','Arquivo'),current=int(getattr(self,'n',0)),total=int(getattr(self,'total',0) or 0))),flush=True)
    for repo,files in plans:
        for info in files:
            print('Arquivo: '+repo+'/'+info.filename,flush=True)
            if not info.will_download:
                print('DUBLASKIZON_TRANSFER '+json.dumps(dict(kind='cache',name='Já no cache: '+info.filename)),flush=True)
            hf_hub_download(repo,info.filename,revision=info.commit_hash,endpoint='https://huggingface.co',tqdm_class=Bar)
            if info.will_download and info.file_size is not None:
                print('DUBLASKIZON_TRANSFER '+json.dumps(dict(name=info.filename,current=info.file_size,total=info.file_size)),flush=True)
        # Refresh the normal snapshot reference through the official cache API.
        print(snapshot_download(repo,endpoint='https://huggingface.co',max_workers=2),flush=True)
'''


def runtime_root():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Dublaskizon" / "runtime"


def managed_python():
    try:
        root = runtime_root().resolve()
        data = json.loads((root / "active.json").read_text(encoding="utf-8"))
        path = (root / data["python"]).resolve()
        if path.is_relative_to(root) and path.is_file():
            return path
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def installed_python313():
    """Locate CPython's existing installation before invoking its maintenance installer."""
    candidates=[runtime_root()/f"python-{PYTHON_VERSION}"/"python.exe",
                Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"Programs"/"Python"/"Python313"/"python.exe",
                Path(os.environ.get("ProgramFiles","C:/Program Files"))/"Python313"/"python.exe"]
    if os.name=="nt":
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive,r"Software\Python\PythonCore\3.13\InstallPath",0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
                    candidates.append(Path(winreg.QueryValue(key,None))/"python.exe")
            except OSError:pass
    return list(dict.fromkeys(path for path in candidates if path.is_file()))


def installed_python312():
    candidates=[runtime_root()/f"python-{AMD_PYTHON_VERSION}"/"python.exe",
                Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"Programs"/"Python"/"Python312"/"python.exe",
                Path(os.environ.get("ProgramFiles","C:/Program Files"))/"Python312"/"python.exe"]
    if os.name=='nt':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive,r"Software\Python\PythonCore\3.12\InstallPath",0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
                    candidates.append(Path(winreg.QueryValue(key,None))/"python.exe")
            except OSError:pass
    return list(dict.fromkeys(path for path in candidates if path.is_file()))


def legacy_model_path(model):
    if model not in MODELS:
        return None
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OmniVoice"
    for cache in (base / "hf_cache", base / "hf" / "_cache"):
        path = cache / model
        if all((path / name).is_file() and (path / name).stat().st_size > 0
               for name in ("config.json", "tokenizer.json", "model.safetensors")):
            return path
    return None


def cached_snapshot(model):
    """Only consider the referenced main snapshot, never an arbitrary partial directory."""
    roots = [Path(os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))) / "hub"]
    for key in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE"):
        if os.environ.get(key):
            roots.insert(0, Path(os.environ[key]))
    for root in roots:
        repository = root / ("models--" + model.replace("/", "--"))
        try:
            revision = (repository / "refs" / "main").read_text().strip()
            if not revision or any(c not in "0123456789abcdef" for c in revision):
                continue
            snapshot = repository / "snapshots" / revision
            config = snapshot / "config.json"
            if config.is_file() and config.stat().st_size and any(p.stat().st_size for p in snapshot.glob("*.safetensors") if p.is_file()):
                return snapshot
        except OSError:
            continue
    return None


def inference_command():
    python = managed_python()
    if not python:
        return None
    # Embed the adapter so frozen builds do not need a loose .py file next to the EXE.
    mapping = {m: str(p) for m in MODELS if not cached_snapshot(m) and (p := legacy_model_path(m))}
    code = ("import os,sys,runpy;os.environ['HF_ENDPOINT']='https://huggingface.co';"
            f"mapping={mapping!r};"
            "i=sys.argv.index('--model')+1 if '--model' in sys.argv else 0;"
            "sys.argv[i]=mapping.get(sys.argv[i],sys.argv[i]) if i else sys.argv[i];"
            "runpy.run_module('omnivoice.cli.infer',run_name='__main__')")
    return [str(python), "-u", "-c", code]


def process_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def official_environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("PIP_") or key in ("PYTHONPATH", "PYTHONHOME"):
            env.pop(key, None)
    env.update(PIP_CONFIG_FILE=os.devnull, PIP_INDEX_URL="https://pypi.org/simple",
               PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
               HF_ENDPOINT="https://huggingface.co")
    return env


class Cancelled(Exception):
    pass


class SetupJob:
    def __init__(self, emit, cancel=None, progress=None, ffmpeg_dir=None, transfer=None):
        self.emit = emit
        self.transfer = transfer or (lambda event:None)
        self.ffmpeg_dir = Path(ffmpeg_dir) if ffmpeg_dir else None
        self.progress = progress or (lambda value: None)
        self.steps = 0
        self.total_steps = 9
        self.cancel = cancel or threading.Event()
        root = runtime_root() / "logs"
        root.mkdir(parents=True, exist_ok=True)
        self.log = root / (time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() % 1000000}.log")

    def write(self, text):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(text.rstrip() + "\n")
        self.emit(text.rstrip())

    def checkpoint(self):
        if self.cancel.is_set():
            raise Cancelled("Operação cancelada. A instalação anterior continua selecionada.")

    def run(self, args, timeout=1800, ok_codes=(0,)):
        self.checkpoint()
        parser=TransferParser(self.transfer)
        self.transfer({'kind':'activity','name':'Executando / instalando; aguardando dados de download'})
        environment = official_environment()
        if self.ffmpeg_dir and self.ffmpeg_dir.is_dir():
            environment['PATH'] = str(self.ffmpeg_dir) + os.pathsep + environment.get('PATH', '')
            environment['FFMPEG_BINARY'] = str(self.ffmpeg_dir / ('ffmpeg.exe' if os.name=='nt' else 'ffmpeg'))
        self.write("> " + subprocess.list2cmdline([str(a) for a in args[:5]]))
        with tempfile.TemporaryDirectory(prefix="dublaskizon-setup-") as temporary:
            path = Path(temporary) / "process.log"
            # Independent handles: seeking the reader must not move the child's write offset.
            with path.open("wb") as writer:
                if os.name == "nt" and getattr(sys, "frozen", False):
                    import ctypes
                    ctypes.windll.kernel32.SetDllDirectoryW(None)
                try:
                    proc = subprocess.Popen([str(a) for a in args], stdout=writer, stderr=subprocess.STDOUT,
                                            env=environment, **process_options())
                finally:
                    if os.name == "nt" and getattr(sys, "frozen", False):
                        ctypes.windll.kernel32.SetDllDirectoryW(getattr(sys, "_MEIPASS", None))
            output = path.open("rb")
            start, offset = time.monotonic(), 0
            try:
                while True:
                    self.checkpoint()
                    if time.monotonic() - start > timeout:
                        raise TimeoutError("Tempo limite excedido; consulte o relatório e tente novamente.")
                    output.seek(offset)
                    raw = output.read()
                    offset += len(raw)
                    if raw:
                        parser.feed(raw.decode('utf-8',errors='replace'))
                        self.write(raw.decode("utf-8", errors="replace"))
                    code = proc.poll()
                    if code is not None:
                        output.seek(offset)
                        tail = output.read()
                        if tail:
                            parser.feed(tail.decode('utf-8',errors='replace'))
                            self.write(tail.decode("utf-8", errors="replace"))
                        parser.feed('',final=True)
                        if code not in ok_codes:
                            raise RuntimeError(f"Comando falhou (código {code}). Veja a mensagem acima; nenhum ambiente incompleto foi ativado.")
                        self.steps += 1
                        self.progress(min(99.0, self.steps / max(1,self.total_steps) * 100))
                        return
                    self.cancel.wait(.15)
            finally:
                try:
                    if proc.poll() is None:
                        if os.name == "nt":
                            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           timeout=15, **process_options())
                        if proc.poll() is None:
                            proc.kill()
                        proc.wait(timeout=15)
                finally:
                    output.close()

    def download_python(self, amd=False):
        version,url,expected=((AMD_PYTHON_VERSION,AMD_PYTHON_URL,AMD_PYTHON_SHA256) if amd else
                              (PYTHON_VERSION,PYTHON_URL,PYTHON_SHA256))
        target = runtime_root() / f"python-{version}-amd64.exe"
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            self.transfer({'kind':'cache','name':'Instalador Python já baixado e verificado'})
            return target
        part = target.with_suffix(".part")
        for attempt in range(3):
            self.checkpoint()
            try:
                self.write(f"Baixando Python oficial (tentativa {attempt + 1}/3)...")
                digest, size, last = hashlib.sha256(), 0, -1
                with urllib.request.urlopen(url, timeout=30) as response, part.open("wb") as output:
                    if not response.url.startswith("https://www.python.org/"):
                        raise RuntimeError("Redirecionamento inesperado no download do Python.")
                    total = int(response.headers.get("Content-Length", "0"))
                    self.transfer({'name':'Python oficial','current':0,'total':total})
                    while block := response.read(256 * 1024):
                        self.checkpoint()
                        output.write(block)
                        digest.update(block)
                        size += len(block)
                        percent = int(size * 100 / total) if total else size // 1048576
                        if percent != last:
                            self.transfer({'name':'Python oficial','current':size,'total':total})
                            self.write(f"Python: {size / 1048576:.1f} MB" + (f" / {total / 1048576:.1f} MB" if total else ""))
                            self.progress(min(10.0,percent / 10))
                            last = percent
                if digest.hexdigest() != expected:
                    raise RuntimeError("SHA-256 diferente do publicado em python.org. Instalador rejeitado.")
                part.replace(target)
                return target
            except Cancelled:
                raise
            except Exception:
                if attempt == 2:
                    raise
                self.cancel.wait(2)

    def install(self, variant):
        if os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64"):
            raise RuntimeError("Este instalador automático requer Windows x64.")
        if variant not in ("cpu", "cu128", "rocm721", "rocm100-gfx1102"):
            raise ValueError("Selecione CPU, NVIDIA CUDA ou um modo AMD ROCm disponível.")
        root = runtime_root()
        root.mkdir(parents=True, exist_ok=True)
        # OS lock is released even if the application crashes.
        import msvcrt
        with (root / "setup.lock").open("a+b") as lock:
            lock.write(b"0")
            lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Outra instalação do Dublaskizon está em andamento.") from exc
            try:
                self._install_locked(variant)
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

    def ensure_base_python(self):
        root=runtime_root()
        check="import sys,struct,venv,ensurepip;assert sys.version_info[:2]==(3,13);assert struct.calcsize('P')==8;print(sys.executable);print(sys.version)"
        def find():
            for candidate in installed_python313():
                self.checkpoint()
                try:self.run([candidate,"-c",check],timeout=30)
                except (OSError,RuntimeError,TimeoutError) as exc:
                    self.write(f"Python encontrado mas não utilizável: {candidate}: {exc}")
                    continue
                self.write(f"Python base validado: {candidate}. Dependências serão instaladas somente no novo ambiente isolado.")
                return candidate
        python=find()
        if python:return python
        if installed_python313():
            raise RuntimeError("O Python 3.13 encontrado não passou na verificação de execução, 64 bits ou venv. Consulte as mensagens acima e repare essa instalação pelo instalador oficial.")
        base = root / f"python-{PYTHON_VERSION}"
        installer = self.download_python()
        self.write("Instalando Python para este usuário, sem alterar PATH nem remover outro Python...")
        self.run([installer, "/quiet", "InstallAllUsers=0", f"TargetDir={base}",
                  "PrependPath=0", "Include_launcher=0", "Include_test=0", "Include_pip=1",
                  "AssociateFiles=0", "Shortcuts=0", "/log", root / "python-install.log"], ok_codes=(0, 3010))
        python=find()
        if not python:
            raise RuntimeError("O instalador terminou, mas nenhum Python 3.13 de 64 bits utilizável foi encontrado. Consulte "+str(root/"python-install.log")+". Nenhum ambiente foi ativado; não é necessário remover o Python anterior.")
        return python

    def ensure_amd_python(self):
        root=runtime_root();check="import sys,struct,venv,ensurepip;assert sys.version_info[:2]==(3,12);assert struct.calcsize('P')==8;print(sys.executable);print(sys.version)"
        def find():
            for candidate in installed_python312():
                self.checkpoint()
                try:self.run([candidate,'-c',check],timeout=30)
                except (OSError,RuntimeError,TimeoutError):continue
                self.write(f"Python 3.12 base validado para AMD ROCm: {candidate}");return candidate
        python=find()
        if python:return python
        base=root/f"python-{AMD_PYTHON_VERSION}";installer=self.download_python(amd=True)
        self.write('Instalando Python 3.12 oficial e isolado, exigido pelo PyTorch AMD ROCm para Windows...')
        self.run([installer,'/quiet','InstallAllUsers=0',f'TargetDir={base}','PrependPath=0','Include_launcher=0',
                  'Include_test=0','Include_pip=1','AssociateFiles=0','Shortcuts=0','/log',root/'python-amd-install.log'],ok_codes=(0,3010))
        python=find()
        if not python:raise RuntimeError('O Python 3.12 x64 exigido pelo AMD ROCm não pôde ser executado. Consulte '+str(root/'python-amd-install.log'))
        return python

    def _install_locked(self, variant):
        root = runtime_root()
        required=20 if variant.startswith('rocm') else 12
        if shutil.disk_usage(root).free < required * 1024**3:
            raise RuntimeError(f"Reserve ao menos {required} GB livres para Python/PyTorch e temporários; modelos precisam de espaço adicional.")
        python=self.ensure_amd_python() if variant.startswith('rocm') else self.ensure_base_python()
        # A failed update never modifies the previously active virtual environment.
        envdir = root / ("env-" + str(time.time_ns()))
        self.run([python, "-m", "venv", envdir])
        executable = envdir / "Scripts" / "python.exe"
        pip = [executable, "-m", "pip", "install", "--retries", "3", "--timeout", "60"]
        self.run([*pip, "--index-url", "https://pypi.org/simple", "--upgrade", "pip"])
        pip.extend(['--progress-bar','raw'])
        if variant=='rocm100-gfx1102':
            index='https://stable.repo.amd.com/rocm/whl-next/'
            preflight=("import urllib.request;index='https://stable.repo.amd.com/rocm/whl-next/';"
                       "checks={'rocm':'10.0.0','torch':'2.13.0%2Brocm10.0.0','torchvision':'0.28.0%2Brocm10.0.0','torchaudio':'2.11.0.2%2Brocm10.0.0'};"
                       "[(lambda data,name,version: (_ for _ in ()).throw(RuntimeError('Pacote AMD ausente: '+name+' '+version)) if version not in data else print('[OK] AMD',name,version))"
                       "(urllib.request.urlopen(index+name+'/',timeout=30).read().decode(),name,version) for name,version in checks.items()]")
            self.write('Conferindo no índice oficial AMD se todos os pacotes RX 7600 ainda estão publicados...')
            self.run([python,'-c',preflight],timeout=180)
            self.write('Instalando ROCm 10.0 e PyTorch oficiais para Radeon RX 7600 (gfx1102)...')
            self.run([*pip,'--index-url',index,'rocm[libraries,device-gfx1102]==10.0.0'],timeout=7200)
            self.run([*pip,'--index-url',index,'torch[device-gfx1102]==2.13.0+rocm10.0.0',
                      'torchvision[device-gfx1102]==0.28.0+rocm10.0.0','torchaudio==2.11.0.2+rocm10.0.0'],timeout=7200)
        elif variant=='rocm721':
            from f5_backend import AMD_BASE,AMD_SDK,AMD_TORCH
            self.write('Instalando SDK ROCm e PyTorch AMD oficiais para o OmniVoice em português...')
            self.run([*pip,'--no-cache-dir',*[AMD_BASE+name for name in AMD_SDK]],timeout=7200)
            self.run([*pip,'--no-cache-dir',*[AMD_BASE+name for name in AMD_TORCH]],timeout=7200)
        else:
            self.run([*pip, "--index-url", f"https://download.pytorch.org/whl/{variant}",
                      "torch==2.8.0", "torchaudio==2.8.0"], timeout=7200)
        constraints = envdir / "constraints.txt"
        constraints.write_text(("torch==2.13.0+rocm10.0.0\ntorchaudio==2.11.0.2+rocm10.0.0\n" if variant=='rocm100-gfx1102' else
                                "torch==2.9.1+rocm7.2.1\ntorchaudio==2.9.1+rocm7.2.1\n" if variant=='rocm721' else
                                "torch==2.8.0\ntorchaudio==2.8.0\n"), encoding="utf-8")
        self.run([*pip, "--index-url", "https://pypi.org/simple", "-c", constraints,
                  "omnivoice==0.2.1", "audioop-lts", "huggingface_hub>=1.32,<2"], timeout=7200)
        self.run([executable, "-m", "pip", "check"])
        self.run([executable, "-m", "omnivoice.cli.infer", "--help"], timeout=180)
        self.run([executable, "-c", "import torch,torchaudio;print('Torch:',torch.__version__,'CUDA:',torch.cuda.is_available());"
                  + ("assert torch.cuda.is_available(), 'GPU AMD ROCm indisponível. Confira Windows 11 e o driver AMD atualizado.';"
                     "assert torch.version.hip;name=torch.cuda.get_device_name(0);assert '7600' in name, 'A GPU ativa não é a RX 7600: '+name;print('AMD:',name,'HIP:',torch.version.hip);print(torch.zeros(1,device='cuda')+1)" if variant=='rocm100-gfx1102' else
                     "assert torch.cuda.is_available(), 'GPU AMD ROCm indisponível. Confira Windows 11, driver AMD 26.2.2 e a matriz oficial.';"
                     "assert torch.version.hip;print('AMD:',torch.cuda.get_device_name(0),'HIP:',torch.version.hip);print(torch.zeros(1,device='cuda')+1)" if variant=='rocm721' else
                     "assert torch.cuda.is_available(), 'Driver/GPU NVIDIA indisponível. Atualize o driver oficial ou selecione CPU.';"
                     "print(torch.zeros(1,device='cuda')+1)" if variant == "cu128" else "print(torch.zeros(1)+1)")], timeout=180)
        self.checkpoint()
        pending = root / "active.pending.json"
        pending.write_text(json.dumps({"python": executable.relative_to(root).as_posix(), "variant": variant,
                                      "created": time.strftime("%Y-%m-%d %H:%M:%S")}), encoding="utf-8")
        pending.replace(root / "active.json")
        self.write("[OK] Python e OmniVoice instalados e CLI validada. Próximo passo: baixar e testar os modelos.")

    def download_models(self, model, whisper=True, sizes_only=False):
        from f5_backend import MODEL, download
        if model == MODEL:return download(self, sizes_only)
        python = managed_python()
        if not python:
            raise RuntimeError("Instale primeiro o ambiente isolado pelo botão 1.")
        if model not in MODELS:
            raise ValueError("Modelo desconhecido.")
        repos = [model, CODEC] + ([WHISPER] if whisper else [])
        self.write("Consultando tamanhos e cache dos repositórios oficiais; modelos já presentes serão reutilizados.")
        self.total_steps = 1
        self.run([python, "-u", "-c", MODEL_DOWNLOAD_WORKER, json.dumps(repos), '1' if sizes_only else '0'], timeout=900 if sizes_only else 14400)
        self.write("[OK] Consulta concluída; nenhum modelo foi baixado." if sizes_only else "[OK] Downloads concluídos. Use TESTAR MODELO para verificar carregamento, memória e compatibilidade.")

    def test_model(self, model, whisper):
        from f5_backend import MODEL, test
        if model == MODEL:return test(self)
        python = managed_python()
        if not python:
            raise RuntimeError("Instale primeiro o ambiente isolado.")
        self.total_steps = 1
        # Offline: this test cannot silently download missing multi-GB dependencies.
        code = ("import os;os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';"
                "import sys,torch;from omnivoice import OmniVoice;"
                "device='cuda' if torch.cuda.is_available() else 'cpu';"
                "m=OmniVoice.from_pretrained(sys.argv[1],device_map=device,"
                "dtype=torch.float16 if device=='cuda' else torch.float32,load_asr=sys.argv[2]=='1');"
                "print('MODELO CARREGADO:',device,'; geração de fala ainda não testada')")
        source = model if cached_snapshot(model) else str(legacy_model_path(model) or model)
        self.run([python, "-u", "-c", code, source, "1" if whisper else "0"], timeout=900)
        try:data=json.loads((runtime_root()/'active.json').read_text(encoding='utf-8'))
        except (OSError,ValueError,TypeError):data={}
        if data.get('variant')=='rocm100-gfx1102':
            output=runtime_root()/'rx7600-teste-portugues.wav'
            if output.exists():output.unlink()
            self.write('Executando síntese portuguesa curta na RX 7600 para validar operadores, memória e gravação WAV...')
            command=inference_command()
            self.run([*command,'--model',source,'--text','Teste de voz em português.','--language','Portuguese',
                      '--instruct','Brazilian Portuguese voice','--duration','0.8','--num_step','2',
                      '--denoise','false','--postprocess_output','false','--output',output],timeout=900)
            if not output.is_file() or output.stat().st_size<1000:
                raise RuntimeError('A RX 7600 carregou o modelo, mas não produziu um WAV válido. Use CPU e envie o relatório.')
            self.write('[OK] RX 7600 validada com geração real em português: '+str(output))

    def diagnose(self, command, ffmpeg_dir, backend='OmniVoice'):
        self.write(f"Sistema: {platform.platform()} / {platform.machine()}\nAmbiente gerenciado: {managed_python() or 'não instalado'}")
        self.write(f"Livre no disco do instalador: {shutil.disk_usage(runtime_root()).free / 1024**3:.1f} GB")
        checks = []
        if command:
            self.write("Gerador selecionado: " + str(command[0]))
            checks.append((backend + " CLI", [*command, "--help"]))
        else:
            self.write("[FALTA] Gerador " + backend + " não encontrado.")
        python = managed_python()
        if backend == 'F5-TTS':
            from f5_backend import runtime
            python = runtime()[0]
        elif backend == 'F5-TTS PT-BR DirectML':
            from directml_backend import runtime
            python = runtime()[0]
        if python:
            checks.append(("PyTorch / GPU", [python, "-c", "import torch,torchaudio;print('PyTorch',torch.__version__,'CUDA disponível:',torch.cuda.is_available());print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"]))
        for name in ("ffmpeg", "ffprobe", "ffplay"):
            exe = (Path(ffmpeg_dir) / (name + ".exe")) if ffmpeg_dir else shutil.which(name)
            if exe and Path(exe).is_file():
                checks.append((name, [exe, "-version"]))
            else:
                self.write(f"[FALTA] {name}: use PREPARAR FERRAMENTAS.")
        self.total_steps = len(checks)
        failures = 0
        for name, args in checks:
            self.write("Verificando " + name)
            try:
                self.run(args, timeout=180)
                self.write("[OK] " + name)
            except Cancelled:
                raise
            except Exception as exc:
                failures += 1
                self.write(f"[FALHOU] {name}: {exc}")
                if name in ("OmniVoice CLI", "PyTorch / GPU"):
                    self.write("Se a mensagem mencionar DLL / WinError 126 ou 1114, confira o Visual C++ x64 oficial e o driver NVIDIA.\n"
                               "Visual C++: https://learn.microsoft.com/pt-br/cpp/windows/latest-supported-vc-redist")
        for model in (*MODELS, CODEC, WHISPER):
            path = cached_snapshot(model) or legacy_model_path(model)
            self.write(f"[{('ARQUIVOS ENCONTRADOS, não validados' if path else 'NÃO ENCONTRADO NO CACHE CONHECIDO')}] {model}: {path or 'use BAIXAR MODELOS'}")
        self.write(f"Diagnóstico concluído; {failures} comando(s) falharam. Cache existente não garante integridade. TESTAR MODELO verifica o carregamento.")


def show_linux_assistant(app):
    """Diagnóstico Linux sem expor os instaladores de Python/CUDA/ROCm do Windows."""
    import shutil
    import tkinter as tk
    from tkinter import ttk
    import webbrowser

    window = tk.Toplevel(app.root)
    app.dependency_window = window
    window.title("Verificação inicial — requisitos Linux")
    window.geometry("850x580")
    window.minsize(700, 480)
    theme = app.current_theme()
    window.configure(bg=theme.get("root", "#172033"))
    ttk.Label(window, text="DUBLASKIZON NO LINUX", font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(16, 5))
    ttk.Label(window, text=("Esta edição usa as dependências instaladas pela distribuição. "
        "Os instaladores de Python, CUDA e ROCm para Windows ficam desativados aqui."),
        wraplength=800, justify="left").pack(anchor="w", padx=18, pady=(0, 10))
    output = tk.Text(window, height=16, wrap="word", state="disabled", font=("Consolas", 10),
                     bg=theme.get("input", "#202838"), fg=theme.get("input_text", "#FFFFFF"))
    output.pack(fill="both", expand=True, padx=18, pady=8)
    status = tk.StringVar(value="Clique em VERIFICAR LINUX.")
    ttk.Label(window, textvariable=status).pack(anchor="w", padx=18)

    def write(lines):
        output.configure(state="normal"); output.delete("1.0", "end")
        output.insert("end", "\n".join(lines)); output.configure(state="disabled")
    def verify():
        import platform
        tools = ("python3", "ffmpeg", "ffprobe", "ffplay", "sox", "xdg-open")
        rows = [f"Sistema: {platform.platform()}", f"Arquitetura: {platform.machine()}", ""]
        missing = []
        for name in tools:
            path = shutil.which(name)
            rows.append(f"[{'OK' if path else 'FALTA'}] {name}: {path or 'não encontrado'}")
            if not path: missing.append(name)
        rows += ["", "Síntese de voz: configure OMNIVOICE_INFER ou instale o ambiente compatível com sua GPU/CPU."]
        if missing:
            rows.append("Instale os itens ausentes pelo gerenciador oficial da sua distribuição.")
            status.set("Há dependências ausentes: " + ", ".join(missing))
        else:
            status.set("Dependências básicas do aplicativo encontradas.")
        write(rows)
    def open_guide():
        guide = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "LEIA-ME-LINUX.md"
        if guide.exists(): subprocess.Popen(["xdg-open", str(guide)])
        else: webbrowser.open("https://docs.python.org/3/using/unix.html")
    def close():
        app.save_dependency_assistant_preference(not dont_show.get())
        app.dependency_window = None
        window.destroy()
    controls = ttk.Frame(window); controls.pack(fill="x", padx=18, pady=10)
    ttk.Button(controls, text="VERIFICAR LINUX", command=verify).pack(side="left", padx=3)
    ttk.Button(controls, text="ABRIR INSTRUÇÕES LINUX", command=open_guide).pack(side="left", padx=3)
    ttk.Button(controls, text="ROCm OFICIAL", command=lambda:webbrowser.open("https://rocm.docs.amd.com/projects/install-on-linux/en/latest/")).pack(side="left", padx=3)
    dont_show = tk.BooleanVar(value=not app.should_show_dependency_assistant())
    ttk.Checkbutton(controls, text="Não mostrar novamente", variable=dont_show).pack(side="left", padx=12)
    ttk.Button(controls, text="CONTINUAR", command=close).pack(side="right", padx=3)
    window.protocol("WM_DELETE_WINDOW", close)
    verify()


def show_assistant(app):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import webbrowser
    import batch_tab
    existing = getattr(app, "dependency_window", None)
    if existing is not None:
        try:
            existing.lift()
            return
        except tk.TclError:
            pass
    if os.name != "nt":
        return show_linux_assistant(app)
    window = tk.Toplevel(app.root)
    app.dependency_window = window
    window.title("Verificação inicial — requisitos do Dublaskizon")
    window.geometry(f"1050x{min(900,max(700,window.winfo_screenheight()-100))}")
    window.minsize(880, 700)
    window.transient(app.root)
    try:
        window.iconbitmap(str(Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "Dublaskizon.ico"))
    except tk.TclError:
        pass
    theme = app.current_theme()
    window.configure(bg=theme["root"])
    for key, value in (("text", "#FFFFFF"), ("input", "#202838"), ("input_text", "#FFFFFF")):
        theme.setdefault(key, value)
    tk.Label(window, text="PREPARAR O DUBLASKIZON", font=("Segoe UI", 17, "bold"),
             bg=theme["root"], fg=theme["text"]).pack(anchor="w", padx=18, pady=(14, 4))
    ttk.Label(window, text="1. Instale o ambiente  →  2. Baixe os modelos  →  3. Teste o carregamento", font=("Segoe UI", 11)).pack(anchor="w", padx=18)
    info = ttk.LabelFrame(window, text="O que é necessário", padding=10)
    info.pack(fill="x", padx=18, pady=10)
    explanation = ttk.Label(info, justify="left", wraplength=900, text="• Python + OmniVoice + PyTorch: geram as vozes; o cache sozinho não substitui esses programas.\n"
              "• Modelo de voz + tokenizer de áudio: necessários para síntese. Whisper: transcrição automática da referência.\n"
              "• FFmpeg / FFprobe / FFplay: conversão e reprodução. VoiceStudio é opcional.\n"
              "• O modo ‘omnivoice-subprocess’ da imagem pertence ao VoiceStudio; não é outro modelo para baixar.")
    explanation.pack(anchor="w", fill="x")
    info.bind("<Configure>", lambda event: explanation.configure(wraplength=max(300, event.width - 24)))
    settings = ttk.Frame(window)
    settings.pack(fill="x", padx=18)
    variants = ("Automático — NVIDIA, AMD ROCm ou DirectML; senão CPU", "NVIDIA — CUDA 12.8 / driver compatível",
                "AMD Radeon — ROCm 7.2.1 oficial (Windows 11)", "AMD RX 7600 — ROCm 10.0 oficial (Windows 11)",
                "AMD RX 500 / GPU DirectX 12 — DirectML experimental",
                "CPU — AMD Ryzen / Intel (mais lento)")
    variant = tk.StringVar(value=variants[0])
    ttk.Label(settings, text="Processamento:").grid(row=0, column=0, sticky="w")
    hardware = ttk.Combobox(settings, values=variants, textvariable=variant, state="readonly", width=47)
    hardware.grid(row=0, column=1, sticky="ew", padx=8, pady=3)
    import i18n
    model = tk.StringVar(value=MODELS[1] if i18n.CURRENT_LANGUAGE == 'ru' else MODELS[0])
    ttk.Label(settings, text="Modelo de voz:").grid(row=1, column=0, sticky="w")
    from f5_backend import MODEL as F5_MODEL
    from directml_backend import MODEL as DML_MODEL
    choice = ttk.Combobox(settings, values=(*MODELS, F5_MODEL, DML_MODEL), textvariable=model, state="readonly", width=47)
    choice.grid(row=1, column=1, sticky="ew", padx=8, pady=3)
    ttk.Label(settings,text='Português prioritário: OmniVoice ou F5-TTS PT-BR DirectML. O perfil DirectML tenta acelerar GPUs DirectX 12 sem ROCm, como RX 560/570/580/590, exige teste real e troca para CPU se a síntese falhar.',wraplength=900).grid(row=3,column=0,columnspan=2,sticky='w')
    settings.columnconfigure(1, weight=1)
    whisper = tk.BooleanVar(value=True)
    whisper_check = ttk.Checkbutton(settings, text="Incluir Whisper (recomendado para clonar sem transcrição)", variable=whisper)
    whisper_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
    def model_changed(_event=None):
        if model.get() in (F5_MODEL,DML_MODEL):
            whisper.set(True)
            whisper_check.configure(state='disabled')
        else:
            whisper_check.configure(state='normal')
    choice.bind('<<ComboboxSelected>>', model_changed)
    detected=tk.StringVar(value='Identificando CPU e GPU deste computador…')
    ttk.Label(window,textvariable=detected,wraplength=960).pack(anchor='w',padx=18)
    ttk.Label(window,text='AMD ROCm no Windows: somente Windows 11 e hardware listado oficialmente. RX 7600 usa ROCm 10.0/gfx1102; acelera OmniVoice BR-PT em português.',wraplength=960).pack(anchor='w',padx=18)
    size_hint=tk.StringVar(value='Estimativa: CPU 1–3 GB; NVIDIA 4–7 GB; AMD ROCm pode ultrapassar 10 GB. Reserve 20 GB para AMD, mais os modelos.')
    ttk.Label(window,textvariable=size_hint,wraplength=960).pack(anchor='w',padx=18,pady=4)
    controls = ttk.Frame(window)
    controls.pack(fill="x", padx=18, pady=8)
    events, stop = queue.Queue(), threading.Event()
    state = {"busy": False, "log": None, "closed": False, 'hardware':None, 'last_transfer':'Nenhum download informado'}
    def probe():
        try:events.put(('hardware',detect_processing()))
        except Exception:events.put(('hardware',{'variant':'cpu','cpu':'CPU AMD/Intel','gpu':'Detecção indisponível; modo automático usará CPU.'}))
    threading.Thread(target=probe,daemon=True).start()
    actions = []
    status = tk.StringVar(value="Pronto para verificar. Nenhuma instalação foi iniciada.")
    ttk.Label(window, textvariable=status).pack(anchor="w", padx=18)
    progress = ttk.Progressbar(window, mode="determinate", maximum=100, value=0)
    progress.pack(fill="x", padx=18, pady=(4, 8))
    transfer_text=tk.StringVar(value='Download: aguardando')
    ttk.Label(window,textvariable=transfer_text,wraplength=960).pack(anchor='w',padx=18)
    transfer_bar=ttk.Progressbar(window,mode='determinate',maximum=100,value=0)
    transfer_bar.pack(fill='x',padx=18,pady=(3,8))
    logframe = ttk.Frame(window)
    logframe.pack(fill="both", expand=True, padx=18)
    output = tk.Text(logframe, height=12, wrap="word", state="disabled", font=("Consolas", 9),
                     bg=theme["input"], fg=theme["input_text"])
    scroll = ttk.Scrollbar(logframe, command=output.yview)
    output.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    output.pack(fill="both", expand=True)

    def write(text):
        output.configure(state="normal")
        output.insert("end", text + "\n")
        if int(output.index("end-1c").split(".")[0]) > 1500:
            output.delete("1.0", "300.0")
        output.see("end")
        output.configure(state="disabled")

    def start(kind):
        if state["busy"]:
            return
        selected, include = model.get(), whisper.get()
        is_f5 = selected == F5_MODEL
        is_dml = selected == DML_MODEL
        if is_f5 or is_dml:include=True
        if variant.get()==variants[0] and state['hardware'] is None:
            status.set('Aguarde a identificação do processador e da placa de vídeo.');return
        mode = (state['hardware']['variant'] if variant.get()==variants[0] else
                'cu128' if variant.get()==variants[1] else 'rocm721' if variant.get()==variants[2] else
                'rocm100-gfx1102' if variant.get()==variants[3] else 'directml' if variant.get()==variants[4] else 'cpu')
        if is_dml and mode!='directml':
            status.set('F5-TTS PT-BR DirectML requer o processamento AMD RX 500 / GPU DirectX 12 — DirectML.');return
        if mode=='directml' and not is_dml:
            status.set('O perfil DirectML usa o modelo F5-TTS PT-BR DirectML. Selecione esse modelo.');return
        if mode=='rocm100-gfx1102' and 'RX 7600' not in state['hardware'].get('gpu','').upper():
            status.set('RX 7600 não detectada. Este perfil baixa kernels gfx1102 específicos e não será instalado em outra placa.');return
        if mode=='rocm100-gfx1102' and rx7600_system_issue():
            status.set(rx7600_system_issue());return
        if mode=='rocm100-gfx1102' and is_f5:
            status.set('Na RX 7600, o modo ROCm 10.0 está validado pelo instalador para OmniVoice BR-PT. Use CPU para F5-TTS Russian.');return
        backend_label='F5-TTS PT-BR + Microsoft DirectML' if is_dml else ('F5-TTS' if is_f5 else 'OmniVoice')
        if kind == "install" and not messagebox.askyesno("Instalar ambiente isolado", ("Baixar Python de python.org, PyTorch e " + backend_label + " do PyPI?\n\n")
                + f"Destino: {runtime_root()}\nModo: {mode}\nDownloads de vários GB. Seu Python atual será preservado.\n"
                "O ambiente novo só será ativado após os testes. Esta ação não baixa os modelos.", parent=window):
            return
        if kind == "models" and not messagebox.askyesno("Baixar modelos", f"Baixar {selected}, " + ("Vocos e " if is_f5 or is_dml else "tokenizer e ") + ("Whisper" if include else "sem Whisper") + " diretamente dos repositórios no Hugging Face?\n\nPode ocupar vários GB; o cache padrão será reutilizado.", parent=window):
            return
        command = None
        if kind == 'check':
            try:command = batch_tab.find_voice_command(selected)
            except RuntimeError as exc:write(str(exc))
        ffmpeg = batch_tab.find_ffmpeg_directory()
        state["busy"] = True
        stop.clear()
        for button in actions:
            button.configure(state="disabled")
        hardware.configure(state="disabled")
        choice.configure(state="disabled")
        whisper_check.configure(state="disabled")
        cancel_button.configure(state="normal")
        progress.configure(mode="determinate",value=0)
        transfer_bar.configure(value=0);state['last_transfer']='Nenhum download informado';transfer_text.set('Consultando / preparando; ainda sem transferência informada')
        status.set("Trabalhando… acompanhe as etapas abaixo. A interface continua disponível.")
        def worker():
            try:
                job = SetupJob(lambda text: events.put(("text", text)), stop, lambda value: events.put(("progress", value)), ffmpeg_dir=ffmpeg,transfer=lambda event:events.put(('transfer',event)))
                events.put(("log", job.log))
                operations={
                    'check':lambda:(job.diagnose(command,ffmpeg,'F5-TTS PT-BR DirectML' if is_dml else 'F5-TTS')
                                    if is_dml or is_f5 else job.diagnose(command,ffmpeg)),
                    'install':lambda:__import__('directml_backend').install(job,mode) if is_dml else __import__('f5_backend').install(job,mode) if is_f5 else job.install(mode),
                    'models':lambda:__import__('directml_backend').download(job) if is_dml else __import__('f5_backend').download(job) if is_f5 else job.download_models(selected,include),
                    'sizes':lambda:__import__('directml_backend').download(job,True) if is_dml else __import__('f5_backend').download(job,True) if is_f5 else job.download_models(selected,include,sizes_only=True),
                    'test':lambda:__import__('directml_backend').test(job,getattr(app,'project_root',None)) if is_dml else __import__('f5_backend').test(job) if is_f5 else job.test_model(selected,include)}
                operations[kind]()
                events.put(("done", (True,"Etapa concluída. Confira os resultados e eventuais itens ausentes no relatório.")))
            except Exception as exc:
                events.put(("text", f"[INTERROMPIDO] {exc}"))
                events.put(("done", (False,"Etapa interrompida. Consulte o relatório; você pode corrigir a causa e tentar novamente.")))
        threading.Thread(target=worker, daemon=True).start()

    for index, (label, kind) in enumerate((("VERIFICAR", "check"), ("1. INSTALAR / REPARAR", "install"),
                                         ("2. BAIXAR MODELOS", "models"), ("3. TESTAR MODELO", "test"))):
        button = ttk.Button(controls, text=label, command=lambda k=kind: start(k))
        button.grid(row=0, column=index, padx=3, sticky="ew")
        controls.columnconfigure(index, weight=1)
        actions.append(button)
    cancel_button = ttk.Button(controls, text="CANCELAR", command=stop.set, state="disabled")
    cancel_button.grid(row=1, column=3, sticky="ew", padx=3, pady=5)
    def prepare_tools():
        app.prepare_shared_audio_tools()
        write("Preparação de FFmpeg / FFprobe / FFplay / SoX iniciada pela ferramenta existente.\n"
              "Fontes: Gyan (build indicado por ffmpeg.org) e projeto SoX no SourceForge.")
        def follow_tools():
            if state["closed"]:
                return
            converter = getattr(app, "converter_app", None)
            if converter is not None and not state["busy"]:
                status.set(converter.download_status_var.get())
            if converter is not None and getattr(converter, "dependencies_running", False):
                window.after(500, follow_tools)
        follow_tools()
    tools_button = ttk.Button(controls, text="PREPARAR FERRAMENTAS DE ÁUDIO", command=prepare_tools)
    tools_button.grid(row=1, column=0, columnspan=2, sticky="ew", padx=3, pady=5)
    actions.append(tools_button)
    size_button=ttk.Button(controls,text='CONSULTAR TAMANHO DOS MODELOS (sem baixar)',command=lambda:start('sizes'))
    size_button.grid(row=2,column=0,columnspan=4,sticky='ew',padx=3,pady=3);actions.append(size_button)
    def open_log():
        if state["log"] and Path(state["log"]).exists():
            os.startfile(str(state["log"]))
    ttk.Button(controls, text="ABRIR RELATÓRIO", command=open_log).grid(row=1, column=2, sticky="ew", padx=3)
    links = ttk.Frame(window)
    links.pack(fill="x", padx=18, pady=7)
    for label, url in (("Python oficial", "https://www.python.org/downloads/release/python-31315/"),
                       ("OmniVoice oficial", "https://github.com/k2-fsa/OmniVoice"),
                       ("F5-TTS Russian", "https://huggingface.co/hotstone228/F5-TTS-Russian"),
                       ("F5-TTS PT-BR", "https://huggingface.co/firstpixel/F5-TTS-pt-br"),
                       ("Microsoft DirectML", "https://github.com/microsoft/DirectML"),
                       ("VoiceStudio (opcional)", "https://github.com/debpalash/VoiceStudio/releases"),
                       ("Driver NVIDIA", "https://www.nvidia.com/Download/index.aspx"),
                       ('AMD ROCm / GPUs compatíveis','https://rocm.docs.amd.com/en/latest/install/rocm.html')):
        ttk.Button(links, text=label, command=lambda u=url: webbrowser.open(u)).pack(side="left", padx=3)
    footer = ttk.Frame(window)
    footer.pack(fill="x", padx=18, pady=(0, 12))
    dont_show = tk.BooleanVar(value=not app.should_show_dependency_assistant())
    ttk.Checkbutton(footer, text="Não mostrar novamente ao iniciar", variable=dont_show).pack(side="left")
    def close():
        if state["busy"]:
            messagebox.showinfo("Operação em andamento", "Use CANCELAR e aguarde a finalização antes de fechar.", parent=window)
            return
        state["closed"] = True
        app.save_dependency_assistant_preference(not dont_show.get())
        app.dependency_window = None
        window.destroy()
    ttk.Button(footer, text="CONTINUAR", command=close).pack(side="right")
    window.protocol("WM_DELETE_WINDOW", close)
    def poll():
        if state["closed"] or not window.winfo_exists():
            stop.set()
            return
        for _ in range(100):
            try:
                kind, payload = events.get_nowait()
            except queue.Empty:
                break
            if kind == "text":
                write(payload)
            elif kind=='hardware':
                state['hardware']=payload
                auto={'cu128':'NVIDIA CUDA','rocm721':'AMD ROCm 7.2.1','rocm100-gfx1102':'AMD ROCm 10.0 / RX 7600','directml':'Microsoft DirectML / RX 500','cpu':'CPU'}[payload['variant']]
                detected.set('CPU: '+payload['cpu']+' | GPU: '+payload['gpu']+' | Automático: '+auto)
                if payload['variant']=='directml' and variant.get()==variants[0]:
                    model.set(DML_MODEL)
                    model_changed()
                    status.set('RX 500 detectada: F5-TTS PT-BR DirectML selecionado automaticamente. Execute os passos 1, 2 e 3.')
            elif kind=='transfer':
                if payload.get('kind')=='size':
                    label=payload['name']+': total '+byte_size(payload['total'])+'; falta baixar '+byte_size(payload['missing'])+'; cache '+byte_size(payload['total']-payload['missing'])
                    if payload.get('unknown'):label+=f" (+ {payload['unknown']} arquivo(s) com tamanho desconhecido)"
                    write(label)
                    if payload['name']=='TOTAL DOS MODELOS':size_hint.set(label+' (dependências à parte; pode haver temporários e retomadas).')
                elif payload.get('kind')=='activity':
                    transfer_text.set(payload['name']+' | Último: '+state['last_transfer'][:100])
                elif payload.get('kind')=='cache':
                    transfer_bar.configure(value=100);state['last_transfer']=payload['name'][:150]+' — sem novo download';transfer_text.set(state['last_transfer'])
                else:
                    current=payload.get('current',0);total=payload.get('total',0)
                    transfer_bar.configure(value=min(100,current*100/total) if total else 0)
                    transfer_text.set(payload.get('name','Arquivo')[:95]+' — '+byte_size(current)+(' / '+byte_size(total)+f' ({min(100,current*100/total):.1f}%)' if total else ' / total não informado'))
                    state['last_transfer']=transfer_text.get()
            elif kind == "progress":
                progress.configure(value=max(float(progress.cget("value")),float(payload)))
            elif kind == "log":
                state["log"] = payload
                write("Relatório: " + str(payload))
            elif kind == "done":
                state["busy"] = False
                success,message=payload
                if success:progress.configure(value=100)
                status.set(message)
                transfer_text.set(('Concluído — ' if success else 'Interrompido — ')+state['last_transfer'])
                cancel_button.configure(state="disabled")
                for button in actions:
                    button.configure(state="normal")
                hardware.configure(state="readonly")
                choice.configure(state="readonly")
                whisper_check.configure(state="normal")
                model_changed()
        window.after(100, poll)
    window.bind("<Destroy>", lambda event: stop.set() if event.widget is window else None, add="+")
    app.ensure_control_contrast(window)
    poll()
