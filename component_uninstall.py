"""Selectable removal inventory. Never scans or removes project audio or API keys."""
from pathlib import Path
import os,json,urllib.request


def unique_paths(paths):
    result=[]
    for path in sorted({Path(os.path.abspath(p)) for p in paths},key=lambda p:len(p.parts)):
        if not any(path==parent or path.is_relative_to(parent) for parent in result):result.append(path)
    return result


def catalog(app_dir=None,project_root=None,include_ollama=True,include_system=True):
    from dependency_setup import runtime_root,huggingface_cache_roots,path_size,MANAGED_MODEL_REPOS
    base=runtime_root();items=[]
    def add(label,paths,shared=False):
        paths=unique_paths([Path(p) for p in paths if Path(p).exists() or Path(p).is_symlink()])
        if paths:items.append(dict(label=label,paths=paths,size=sum(path_size(p) for p in paths),kind='files',shared=shared))
    def matches(patterns):return [p for pattern in patterns for p in base.glob(pattern)]
    add('Motor OmniVoice — ambientes e apontador ativo',matches(['env-*','active.json']))
    add('Motor F5-TTS Russian',matches(['f5-env-*','f5-active.json']))
    add('Motor F5-TTS PT-BR / DirectML',matches(['directml-env-*','directml-active.json']))
    add('Motor Qwen3-TTS (modelos separados abaixo)',[p for p in (base/'qwen').glob('*') if p.name!='models'])
    add('Motor Fish Speech e modelos próprios',matches(['fish-env-*','fish-source-*','fish-models','fish-active.json','fish-model.txt']))
    add('Seed-VC — reações / emoções nativas',[base/'native-emotions'])
    add('Transcrição / tradução — Faster-Whisper, Whisper, Argos e bibliotecas',matches(['translation-[0-9]*','translation-active.json']))
    add('Python isolado compartilhado — motores dependentes precisarão ser preparados novamente',matches(['python-*']),True)
    add('Caches de referências e relatórios dos motores',matches(['voice-references-*','fish-reference-transcripts','logs']))
    from shared_audio_tools import storage_dir
    add('FFmpeg / FFprobe / FFplay / SoX — sistema compartilhado',[storage_dir()],True)
    for root in {Path(p) for p in (app_dir,project_root) if p}:add('FFmpeg / FFprobe / FFplay / SoX — '+str(root),[root/'ferramentas_audio'])
    from audacity_setup import managed_directory
    aud=managed_directory();bridge=aud.parent.parent/'audacity_openvino'
    add('Audacity portátil gerenciado (inclui os plugins nesta cópia)',[aud])
    plugin_files=[p for pattern in ('openvino*.dll','torch*.dll','tbb*.dll','libiomp*.dll','c10.dll','asmjit.dll','fbgemm.dll','uv.dll','whisper.dll','OpenCL.dll') for p in aud.glob(pattern)]
    add('Somente OpenVINO — plugins, modelos e cópias de automação',[aud/'modules/mod-openvino.dll',aud/'openvino-models',bridge]+plugin_files)
    add('Instaladores / downloads de Audacity e OpenVINO',[aud.parent/'downloads'])
    known=set(MANAGED_MODEL_REPOS)
    for module in ('f5_backend','directml_backend','qwen_backend'):
        known.update(__import__(module).FILES)
    caches=list(huggingface_cache_roots())+[base/'qwen/models']
    for root in dict.fromkeys(caches):
        for folder in sorted(root.glob('models--*')):
            repo=folder.name[len('models--'):].replace('--','/')
            if repo in known or repo.startswith(('Systran/faster-whisper','openai/whisper','facebook/nllb','facebook/m2m','Helsinki-NLP/opus-mt')):
                add('Modelo Hugging Face — '+repo,[folder],True)
    for model in sorted((Path.home()/'.cache/whisper').glob('*.pt')):add('Whisper — '+model.stem,[model],True)
    argos_roots=[Path(os.environ.get('ARGOS_PACKAGES_DIR',Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'argos-translate/packages'))]
    for root in argos_roots:
        for package in sorted(root.glob('*')):
            if package.is_dir():add('Argos Translate — '+package.name,[package],True)
    if include_ollama:
        names={}
        models=Path(os.environ.get('OLLAMA_MODELS',str(Path.home()/'.ollama/models')))
        for manifest in (models/'manifests').glob('*/*/*/*'):
            if not manifest.is_file():continue
            try:
                data=json.loads(manifest.read_text(encoding='utf-8'));parts=manifest.relative_to(models/'manifests').parts
                name=(('' if parts[1]=='library' else parts[1]+'/')+parts[2]+':'+parts[3])
                names[name]=sum(layer.get('size',0) for layer in data.get('layers',[]))+data.get('config',{}).get('size',0)
            except (OSError,ValueError,IndexError):continue
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=2) as response:data=json.load(response)
            names.update({m['name']:m.get('size',0) for m in data.get('models',[])})
        except Exception:pass
        for name,size in sorted(names.items()):items.append(dict(label='IA local Ollama — '+name,paths=[],size=size,kind='ollama',model=name,shared=True))
        ollama=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Programs/Ollama/unins000.exe'
        if ollama.is_file():items.append(dict(label='Aplicativo Ollama — abre seu desinstalador oficial',paths=[ollama],size=0,kind='native',shared=True))
    if include_system and os.name=='nt':
        import winreg,re
        from audacity_setup import installations
        roots=installations()
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\Uninstall',0,winreg.KEY_READ|view) as parent:
                        for index in range(winreg.QueryInfoKey(parent)[0]):
                            try:
                                with winreg.OpenKey(parent,winreg.EnumKey(parent,index)) as key:
                                    name=winreg.QueryValueEx(key,'DisplayName')[0]
                                    if name!='Audacity' and not name.startswith(('Audacity ','OpenVINO AI Plugins for Audacity')):continue
                                    command=winreg.QueryValueEx(key,'UninstallString')[0]
                                    match=re.match(r'^"([^"\n]+\.exe)"|^([^"\n]+?\.exe)(?:\s|$)',command,re.I)
                                    if not match:continue
                                    exe=Path(match.group(1) or match.group(2))
                                    if not exe.is_file() or not exe.name.lower().startswith('unins'):continue
                                    if not any(exe.resolve().is_relative_to(root.resolve()) for root in roots):continue
                                    if any(exe in item['paths'] for item in items):continue
                                    items.append(dict(label=name+' — instalação Windows / desinstalador oficial',paths=[exe],size=0,kind='native',shared=True))
                            except OSError:continue
                except OSError:continue
    return items


