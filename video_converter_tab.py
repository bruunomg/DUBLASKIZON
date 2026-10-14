"""Compactação de vídeos baseada em compactar_videos_v2.py, com fila e prévia FFplay."""
from __future__ import annotations
import ctypes
import json
import math
import os
import queue
import subprocess
import tempfile
import threading
from collections import deque
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
try:
    from .duration_converter_tab import executable_path
    from .ui_theme import apply_button_style, apply_button_style_to_tree
except ImportError:
    from duration_converter_tab import executable_path
    from ui_theme import apply_button_style, apply_button_style_to_tree

VIDEO_EXTENSIONS = {'.mp4','.mkv','.avi','.mov','.webm','.m4v','.mpg','.mpeg','.wmv','.flv','.ts','.mts','.m2ts','.vob','.ogv','.3gp','.mxf'}
FORMATS = {'MP4 — H.265 (igual ao script)': ('.mp4','libx265'), 'MKV — H.265': ('.mkv','libx265'),
           'MP4 — H.264 (compatibilidade)': ('.mp4','libx264'), 'MOV — H.264': ('.mov','libx264'),
           'WebM — VP9': ('.webm','libvpx-vp9'), 'MKV — sem perdas (FFV1 + FLAC)': ('.mkv','ffv1')}
QUALITY = {'Igual ao script — CRF 28':28, 'Maior qualidade — CRF 20':20, 'Qualidade muito alta — CRF 16':16}
DEFAULT_FORMAT = next(iter(FORMATS))
DEFAULT_QUALITY = next(iter(QUALITY))

