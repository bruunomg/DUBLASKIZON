"""Troca de áudio sem recodificar imagem; backup e reversão por faixas WAV."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
try:
    from .video_converter_tab import VIDEO_EXTENSIONS, probe_video, hidden_kwargs
    from .video_preview import VideoPreview
    from .audio_player import AudioPlayerManager
    from .duration_converter_tab import executable_path
    from .ui_theme import apply_button_style, apply_button_style_to_tree
except ImportError:
    from video_converter_tab import VIDEO_EXTENSIONS, probe_video, hidden_kwargs
    from video_preview import VideoPreview
    from audio_player import AudioPlayerManager
    from duration_converter_tab import executable_path
    from ui_theme import apply_button_style, apply_button_style_to_tree

AUDIO_EXTENSIONS={'.wav','.wave','.mp3','.m4a','.aac','.flac','.ogg','.opus','.wma','.aif','.aiff'}
VIDEO_CONTAINERS={'.mp4','.mov','.m4v','.mkv','.avi','.webm'}

def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

def backup_key(video):
    return hashlib.sha256(os.path.normcase(str(Path(video).resolve())).encode('utf-8')).hexdigest()[:24]

def backup_paths(root,video):
    key=backup_key(video);folder=Path(root)/key[0]/key[1]/key
    return folder/(Path(video).stem+'.wav'),folder/'manifest.json'

def audio_streams(ffprobe,path):
    result=subprocess.run([str(ffprobe),'-v','error','-select_streams','a','-show_streams','-of','json',str(path)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,**hidden_kwargs())
    if result.returncode:raise RuntimeError(result.stderr[-1200:])
    return json.loads(result.stdout).get('streams',[])

def check_backup(manifest,video):
    data=json.loads(manifest.read_text(encoding='utf-8'))
    if os.path.normcase(data['path'])!=os.path.normcase(str(Path(video).resolve())):raise RuntimeError('Backup de outro vídeo.')
    for track in data['tracks']:
        path=(manifest.parent/track['file']).resolve()
        if not path.is_relative_to(manifest.parent.resolve()) or not path.is_file() or file_hash(path)!=track['sha256']:raise RuntimeError('WAV de backup ausente ou alterado; operação cancelada.')
    return data

def ensure_backup(root,video,ffmpeg,ffprobe):
    video=Path(video).resolve();wav,manifest=backup_paths(root,video)
    if manifest.exists():check_backup(manifest,video);return wav
    legacy=Path(root)/backup_key(video);binary=legacy/'original.bin';old_manifest=legacy/'manifest.json'
    source=video
    if binary.exists():
        if not old_manifest.exists():raise RuntimeError('Backup BIN sem manifesto. Não é seguro extrair o original automaticamente.')
        old=json.loads(old_manifest.read_text(encoding='utf-8'))
        if os.path.normcase(old['path'])!=os.path.normcase(str(video)) or file_hash(binary)!=old['sha256']:raise RuntimeError('Backup BIN antigo inválido.')
        source=binary
    streams=audio_streams(ffprobe,source)
    manifest.parent.mkdir(parents=True,exist_ok=True);tracks=[];temporaries=[]
    try:
        for index,stream in enumerate(streams):
            target=wav if index==0 else manifest.parent/f'faixa_{index+1:03}'/(video.stem+'.wav')
            target.parent.mkdir(parents=True,exist_ok=True)
            fd,name=tempfile.mkstemp(prefix='.extrair-',suffix='.wav',dir=target.parent);os.close(fd);temp=Path(name);temporaries.append(temp)
            result=subprocess.run([str(ffmpeg),'-y','-nostdin','-v','error','-i',str(source),'-map',f'0:a:{index}','-vn','-c:a','pcm_s16le','-rf64','auto',str(temp)],capture_output=True,**hidden_kwargs())
            if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-1200:])
            if not audio_streams(ffprobe,temp):raise RuntimeError('A extração não produziu um WAV válido.')
            temp.replace(target)
            tracks.append({'file':target.relative_to(manifest.parent).as_posix(),'sha256':file_hash(target),'tags':stream.get('tags',{})})
        metadata={'version':2,'path':str(video),'name':video.name,'tracks':tracks,'no_audio':not streams}
        temp_meta=manifest.with_suffix('.tmp');temp_meta.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8');temp_meta.replace(manifest)
        check_backup(manifest,video)
        # Migra o backup antigo somente depois que todos os WAVs foram verificados.
        if source==binary:
            binary.unlink()
            old_manifest.write_text(json.dumps({'migrated_to':str(manifest)},ensure_ascii=False),encoding='utf-8')
        return wav
    finally:
        for temp in temporaries:temp.unlink(missing_ok=True)

def restore_backup(root,video,ffmpeg,ffprobe):
    video=Path(video).resolve();wav,manifest=backup_paths(root,video)
    if not manifest.exists():
        legacy=Path(root)/backup_key(video)/'original.bin'
        if not legacy.exists():raise RuntimeError('Nenhum backup para este vídeo. Selecione a mesma pasta usada ao aplicar.')
        ensure_backup(root,video,ffmpeg,ffprobe)
    data=check_backup(manifest,video)
    fd,name=tempfile.mkstemp(prefix='.reverter-',suffix=video.suffix,dir=video.parent);os.close(fd);temporary=Path(name)
    try:
        command=[str(ffmpeg),'-y','-nostdin','-v','error','-i',str(video)]
        for track in data['tracks']:command+=['-i',str(manifest.parent/track['file'])]
        command+=['-map','0','-map','-0:a']
        for index,track in enumerate(data['tracks']):command+=['-map',f'{index+1}:a:0']
        codec={'.mkv':'flac','.avi':'pcm_s16le','.webm':'libopus','.mov':'pcm_s16le'}.get(video.suffix.lower(),'aac')
        command+=['-map_metadata','0','-c','copy']
        if data['tracks']:command+=['-c:a',codec]
        if codec in {'aac','libopus'} and data['tracks']:command+=['-b:a','192k']
        for index,track in enumerate(data['tracks']):
            for key in ('language','title'):
                if key in track['tags']:command+= [f'-metadata:s:a:{index}',f"{key}={track['tags'][key]}"]
        command.append(str(temporary))
        result=subprocess.run(command,capture_output=True,**hidden_kwargs())
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-1200:])
        probe_video(ffprobe,temporary)
        if len(audio_streams(ffprobe,temporary))!=len(data['tracks']):raise RuntimeError('Quantidade de faixas restauradas não confere.')
        os.replace(temporary,video)
    finally:temporary.unlink(missing_ok=True)

def match_pairs(audios,videos):
    """Mesmo nome, ignorando extensão/caixa; duplicatas nunca são adivinhadas."""
    a_map={};v_map={}
    for path in audios:a_map.setdefault(path.stem.casefold(),[]).append(path)
    for path in videos:v_map.setdefault(path.stem.casefold(),[]).append(path)
    pairs=[];issues=[]
    for key,targets in v_map.items():
        sources=a_map.get(key,[])
        if len(targets)!=1 or len(sources)>1:issues.append(f'Nome ambíguo: {targets[0].stem}. Carregue um par por vez.');continue
        if not sources:issues.append(f'Sem áudio correspondente: {targets[0].name}');continue
        pairs.append((targets[0],sources[0]))
    for key,sources in a_map.items():
        if key not in v_map:issues.append(f'Sem vídeo correspondente: {sources[0].name}')
    return pairs,issues

def replacement_command(ffmpeg,video,audio,target,duration):
    extension=video.suffix.lower()
    if extension not in VIDEO_CONTAINERS:raise ValueError('Para trocar áudio, use MP4, MOV, M4V, MKV, AVI ou WebM.')
    codec={'.mkv':'flac','.avi':'pcm_s16le','.webm':'libopus'}.get(extension,'aac')
    command=[str(ffmpeg),'-y','-nostdin','-hide_banner','-loglevel','error','-i',str(video),'-i',str(audio),
             '-map','0','-map','-0:a','-map','1:a:0','-map_metadata','0','-c','copy','-c:a',codec]
    if codec in {'aac','libopus'}:command+=['-b:a','192k']
    if duration>0:command+=['-af',f'apad,atrim=duration={duration:.6f}']
    return command+[str(target)]

class VideoAudioSwapApp:
    def __init__(self,root,project_root,project_actions=None):
        self.root=root;self.project_root=Path(project_root);self.project_actions=project_actions or {};self.theme={}
        self.original_audios=[];self.audios=[];self.files=[];self.previews=[];self.running=False;self.process=None;self.events=queue.Queue();self.cancel_event=threading.Event()
        self.backup_var=tk.StringVar(value=str(self.project_root/'BACKUP TROCAR AUDIO VIDEO'))
        self.status=tk.StringVar(value='Arraste áudios à esquerda e vídeos à direita. Os pares usam o mesmo nome sem a extensão.')
        self.audio_player=AudioPlayerManager(root,self.project_root,status_callback=self.status.set)
        self.progress=tk.DoubleVar(value=0);self.build_ui();self.root.after(100,self.poll)
    def button(self,parent,text,command,role='secondary'):
        widget=tk.Button(parent,text=text,command=command,relief='flat',padx=8,pady=6,cursor='hand2')
        widget.pack(side='left',padx=3,pady=3);apply_button_style(widget,self.theme,role);return widget
    def build_ui(self):
        ttk.Label(self.root,text='TROCAR AUDIO DO VÍDEO',font=('Segoe UI',16,'bold')).pack(anchor='w',padx=16,pady=10)
        ttk.Label(self.root,text='Exemplo: cena01.wav ↔ cena01.mp4. A imagem do vídeo não é recodificada.\nAplicar substitui o arquivo de vídeo, após extrair as faixas originais em WAV. Reverter recoloca essas faixas no vídeo.',wraplength=1000).pack(anchor='w',padx=16)
        panels=ttk.PanedWindow(self.root,orient='horizontal');panels.pack(fill='both',expand=True,padx=16,pady=8)
        self.lists={}
        for kind,label in [('audio','ÁUDIOS DUBLADOS — arraste aqui'),('video','VÍDEOS ORIGINAIS — arraste aqui'),('original','ÁUDIOS ORIGINAIS EXTRAÍDOS — WAV')]:
            panel=ttk.LabelFrame(panels,text=label,padding=6);panels.add(panel,weight=1)
            listing=tk.Listbox(panel,selectmode='extended',exportselection=False,height=12);listing.pack(fill='both',expand=True)
            self.lists[kind]=listing
            try:
                if kind!='original':listing.drop_target_register('DND_Files');listing.dnd_bind('<<Drop>>',lambda event,k=kind:self.drop(event,k))
            except (AttributeError,tk.TclError):pass
            row=ttk.Frame(panel);row.pack(fill='x')
            if kind!='original':
                self.button(row,'ADICIONAR',lambda k=kind:self.add_files(k),'primary')
                self.button(row,'PASTA',lambda k=kind:self.add_folder(k))
                self.button(row,'REMOVER',lambda k=kind:self.remove(k))
            else:
                self.button(row,'ATUALIZAR',self.refresh_originals)
            if kind in {'audio','original'}:
                self.button(row,'OUVIR',lambda k=kind:self.listen_audio(k),'teal')
                listing.bind('<Double-Button-1>',lambda event,k=kind:self.listen_audio(k))
        self.lists['video'].bind('<Double-Button-1>',lambda event:self.preview())
        row=ttk.Frame(self.root);row.pack(fill='x',padx=13)
        self.button(row,'ABRIR PASTA DE DESTINO DOS VÍDEOS DUBLADOS',self.open_destination)
        self.button(row,'EXTRAIR ÁUDIOS ORIGINAIS WAV',lambda:self.start('extract'),'primary')
        row=ttk.Frame(self.root);row.pack(fill='x',padx=13)
        self.apply_button=self.button(row,'APLICAR DUBLAGEM',lambda:self.start('apply'),'success')
        self.revert_button=self.button(row,'REVERTER DUBLAGEM',lambda:self.start('revert'),'warning')
        self.button(row,'VISUALIZAR VÍDEO',self.preview,'teal');self.button(row,'CANCELAR',self.cancel_run,'danger')
        self.button(row,'PREPARAR FERRAMENTAS',lambda:self.project_actions['prepare_video_tools']())
        row=ttk.Frame(self.root);row.pack(fill='x',padx=16,pady=6)
        ttk.Label(row,text='Backup dos áudios WAV:').pack(side='left')
        ttk.Entry(row,textvariable=self.backup_var).pack(side='left',fill='x',expand=True,padx=6)
        ttk.Button(row,text='ESCOLHER',command=self.choose_backup).pack(side='left')
        ttk.Button(row,text='ABRIR BACKUP',command=lambda:self.open_folder(Path(self.backup_var.get()))).pack(side='left',padx=4)
        ttk.Label(self.root,text='Áudio curto recebe silêncio no fim; áudio longo é limitado à duração do vídeo. As faixas de áudio antigas são substituídas pela dublagem.\nOs originais são exportados em WAV PCM 16-bit, em subpastas. A reversão restaura o áudio, sem restaurar o vídeo inteiro byte por byte.',wraplength=1000).pack(anchor='w',padx=16)
        ttk.Progressbar(self.root,variable=self.progress,maximum=100).pack(fill='x',padx=16,pady=6)
        ttk.Label(self.root,textvariable=self.status,wraplength=1000).pack(fill='x',padx=16)
        self.log=tk.Text(self.root,height=8,state='disabled',wrap='word');self.log.pack(fill='both',expand=True,padx=16,pady=8)
    def add_paths(self,kind,paths):
        if self.running:return
        items=self.audios if kind=='audio' else self.files;extensions=AUDIO_EXTENSIONS if kind=='audio' else VIDEO_CONTAINERS
        seen=set(items)
        for raw in paths:
            path=Path(raw).expanduser().resolve();candidates=path.rglob('*') if path.is_dir() else [path]
            for file in candidates:
                if file.is_file() and file.suffix.lower() in extensions and file not in seen:items.append(file);seen.add(file)
        listing=self.lists[kind];listing.delete(0,'end')
        for path in items:listing.insert('end',f'{path.name} — {path.parent}')
        self.refresh_originals()
        pairs,issues=match_pairs(self.audios,self.files);self.status.set(f'{len(pairs)} par(es) pronto(s); {len(issues)} aviso(s). Aplicar e Reverter usam todos os vídeos carregados.')
    def add_files(self,kind):
        extensions=AUDIO_EXTENSIONS if kind=='audio' else VIDEO_CONTAINERS
        self.add_paths(kind,filedialog.askopenfilenames(parent=self.root,filetypes=[('Arquivos aceitos',' '.join('*'+ext for ext in sorted(extensions)))]))
    def add_folder(self,kind):
        folder=filedialog.askdirectory(parent=self.root)
        if folder:self.add_paths(kind,[folder])
    def drop(self,event,kind):self.add_paths(kind,self.root.tk.splitlist(event.data));return 'break'
    def remove(self,kind):
        if self.running:return
        items=self.audios if kind=='audio' else self.files;indices=set(self.lists[kind].curselection());items[:]=[p for i,p in enumerate(items) if i not in indices];self.add_paths(kind,[])
    def choose_backup(self):
        if self.running:return
        folder=filedialog.askdirectory(parent=self.root)
        if folder:self.backup_var.set(folder);self.refresh_originals()
    def open_folder(self,path):
        try:
            path.mkdir(parents=True,exist_ok=True)
            if os.name=='nt':os.startfile(str(path))
        except OSError as exc:messagebox.showerror('Pasta',str(exc),parent=self.root)
    def preview(self):
        selected=self.lists['video'].curselection()
        if not selected:self.status.set('Selecione um vídeo para visualizar.');return
        if self.running:self.status.set('Aguarde a troca terminar antes de abrir o vídeo.');return
        try:self.previews.append(VideoPreview(self,self.files[int(selected[0])]))
        except Exception as exc:messagebox.showerror('Vídeo',str(exc),parent=self.root)
    def close_previews(self):
        self.audio_player.close_window()
        for preview in self.previews:
            if not preview.closed:preview.close()
        self.previews=[]
    def start(self,mode):
        if self.running:return
        pairs,issues=match_pairs(self.audios,self.files) if mode=='apply' else ([(p,None) for p in self.files],[])
        for issue in issues:self.events.put(('log',issue))
        if not pairs:self.status.set('Nenhum par válido.' if mode=='apply' else 'Carregue os vídeos que deseja restaurar.');return
        if not self.backup_var.get().strip():self.status.set('Escolha a pasta de backup.');return
        ffmpeg=executable_path('ffmpeg',self.project_root);ffprobe=executable_path('ffprobe',self.project_root)
        if not ffmpeg or not ffprobe:self.status.set('Use PREPARAR FERRAMENTAS.');return
        description={'apply':'substituir o áudio','revert':'restaurar as faixas de áudio originais','extract':'extrair as faixas originais como WAV'}[mode]
        preview='\n'.join(video.name for video,_ in pairs[:8])
        if not messagebox.askyesno('Confirmar operação',f'Você vai {description} de {len(pairs)} vídeo(s), nos arquivos carregados:\n\n{preview}\n\nBackup: {self.backup_var.get()}\n\nContinuar?',parent=self.root):return
        self.close_previews();self.running=True;self.cancel_event.clear();self.progress.set(0)
        self.apply_button.configure(state='disabled');self.revert_button.configure(state='disabled')
        threading.Thread(target=self.worker,args=(mode,pairs,Path(self.backup_var.get()).resolve(),ffmpeg,ffprobe),daemon=True).start()
    def cancel_run(self):
        self.cancel_event.set()
        process=self.process
        if process is not None and process.poll() is None:process.terminate()
        if self.running:self.status.set('Cancelando após a etapa segura atual...')
    def worker(self,mode,pairs,backup_root,ffmpeg,ffprobe):
        completed=0;failed=0
        try:
            for index,(video,audio) in enumerate(pairs):
                if self.cancel_event.is_set():break
                temporary=None
                try:
                    if mode=='revert':restore_backup(backup_root,video,ffmpeg,ffprobe)
                    elif mode=='extract':ensure_backup(backup_root,video,ffmpeg,ffprobe)
                    else:
                        info=probe_video(ffprobe,video)
                        self.events.put(('log',f'Backup/validação: {video.name}'))
                        ensure_backup(backup_root,video,ffmpeg,ffprobe)
                        if self.cancel_event.is_set():break
                        fd,name=tempfile.mkstemp(prefix='.aplicar-',suffix=video.suffix,dir=video.parent);os.close(fd);temporary=Path(name)
                        self.events.put(('log',f'Aplicando dublagem: {video.name} ← {audio.name}'))
                        self.process=subprocess.Popen(replacement_command(ffmpeg,video,audio,temporary,info['duration']),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,**hidden_kwargs())
                        if self.cancel_event.is_set():self.process.terminate()
                        _out,error=self.process.communicate();code=self.process.returncode;self.process=None
                        if self.cancel_event.is_set():break
                        if code:raise RuntimeError(error.decode('utf-8',errors='replace')[-1500:])
                        check=probe_video(ffprobe,temporary)
                        if (check['video']['width'],check['video']['height'])!=(info['video']['width'],info['video']['height']):raise RuntimeError('Validação de vídeo falhou.')
                        os.replace(temporary,video);temporary=None
                    completed+=1;self.events.put(('log',f'OK: {video.name} — {"dublagem aplicada" if mode=="apply" else "WAV extraído" if mode=="extract" else "áudio original restaurado"}.'))
                except Exception as exc:
                    failed+=1;self.events.put(('log',f'ERRO: {video.name}: {exc}'))
                finally:
                    process=self.process
                    if process is not None:
                        if process.poll() is None:process.kill();process.wait()
                        if process.stderr:process.stderr.close()
                        self.process=None
                    if temporary is not None:temporary.unlink(missing_ok=True)
                self.events.put(('progress',(index+1)/len(pairs)*100))
        finally:self.events.put(('done',completed,failed,self.cancel_event.is_set()))
    def poll(self):
        try:
            while True:
                item=self.events.get_nowait()
                if item[0]=='log':self.log.configure(state='normal');self.log.insert('end',item[1]+'\n');self.log.see('end');self.log.configure(state='disabled');self.status.set(item[1])
                elif item[0]=='progress':self.progress.set(item[1])
                elif item[0]=='done':
                    self.refresh_originals()
                    self.running=False;self.apply_button.configure(state='normal');self.revert_button.configure(state='normal')
                    self.status.set(f'{"Cancelado" if item[3] else "Concluído"}: {item[1]} sucesso(s), {item[2]} erro(s).')
        except queue.Empty:pass
        try:self.root.after(100,self.poll)
        except tk.TclError:pass
    def apply_theme(self,theme):
        self.theme=theme
        self.audio_player.apply_theme(theme)
        for widget in [*self.lists.values(),self.log]:widget.configure(bg=theme.get('input','#FFFFFF'),fg=theme.get('input_text','#1F2937'),selectbackground=theme.get('select','#DBEAFE'))
        apply_button_style_to_tree(self.root,theme)
        for preview in self.previews:
            if not preview.closed:preview.apply_theme(theme)
    def refresh_originals(self):
        self.original_audios=[];listing=self.lists['original'];listing.delete(0,'end')
        root=Path(self.backup_var.get())
        for video in self.files:
            _wav,manifest=backup_paths(root,video)
            if not manifest.is_file():continue
            try:
                data=json.loads(manifest.read_text(encoding='utf-8'))
                for index,track in enumerate(data['tracks']):
                    path=(manifest.parent/track['file']).resolve()
                    if path.is_relative_to(manifest.parent.resolve()) and path.is_file():
                        self.original_audios.append(path);listing.insert('end',f'{video.name} — faixa {index+1} — {path.name}')
            except (OSError,KeyError,ValueError):continue
    def listen_audio(self,kind):
        selection=self.lists[kind].curselection()
        files=self.audios if kind=='audio' else self.original_audios
        if not selection or not files:return
        index=int(selection[0])
        self.audio_player.set_loaded_audio_pairs({p:(p,None) if kind=='original' else (None,p) for p in files})
        self.audio_player.play_one(files[index], 'OUVIR ÁUDIO ORIGINAL WAV' if kind=='original' else 'OUVIR ÁUDIO DUBLADO', playlist=files,index=index)
    def open_destination(self):
        selection=self.lists['video'].curselection()
        if not self.files:self.status.set('Carregue ou selecione um vídeo para abrir sua pasta de destino.');return
        path=self.files[int(selection[0])] if selection else self.files[0]
        self.open_folder(path.parent)
    def refresh_for_project(self):self.refresh_originals()