def remove_selected(items,emit=lambda text:None):
    from dependency_setup import remove_managed_downloads
    files=unique_paths([p for item in items if item['kind']=='files' for p in item['paths']])
    removed,failures=remove_managed_downloads(files);notices=[]
    for item in items:
        try:
            if item['kind']=='ollama':
                from audio_translation import ensure_ollama
                ensure_ollama(emit)
                request=urllib.request.Request('http://127.0.0.1:11434/api/delete',data=json.dumps({'model':item['model']}).encode(),headers={'Content-Type':'application/json'},method='DELETE')
                with urllib.request.urlopen(request,timeout=120) as response:response.read()
                notices.append('Modelo Ollama removido: '+item['model']+' (blobs compartilhados podem continuar em uso por outros modelos).')
            elif item['kind']=='native':
                os.startfile(str(item['paths'][0]))
                notices.append('Desinstalador oficial aberto: '+item['label']+'. Conclua a remoção na janela própria.')
        except Exception as exc:failures.append(item['label']+': '+str(exc))
    return removed,failures,notices


def choose(parent,items,theme=None):
    import tkinter as tk
    from tkinter import ttk,messagebox
    from dependency_setup import byte_size
    window=tk.Toplevel(parent);window.title('Desinstalar tudo / por componentes');window.transient(parent)
    window.geometry('920x650');window.minsize(650,440)
    theme=theme or {};bg=theme.get('surface',theme.get('root','#202B3B'));fg=theme.get('text','#F8FAFC')
    window.configure(bg=bg)
    style=ttk.Style(window)
    for name in ('TFrame','TLabel','TCheckbutton'):
        style.configure('Uninstall.'+name,background=bg,foreground=fg)
    style.map('Uninstall.TCheckbutton',background=[('active',bg)],foreground=[('active',fg)])
    style.configure('Uninstall.TButton',background='#0891B2',foreground=fg,padding=7)
    style.map('Uninstall.TButton',background=[('active','#0E7490')],foreground=[('active',fg)])

    ttk.Label(window,style='Uninstall.TLabel',text='SELECIONE O QUE DESEJA DESINSTALAR',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=14,pady=10)
    ttk.Label(window,style='Uninstall.TLabel',text='Projetos, áudios, TXT, chaves e configurações pessoais serão preservados.\nItens marcados como compartilhados também podem ser usados por outros programas. Tamanhos são estimados.',wraplength=850).pack(fill='x',padx=14)
    tools=ttk.Frame(window,style='Uninstall.TFrame');tools.pack(fill='x',padx=14,pady=7)
    variables=[tk.BooleanVar(window,value=False) for item in items]
    total=tk.StringVar(window)
    def update(*args):
        selected=[item for item,var in zip(items,variables) if var.get()]
        # Sizes are precomputed; do not rescan multi-GB runtimes on every click.
        size=sum(item['size'] for item in selected)
        total.set(f'{len(selected)} componentes selecionados | até {byte_size(size)} (itens sobrepostos / compartilhados podem ocupar menos)')
    def mark(value):
        for var in variables:var.set(value)
        update()
    ttk.Button(tools,style='Uninstall.TButton',text='MARCAR TODOS',command=lambda:mark(True)).pack(side='left')
    ttk.Button(tools,style='Uninstall.TButton',text='DESMARCAR TODOS',command=lambda:mark(False)).pack(side='left',padx=5)
    area=ttk.Frame(window,style='Uninstall.TFrame');area.pack(fill='both',expand=True,padx=14)
    canvas=tk.Canvas(area,highlightthickness=0,bg=bg);scroll=ttk.Scrollbar(area,orient='vertical',command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
    body=ttk.Frame(canvas,style='Uninstall.TFrame');item_id=canvas.create_window(0,0,window=body,anchor='nw')
    body.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item_id,width=event.width))
    for item,var in zip(items,variables):
        row=ttk.Frame(body,style='Uninstall.TFrame');row.pack(fill='x',pady=3)
        check=ttk.Checkbutton(row,style='Uninstall.TCheckbutton',text=item['label']+('  [COMPARTILHADO]' if item.get('shared') else ''),variable=var,command=update)
        check.pack(anchor='w')
        ttk.Label(row,style='Uninstall.TLabel',text=byte_size(item['size'])+' | '+(' | '.join(str(p) for p in item['paths']) if item['paths'] else 'Ollama local / remoção pela API'),wraplength=820).pack(anchor='w',padx=23)
        for widget in (row,check,*row.winfo_children()):widget.bind('<MouseWheel>',lambda event:canvas.yview_scroll(-3 if event.delta>0 else 3,'units'))
    ttk.Label(window,style='Uninstall.TLabel',textvariable=total,wraplength=850).pack(fill='x',padx=14,pady=8)
    result=None
    def accept():
        nonlocal result
        selected=[item for item,var in zip(items,variables) if var.get()]
        if not selected:messagebox.showinfo('Desinstalar','Marque os componentes que deseja remover.',parent=window);return
        labels='\n'.join('• '+item['label'] for item in selected)
        if not messagebox.askyesno('Confirmar remoção dos selecionados',labels+'\n\nRemover somente estes componentes? Modelos e bibliotecas compartilhados podem afetar outros programas.',parent=window):return
        result=selected;window.destroy()
    bottom=ttk.Frame(window,style='Uninstall.TFrame');bottom.pack(fill='x',padx=14,pady=10)
    tk.Button(bottom,text='DESINSTALAR SELECIONADOS',command=accept,bg='#C00000',fg='white',pady=7).pack(side='left')
    ttk.Button(bottom,style='Uninstall.TButton',text='CANCELAR',command=window.destroy).pack(side='right')
    window.protocol('WM_DELETE_WINDOW',window.destroy);update();window.grab_set();window.wait_window()
    return result