def hidden_kwargs():
    return {'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}

def format_size(size):
    return f'{size / (1024 * 1024):.2f} MB'

def parse_position(text):
    pieces=str(text).strip().replace(',','.').split(':')
    if not 1 <= len(pieces) <= 3:
        raise ValueError('Informe segundos ou HH:MM:SS.')
    result=0.0
    for item in pieces:
        value=float(item)
        if not math.isfinite(value) or value < 0:
            raise ValueError('O tempo deve ser positivo.')
        result=result*60+value
    return result

def probe_video(ffprobe, path):
    result=subprocess.run([str(ffprobe),'-v','error','-show_format','-show_streams','-of','json',str(path)],
                          capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45,**hidden_kwargs())
    if result.returncode:
        raise RuntimeError(result.stderr[-1800:] or 'Não foi possível ler o arquivo.')
    data=json.loads(result.stdout)
    streams=[s for s in data.get('streams',[]) if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')]
    if not streams:
        raise ValueError('O arquivo não contém uma faixa de vídeo.')
    raw=data.get('format',{}).get('duration') or streams[0].get('duration') or 0
    try: duration=float(raw)
    except (ValueError,TypeError): duration=0
    return {'duration':duration if math.isfinite(duration) and duration>0 else 0, 'video':streams[0]}

def conversion_command(ffmpeg, source, target, format_name, quality):
    _extension,codec=FORMATS[format_name]
    cmd=[str(ffmpeg),'-y','-nostdin','-hide_banner','-loglevel','error','-i',str(source),'-map','0:V:0','-map','0:a?',
         '-map_metadata','0','-c:v',codec]
    if codec=='ffv1':
        cmd += ['-level','3','-c:a','flac']
    elif codec=='libvpx-vp9':
        cmd += ['-crf',str(QUALITY[quality]),'-b:v','0','-deadline','good','-cpu-used','2','-c:a','libopus','-b:a','128k']
    else:
        cmd += ['-crf',str(QUALITY[quality]),'-preset','medium','-c:a','aac','-b:a','128k']
        if Path(target).suffix.lower() in {'.mp4','.mov'}:
            cmd += ['-movflags','+faststart']
        if codec=='libx265' and Path(target).suffix.lower()=='.mp4': cmd += ['-tag:v','hvc1']
    return cmd+['-progress','pipe:1','-nostats',str(target)]

def unique_output(folder, source, extension):
    candidate=folder/f'{source.stem}_compacto{extension}'
    index=2
    while candidate.exists() or candidate.resolve()==source.resolve():
        candidate=folder/f'{source.stem}_compacto_{index}{extension}';index+=1
    return candidate

try:
    from .video_preview import VideoPreview
except ImportError:
    from video_preview import VideoPreview

class VideoConverterApp:
    def __init__(self,root,project_root,project_actions=None):
        self.root=root;self.project_root=Path(project_root).resolve();self.project_actions=project_actions or {}
        self.files=[];self.running=False;self.process=None;self.cancel_event=threading.Event();self.events=queue.Queue();self.previews=[]
        self.theme={};self.format_var=tk.StringVar(value=DEFAULT_FORMAT);self.quality_var=tk.StringVar(value=DEFAULT_QUALITY)
        self.output_var=tk.StringVar(value=str(self.project_root/'VIDEOS COMPACTADOS'))
        self.status_var=tk.StringVar(value='Adicione ou arraste vídeos para a lista.');self.progress_var=tk.DoubleVar(value=0)
        self.build_ui();self.root.after(120,self.poll)
    def button(self,parent,text,command,role='secondary'):
        button=tk.Button(parent,text=text,command=command,relief='flat',padx=9,pady=6,cursor='hand2')
        button.pack(side='left',padx=3,pady=3);apply_button_style(button,self.theme,role);return button
    def build_ui(self):
        ttk.Label(self.root,text='COMPACTAR / CONVERTER VÍDEOS',font=('Segoe UI',16,'bold')).pack(anchor='w',padx=16,pady=10)
        ttk.Label(self.root,text='Mantém a resolução e a taxa de quadros. O perfil do script usa H.265 / CRF 28 / AAC 128k (com perdas).\nMaior qualidade pode gerar arquivos maiores. Sem perdas preserva o conteúdo decodificado, mas pode aumentar muito o tamanho.',wraplength=1000).pack(anchor='w',padx=16)
        frame=ttk.LabelFrame(self.root,text='ARRASTE OS VÍDEOS AQUI — duplo clique para visualizar',padding=8);frame.pack(fill='both',expand=True,padx=16,pady=8)
        self.listbox=tk.Listbox(frame,selectmode='extended',exportselection=False,height=10)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=self.listbox.yview);scroll.pack(side='right',fill='y')
        self.listbox.configure(yscrollcommand=scroll.set);self.listbox.pack(fill='both',expand=True)
        self.listbox.bind('<Double-Button-1>',lambda event:self.preview_selected())
        for widget in (self.listbox,frame):
            try:widget.drop_target_register('DND_Files');widget.dnd_bind('<<Drop>>',self.drop)
            except (AttributeError,tk.TclError):pass
        row=ttk.Frame(self.root);row.pack(fill='x',padx=13)
        self.button(row,'ADICIONAR VÍDEOS',self.add_files,'primary');self.button(row,'ADICIONAR PASTA',self.add_folder)
        self.button(row,'REMOVER SELECIONADOS',self.remove_selected);self.button(row,'VISUALIZAR VÍDEO',self.preview_selected,'teal')
        self.button(row,'ABRIR PASTA DO VÍDEO',self.open_input)
        options=ttk.Frame(self.root);options.pack(fill='x',padx=16,pady=8);options.columnconfigure(1,weight=1)
        ttk.Label(options,text='Formato de saída:').grid(row=0,column=0,sticky='w',padx=4,pady=4)
        ttk.Combobox(options,textvariable=self.format_var,values=list(FORMATS),state='readonly',width=45).grid(row=0,column=1,sticky='ew',padx=4)
        ttk.Label(options,text='Qualidade (perfis com perdas):').grid(row=1,column=0,sticky='w',padx=4,pady=4)
        ttk.Combobox(options,textvariable=self.quality_var,values=list(QUALITY),state='readonly').grid(row=1,column=1,sticky='ew',padx=4)
        ttk.Label(options,text='Pasta de saída:').grid(row=2,column=0,sticky='w',padx=4,pady=4)
        ttk.Entry(options,textvariable=self.output_var).grid(row=2,column=1,sticky='ew',padx=4)
        ttk.Button(options,text='ESCOLHER PASTA',command=self.choose_output).grid(row=2,column=2,padx=4)
        row=ttk.Frame(self.root);row.pack(fill='x',padx=13)
        self.convert_button=self.button(row,'CONVERTER VÍDEO PARA FICAR MAIS LEVE',self.start,'success')
        self.button(row,'CANCELAR',self.cancel_run,'danger');self.button(row,'ABRIR PASTA DE SAÍDA',self.open_output)
        self.button(row,'PREPARAR FERRAMENTAS',lambda:self.project_actions.get('prepare_video_tools',lambda:None)(),'teal')
        ttk.Label(self.root,text='Os originais são preservados. Converte vídeo e faixas de áudio; não inclui legendas nem anexos.',wraplength=1000).pack(anchor='w',padx=16,pady=4)
        ttk.Progressbar(self.root,variable=self.progress_var,maximum=100).pack(fill='x',padx=16,pady=4)
        ttk.Label(self.root,textvariable=self.status_var,wraplength=1000).pack(fill='x',padx=16)
        self.log=tk.Text(self.root,height=8,state='disabled',wrap='word');self.log.pack(fill='both',expand=True,padx=16,pady=8)
    def add_paths(self,paths):
        if self.running:return
        seen=set(self.files)
        for raw in paths:
            path=Path(raw).expanduser().resolve()
            found=(p for p in path.rglob('*') if p.suffix.lower() in VIDEO_EXTENSIONS) if path.is_dir() else [path]
            for candidate in found:
                if candidate.is_file() and candidate not in seen:self.files.append(candidate);seen.add(candidate)
        self.listbox.delete(0,'end')
        for path in self.files:
            try:size=format_size(path.stat().st_size)
            except OSError:size='indisponível'
            self.listbox.insert('end',f'{path.name} — {size} — {path.parent}')
        self.status_var.set(f'{len(self.files)} vídeo(s) na fila. Entradas são verificadas antes da conversão.')
    def add_files(self):
        paths=filedialog.askopenfilenames(parent=self.root,title='Adicionar vídeos',filetypes=[('Vídeos',' '.join('*'+ext for ext in sorted(VIDEO_EXTENSIONS))),('Todos os arquivos','*.*')])
        self.add_paths(paths)
    def add_folder(self):
        folder=filedialog.askdirectory(parent=self.root)
        if folder:self.add_paths([folder])
    def drop(self,event):self.add_paths(self.root.tk.splitlist(event.data));return 'break'
    def remove_selected(self):
        if self.running:return
        indices=set(self.listbox.curselection());self.files=[p for i,p in enumerate(self.files) if i not in indices];self.add_paths([])
    def selected(self):
        selection=self.listbox.curselection()
        return self.files[int(selection[0])] if selection else None
    def preview_selected(self):
        path=self.selected()
        if path:
            try:self.previews.append(VideoPreview(self,path))
            except Exception as exc:messagebox.showerror('Visualizar vídeo',str(exc),parent=self.root)
        else:self.status_var.set('Selecione um vídeo para visualizar.')
    def choose_output(self):
        path=filedialog.askdirectory(parent=self.root)
        if path:self.output_var.set(path)
    def open_folder(self,path):
        try:
            path=Path(path);path.mkdir(parents=True,exist_ok=True)
            if os.name=='nt':os.startfile(str(path))
            else:subprocess.Popen(['open' if __import__('sys').platform=='darwin' else 'xdg-open',str(path)])
        except Exception as exc:messagebox.showerror('Abrir pasta',str(exc),parent=self.root)
    def open_input(self):
        path=self.selected()
        if path:self.open_folder(path.parent)
    def open_output(self):self.open_folder(self.output_var.get())
    def start(self):
        if self.running:return
        if not self.files:self.status_var.set('Adicione pelo menos um vídeo.');return
        ffmpeg=executable_path('ffmpeg',self.project_root);ffprobe=executable_path('ffprobe',self.project_root)
        if not ffmpeg or not ffprobe:
            self.status_var.set('Faltam FFmpeg/FFprobe. Clique em PREPARAR FERRAMENTAS.');return
        if not self.output_var.get().strip():self.status_var.set('Escolha a pasta de saída.');return
        self.running=True;self.cancel_event.clear();self.progress_var.set(0);self.convert_button.configure(state='disabled')
        settings=(list(self.files),Path(self.output_var.get()).expanduser().resolve(),self.format_var.get(),self.quality_var.get(),ffmpeg,ffprobe)
        threading.Thread(target=self.worker,args=settings,daemon=True).start()
    def cancel_run(self):
        self.cancel_event.set()
        process=self.process
        if process is not None and process.poll() is None:
            process.terminate()
            self.root.after(1500,lambda:process.kill() if process.poll() is None else None)
        if self.running:self.status_var.set('Cancelando... Os arquivos já concluídos serão mantidos.')
    def worker(self,files,folder,format_name,quality,ffmpeg,ffprobe):
        success=0;failed=0
        try:
            folder.mkdir(parents=True,exist_ok=True)
            for index,source in enumerate(files):
                if self.cancel_event.is_set():break
                partial=None
                try:
                    info=probe_video(ffprobe,source)
                    if self.cancel_event.is_set():break
                    extension=FORMATS[format_name][0];target=unique_output(folder,source,extension)
                    handle=tempfile.NamedTemporaryFile(prefix='.dublaskizon-video-',suffix=extension,dir=folder,delete=False);partial=Path(handle.name);handle.close()
                    self.events.put(('log',f'[{index+1}/{len(files)}] {source.name}: {format_size(source.stat().st_size)} → {target.name}'))
                    self.process=subprocess.Popen(conversion_command(ffmpeg,source,partial,format_name,quality),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',**hidden_kwargs())
                    if self.cancel_event.is_set():self.process.terminate()
                    tail=deque(maxlen=18)
                    for line in self.process.stdout:
                        tail.append(line.strip())
                        if line.startswith('out_time_us=') and info['duration']:
                            try:done=min(1,float(line.split('=',1)[1])/1e6/info['duration'])
                            except ValueError:continue
                            self.events.put(('progress',(index+done)/len(files)*100))
                    code=self.process.wait();self.process.stdout.close();self.process=None
                    if self.cancel_event.is_set():break
                    if code or not partial.is_file() or not partial.stat().st_size:raise RuntimeError('\n'.join(tail) or f'FFmpeg terminou com código {code}')
                    probe_video(ffprobe,partial)
                    # Rename sem sobrescrever saídas preexistentes no Windows.
                    target=unique_output(folder,source,extension);partial.rename(target);partial=None
                    before=source.stat().st_size;after=target.stat().st_size
                    reduction=(1-after/before)*100 if before else 0
                    note=f'redução {reduction:.1f}%' if reduction>=0 else f'ficou {-reduction:.1f}% maior; original preservado'
                    self.events.put(('log',f'OK: {target.name} — {format_size(before)} → {format_size(after)} ({note}).'))
                    success+=1
                except Exception as exc:
                    if not self.cancel_event.is_set():failed+=1;self.events.put(('log',f'ERRO em {source.name}: {exc}'))
                finally:
                    process = self.process
                    if process is not None:
                        if process.poll() is None:
                            process.kill()
                            process.wait(timeout=5)
                        if process.stdout is not None:
                            process.stdout.close()
                        self.process = None
                    if partial is not None:
                        try:partial.unlink(missing_ok=True)
                        except OSError:pass
                self.events.put(('progress',(index+1)/len(files)*100))
        except Exception as exc:failed+=1;self.events.put(('log',str(exc)))
        finally:self.events.put(('done',success,failed,self.cancel_event.is_set()))
    def poll(self):
        try:
            while True:
                item=self.events.get_nowait()
                if item[0]=='progress':self.progress_var.set(item[1])
                elif item[0]=='log':
                    self.log.configure(state='normal');self.log.insert('end',item[1]+'\n');self.log.see('end');self.log.configure(state='disabled');self.status_var.set(item[1])
                elif item[0]=='done':
                    self.running=False;self.convert_button.configure(state='normal')
                    self.status_var.set(f'{"Cancelado" if item[3] else "Concluído"}: {item[1]} convertido(s), {item[2]} erro(s).')
        except queue.Empty:pass
        try:self.root.after(120,self.poll)
        except tk.TclError:pass
    def apply_theme(self,theme):
        self.theme=theme
        for widget in (self.listbox,self.log):widget.configure(bg=theme.get('input','#FFFFFF'),fg=theme.get('input_text','#1F2937'),selectbackground=theme.get('select','#DBEAFE'))
        apply_button_style_to_tree(self.root,theme)
        for preview in self.previews:
            if not preview.closed:preview.apply_theme(theme)
    def refresh_for_project(self):pass
    def close_previews(self):
        for preview in self.previews:
            if not preview.closed:preview.close()
        self.previews=[]
