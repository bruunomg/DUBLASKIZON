"""Selection-time availability and download-size prompts without blocking the UI."""
import fnmatch,json,os,queue,shutil,threading,urllib.request
from pathlib import Path

def repositories(model):
    import f5_backend,directml_backend,qwen_backend
    for backend in (f5_backend,directml_backend,qwen_backend):
        if model==backend.MODEL:return backend.FILES
    from dependency_setup import CODEC,WHISPER
    return {repo:['*'] for repo in (model,CODEC,WHISPER)}

def missing(batch,model):
    try:runtime=bool(batch_module().find_voice_command(model))
    except (RuntimeError,OSError,ValueError):runtime=False
    import qwen_backend
    roots=batch_module().model_cache_roots()
    if model==qwen_backend.MODEL:roots=[qwen_backend.root()/'models']+roots
    absent=[]
    for repo in repositories(model):
        found=False
        for root in roots:
            snapshots=root/('models--'+repo.replace('/','--'))/'snapshots'
            if snapshots.exists() and any(p.is_file() for pattern in ('*.safetensors','*.bin','*.pt') for p in snapshots.rglob(pattern)):
                found=True;break
        if not found:absent.append(repo)
    return (not runtime),absent

def batch_module():
    import batch_tab
    return batch_tab

def estimate(model,only_repos=None):
    total=0;unknown=[]
    for repo,patterns in repositories(model).items():
        if only_repos is not None and repo not in only_repos:continue
        try:
            request=urllib.request.Request('https://huggingface.co/api/models/'+repo+'?blobs=true',headers={'User-Agent':'Dublaskizon-requisitos'})
            with urllib.request.urlopen(request,timeout=8) as response:data=json.load(response)
            files=[f for f in data.get('siblings',[]) if any(fnmatch.fnmatch(f['rfilename'],pattern) for pattern in patterns)]
            if not files or any('size' not in f for f in files):unknown.append(repo)
            total+=sum(f.get('size',0) for f in files)
        except Exception:unknown.append(repo)
    return total,unknown

def free_space(path):
    path=Path(path).expanduser().resolve()
    while not path.exists():path=path.parent
    return shutil.disk_usage(path).free

def prompt(batch):
    if getattr(batch,'running',False):return
    model=batch.selected_model_id()
    serial=getattr(batch,'_model_prompt_serial',0)+1;batch._model_prompt_serial=serial
    absent_runtime,absent_models=missing(batch,model)
    if not absent_runtime and not absent_models:return
    batch.append_log('Consultando tamanho e espaço para '+model+'…','info')
    messages=queue.Queue()
    def worker():messages.put(estimate(model,absent_models))
    threading.Thread(target=worker,daemon=True).start()
    def poll():
        if getattr(batch,'_model_prompt_serial',None)!=serial or batch.selected_model_id()!=model:return
        try:total,unknown=messages.get_nowait()
        except queue.Empty:batch.root.after(100,poll);return
        from tkinter import messagebox
        from dependency_setup import byte_size,runtime_root
        import qwen_backend
        cache=qwen_backend.root()/'models' if model==qwen_backend.MODEL else batch_module().model_cache_roots()[0]
        available=free_space(cache);runtime_free=free_space(runtime_root())
        reserve=8*1024**3 if absent_runtime else 0
        same_disk=Path(cache).resolve().anchor.casefold()==runtime_root().resolve().anchor.casefold()
        required=int(total*1.2)+(reserve if same_disk else 0)
        enough=available>=required and (same_disk or runtime_free>=reserve)
        text=f'Modelo: {model}\n'+('Ambiente da ferramenta ausente.\n' if absent_runtime else '')
        text+='Modelos ausentes: '+(', '.join(absent_models) or 'nenhum')+'\n'
        text+='Tamanho dos modelos: '+(byte_size(total) if not unknown else 'consulta incompleta; parte conhecida: '+byte_size(total))+'\n'
        text+=f'Cache: {cache}\nEspaço livre: {byte_size(available)}\nAmbiente: {runtime_root()}\nLivre no ambiente: {byte_size(runtime_free)}\n'
        text+='O cache existente será reaproveitado; tamanho acima considera os repositórios ausentes.\n'
        text+='Reserva estimada do ambiente: '+byte_size(reserve)+'; margem de 20% para modelos.\n'
        if not enough:
            messagebox.showwarning('Espaço insuficiente',text+'\nLibere espaço antes de preparar.',parent=batch.root);return
        text+='\n'+('Há espaço para a estimativa consultada.' if not unknown else 'O tamanho total não pôde ser confirmado; confira o relatório dos requisitos.')+'\nBaixar / instalar agora?'
        if messagebox.askyesno('Ferramenta / modelo não preparado',text,parent=batch.root):
            callback=batch.project_actions.get('prepare_model')
            if callback:callback(model)
            else:messagebox.showinfo('Requisitos','Abra REQUISITOS para preparar este modelo.',parent=batch.root)
    batch.root.after(100,poll)
