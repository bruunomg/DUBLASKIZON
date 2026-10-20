"""Official, compatible Audacity/OpenVINO preparation for Windows."""
from pathlib import Path
import os, urllib.request, zipfile, subprocess, time, hashlib, shutil

AUDACITY_URL='https://github.com/audacity/audacity/releases/download/Audacity-3.7.3/audacity-win-3.7.3-64bit.zip'
PLUGIN_URL='https://github.com/intel/openvino-plugins-ai-audacity/releases/download/v3.7.1-R4.2/audacity-win-v3.7.1-R4.2-64bit-OpenVINO-AI-Plugins.exe'
AUDACITY_SHA256='1d4c91d0bc1b5376f4c8768d48a6e79ab9dcb4600c1162053f61556becb45ce5'
COMPONENTS=r'music_sep,noise_sup,noise_sup\deepfilternet2,noise_sup\deepfilternet3,noise_sup\denseunet'

def managed_directory():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'DUBLASKIZON'/'tools'/'Audacity-3.7.3'

def installations():
    paths=[managed_directory()]
    for name in ('ProgramFiles','ProgramFiles(x86)','LOCALAPPDATA'):
        value=os.environ.get(name)
        if value:paths.append(Path(value)/'Audacity')
    return [p for p in paths if (p/'Audacity.exe').is_file()]

def missing(directory, plugins=True):
    root=Path(directory);names=['Audacity.exe']
    if plugins:
        names+=['modules/mod-openvino.dll','modules/mod-script-pipe.dll']
        names+=['openvino-models/'+name+suffix for name in ('htdemucs_v4','noise-suppression-denseunet-ll-0001') for suffix in ('.xml','.bin')]
        names+=['openvino-models/deepfilternet3']
    return [name for name in names if not (root/name).exists() or ((root/name).is_file() and (root/name).stat().st_size==0)]

def diagnose(job,plugins=True):
    for root in installations():
        absent=missing(root,plugins)
        job.write('Audacity: '+str(root)+(' — pronto' if not absent else ' — faltam: '+', '.join(absent)))
        if not absent:return root
    job.write('Audacity/OpenVINO: preparação necessária.');return None

def download(job,url,target,expected):
    def valid(path):
        return path.is_file() and path.stat().st_size==expected and (url!=AUDACITY_URL or hashlib.sha256(path.read_bytes()).hexdigest()==AUDACITY_SHA256)
    if valid(target):return target
    part=target.with_suffix(target.suffix+'.part');target.parent.mkdir(parents=True,exist_ok=True)
    job.write('Baixando fonte oficial: '+url)
    req=urllib.request.Request(url,headers={'User-Agent':'Dublaskizon-requisitos'})
    with urllib.request.urlopen(req,timeout=60) as response,part.open('wb') as stream:
        current=0
        while True:
            job.checkpoint();data=response.read(1024*512)
            if not data:break
            stream.write(data);current+=len(data)
            job.transfer({'name':target.name,'current':current,'total':expected})
    if not valid(part):raise RuntimeError('Download incompleto ou checksum divergente: '+target.name)
    os.replace(part,target);return target

def run_plugin_installer(job,installer,directory):
    # The official Inno installer requires elevation. The Windows prompt remains user-controlled.
    import ctypes
    from ctypes import wintypes as w
    class Info(ctypes.Structure):
        _fields_=[('cbSize',w.DWORD),('fMask',w.ULONG),('hwnd',w.HWND),('lpVerb',w.LPCWSTR),('lpFile',w.LPCWSTR),('lpParameters',w.LPCWSTR),('lpDirectory',w.LPCWSTR),('nShow',ctypes.c_int),('hInstApp',w.HINSTANCE),('lpIDList',ctypes.c_void_p),('lpClass',w.LPCWSTR),('hkeyClass',w.HKEY),('dwHotKey',w.DWORD),('hIcon',w.HANDLE),('hProcess',w.HANDLE)]
    args=['/SILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',f'/DIR={directory}',f'/COMPONENTS={COMPONENTS}',f'/LOG={directory / "openvino-install.log"}']
    info=Info();info.cbSize=ctypes.sizeof(info);info.fMask=0x40;info.lpVerb='runas';info.lpFile=str(installer);info.lpParameters=subprocess.list2cmdline(args);info.nShow=1
    shell=ctypes.WinDLL('shell32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    shell.ShellExecuteExW.argtypes=[ctypes.POINTER(Info)];shell.ShellExecuteExW.restype=w.BOOL
    kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];kernel.CloseHandle.argtypes=[w.HANDLE]
    job.checkpoint();job.write('Instalando OpenVINO e modelos Music Separation / Noise Suppression. Confirme a solicitação do Windows, se aparecer.')
    if not shell.ShellExecuteExW(ctypes.byref(info)):raise ctypes.WinError(ctypes.get_last_error())
    try:
        cancellation_reported=False
        while kernel.WaitForSingleObject(info.hProcess,500)==258:
            # Do not kill an elevated installer midway through writing its files.
            if job.cancel.is_set() and not cancellation_reported:
                job.write('Cancelamento solicitado: use Cancelar na janela do instalador oficial; aguardando finalização segura.');cancellation_reported=True
        code=w.DWORD();kernel.GetExitCodeProcess(info.hProcess,ctypes.byref(code))
        if code.value not in (0,3010):raise RuntimeError(f'Instalador OpenVINO terminou com código {code.value}. Consulte openvino-install.log.')
    finally:kernel.CloseHandle(info.hProcess)
    job.checkpoint()

def prepare(job,audacity=True,plugins=True):
    if not audacity and not plugins:return
    from audacity_openvino import audacity_running
    ready=diagnose(job,plugins)
    if ready:return ready
    if audacity_running():raise RuntimeError('Salve e feche o Audacity antes de preparar os componentes. Nenhum projeto foi alterado.')
    # A separate known-compatible pair prevents downgrading the user's Audacity.
    root=managed_directory();root.mkdir(parents=True,exist_ok=True)
    cache=root.parent/'downloads'
    if not (root/'Audacity.exe').is_file():
        archive=download(job,AUDACITY_URL,cache/'audacity-3.7.3.zip',26398933)
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                job.checkpoint()
                relative=Path(member.filename)
                if relative.parts and relative.parts[0]=='audacity-win-3.7.3-64bit':relative=Path(*relative.parts[1:])
                destination=(root/relative).resolve()
                if not destination.is_relative_to(root.resolve()):raise ValueError('Caminho inválido no pacote Audacity.')
                if member.is_dir():destination.mkdir(parents=True,exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    with bundle.open(member) as src,destination.open('wb') as dst:shutil.copyfileobj(src,dst)
    if not (root/'Audacity.exe').is_file():raise RuntimeError('Audacity.exe não encontrado após extrair o pacote oficial.')
    if plugins and missing(root,True):
        installer=download(job,PLUGIN_URL,cache/'openvino-v3.7.1-R4.2.exe',76495696)
        run_plugin_installer(job,installer,root)
    absent=missing(root,plugins)
    if absent:raise RuntimeError('Preparação incompleta: '+', '.join(absent))
    job.write('Audacity'+(' + OpenVINO Music Separation e Noise Suppression' if plugins else '')+' prontos: '+str(root))
    return root
