"""Dublagem de trechos de TXT em arquivos independentes da cena principal."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import wave


def scene_parts_dir(root, source, scene):
    identity = json.dumps([str(source), str(scene)], ensure_ascii=False)
    return Path(root) / 'revisoes' / 'partes_txt' / hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]


def list_parts(folder):
    result = []
    if not Path(folder).is_dir():
        return result
    for child in Path(folder).glob('parte_*'):
        if not child.is_dir() or not child.name[6:].isdigit():
            continue
        audio, text = child/'parte.wav', child/'texto.txt'
        if audio.is_file() and text.is_file() and (child/'info.json').is_file():
            try:metadata=json.loads((child/'info.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):metadata={}
            result.append({'number': int(child.name[6:]), 'audio': audio, 'text': text, 'kind':metadata.get('kind','txt'), 'title':metadata.get('title',''), 'reference':child/'original.wav' if (child/'original.wav').is_file() else None})
    return sorted(result, key=lambda item: item['number'])


def run_command(command, cancel, progress=None):
    try:
        from .batch_tab import hidden_process_kwargs
    except ImportError:
        from batch_tab import hidden_process_kwargs
    # A file avoids pipe deadlocks and unbounded output buffering on long inference jobs.
    with tempfile.TemporaryDirectory(prefix='dublaskizon-parte-') as log_dir, (Path(log_dir)/'progress.log').open('w+b') as log:
        from generation_progress import GenerationProgress,emit_process_line,process_label
        label=process_label(command)+' — PARTE / RECORTE'
        emit_process_line(label,'Iniciando dublagem da parte ou recorte.')
        observer=GenerationProgress(progress or (lambda *args:None))
        offset=0;pending=''
        def read_progress():
            nonlocal offset,pending
            with (Path(log_dir)/'progress.log').open('rb') as reader:
                reader.seek(offset);data=reader.read();offset=reader.tell()
            pending+=data.decode('utf-8',errors='replace')
            import re
            lines=re.split(r'[\r\n]',pending);pending=lines.pop()
            for line in lines:
                observer.feed(line)
                emit_process_line(label,line)
        from warm_inference import review_memory_cache, WarmInference, LoggedScene
        while review_memory_cache.preloading:
            if cancel.wait(.1):raise RuntimeError('Dublagem da parte cancelada durante a preparação.')
        local_pool=None
        options=dict(stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONUNBUFFERED':'1'},**hidden_process_kwargs())
        if WarmInference.eligible(command):
            if review_memory_cache.enabled:
                process=review_memory_cache.start(command,**options)
            else:
                review_memory_cache.evict_idle('Liberado para dublar recorte')
                local_pool=WarmInference()
                try:
                    scene=local_pool.start(command,**options)
                    process=LoggedScene(scene,log,lambda code:None)
                except BaseException:
                    local_pool.close();raise
        else:
            process=subprocess.Popen(command,**options)
        try:
            while process.poll() is None:
                read_progress()
                if cancel.wait(0.15):
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
                    raise RuntimeError('Dublagem da parte cancelada.')
            log.seek(0, 2)
            read_progress()
            log.seek(max(0, log.tell()-4000))
            details = log.read().decode('utf-8', errors='replace')
            emit_process_line(label,'Processamento finalizado; código '+str(process.returncode)+'.')
            if process.returncode:
                report=None
                if '--output' in command:
                    target=Path(command[command.index('--output')+1])
                    try:
                        directory=target.parent.parent/'logs'
                        directory.mkdir(parents=True,exist_ok=True)
                        report=directory/('falha_'+str(time.time_ns())+'.log')
                        shutil.copy2(Path(log_dir)/'progress.log',report)
                    except OSError:pass
                native=(int(process.returncode)&0xFFFFFFFF)==0xC0000005
                summary=('O processo de áudio sofreu uma falha nativa de acesso à memória (0xC0000005).'
                         if native else f'Processamento terminou com código {process.returncode}.')
                if report:summary+='\nRelatório completo: '+str(report)
                if not native:summary+='\n'+details[-900:]
                raise RuntimeError(summary)
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            if local_pool is not None:local_pool.close()


def _generate_part(context, text, reference, cancel, runner=run_command):
    """Gera e valida primeiro; publica uma nova parte sem substituir cenas ou partes."""
    try:
        from .batch_tab import find_voice_command, apply_r_pronunciation
        from .duration_converter_tab import executable_path
    except ImportError:
        from batch_tab import find_voice_command, apply_r_pronunciation
        from duration_converter_tab import executable_path
    if cancel.is_set():
        raise RuntimeError('Dublagem da parte cancelada.')
    text = text.strip()
    if not text:
        raise ValueError('Deixe no TXT pelo menos a frase que deseja dublar.')
    reference = Path(reference)
    if not reference.is_file():
        raise ValueError('Áudio de referência não encontrado. Escolha outro áudio.')
    from f5_backend import MODEL as F5_MODEL, validate
    from directml_backend import MODEL as DML_MODEL, validate as validate_dml
    config = context['config']
    if config['model'] == F5_MODEL:
        validate(config['language'])
    elif config['model'] == DML_MODEL:
        validate_dml(config['language'])
    prefix = context.get('infer_prefix') or find_voice_command(config['model'])
    if not prefix:
        raise RuntimeError('OmniVoice não foi encontrado. Prepare as ferramentas de dublagem.')
    config = context['config']
    folder = scene_parts_dir(context['root'], context['source'], context['scene'])
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.gerando_', dir=folder) as temporary:
        generated = Path(temporary)/'gerado.wav'
        from speech_completeness import verified_command
        command = [*prefix, '--model', str(config['model']), '--text', apply_r_pronunciation(text, context.get('r_mode','unchanged')), '--language', str(config['language']), '--instruct', str(config['instruct']), '--ref_audio', str(reference), '--output', str(generated)]
        from voice_reference import protect_reference_command
        command=protect_reference_command(command,config['model'])
        command=verified_command(command,config['model'],context['root'])
        if 'omnivoice' in str(config['model']).lower() and len(command)>=4 and command[2]=='-c':
            command=list(command)
            command[3]='# DUBLASKIZON_SAFE_REFERENCE\n'+command[3]
        try:
            runner(command, cancel)
        except RuntimeError as exc:
            native=any(code in str(exc) for code in ('0xC0000005','3221225477','-1073741819'))
            if not native or cancel.is_set() or 'omnivoice' not in str(config['model']).lower() or len(command)<4 or command[2]!='-c':raise
            # A native CUDA/ASR failure gets one isolated recovery with Whisper
            # on CPU; synthesis parameters and text verification stay unchanged.
            command=list(command)
            command[3]='# DUBLASKIZON_ASR_CPU_RECOVERY\n'+command[3]
            generated.unlink(missing_ok=True)
            runner(command,cancel)
        if cancel.is_set():
            raise RuntimeError('Dublagem da parte cancelada.')
        if not generated.is_file():
            raise RuntimeError('OmniVoice não produziu o áudio da parte.')
        try:
            with wave.open(str(generated),'rb') as wav:
                actual=(wav.getnchannels(),wav.getsampwidth(),wav.getframerate())
                if wav.getnframes() <= 0:
                    raise ValueError('OmniVoice produziu um WAV vazio.')
        except wave.Error:
            actual=None  # FFmpeg converte também WAV float/extensible.
        desired=tuple(context.get('format') or actual or (1,2,24000))
        ready=generated
        if desired != actual:
            ffmpeg=executable_path('ffmpeg',Path(context['root']))
            if not ffmpeg:
                raise RuntimeError('FFmpeg é necessário para compatibilizar a parte com o áudio principal.')
            codecs={1:'pcm_u8',2:'pcm_s16le',3:'pcm_s24le',4:'pcm_s32le'}
            ready=Path(temporary)/'compativel.wav'
            runner([ffmpeg,'-y','-i',str(generated),'-ac',str(desired[0]),'-ar',str(desired[2]),'-c:a',codecs[desired[1]],str(ready)],cancel)
        with wave.open(str(ready),'rb') as wav:
            if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate()) != desired or wav.getnframes()<=0:
                raise ValueError('O WAV gerado não é compatível com a montagem principal.')
        if cancel.is_set():
            raise RuntimeError('Dublagem da parte cancelada.')
        number=max((item['number'] for item in list_parts(folder)),default=0)+1
        while True:
            destination=folder/f'parte_{number:04d}'
            try:
                destination.mkdir()
                break
            except FileExistsError:
                number+=1
        try:
            shutil.copy2(ready,destination/'parte.wav')
            if context.get('kind') == 'original':
                shutil.copy2(reference,destination/'original.wav')
            (destination/'texto.txt').write_text(text+'\n',encoding='utf-8')
            from speech_completeness import publish_review_report
            publish_review_report(generated,destination/'parte.wav')
            metadata={'scene':str(context['scene']),'source':str(context['source']),'reference':str(reference),'number':number,'created':time.strftime('%Y-%m-%d %H:%M:%S')}
            metadata['kind']=context.get('kind','txt')
            if metadata['kind']=='original':
                metadata['reference']=str(destination/'original.wav')
                metadata['original_source']=str(context.get('original',''))
            (destination/'info.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception:
            # Remove only our incomplete publication, never an existing part.
            for name in ('parte.wav','texto.txt','info.json','original.wav'):
                (destination/name).unlink(missing_ok=True)
            destination.rmdir()
            raise
    return {'number':number,'audio':destination/'parte.wav','text':destination/'texto.txt','kind':context.get('kind','txt'),'reference':destination/'original.wav' if context.get('kind')=='original' else None}


def generate_part(context,text,reference,cancel,runner=run_command):
    from generation_progress import emit_process_line
    label='GERAÇÃO — '+str(context.get('scene','parte'))+' — '+str(context.get('kind','txt'))
    emit_process_line(label,'Iniciando parte independente da cena.')
    try:
        result=_generate_part(context,text,reference,cancel,runner)
        emit_process_line(label,'CONCLUÍDO: parte salva em '+str(result['audio']))
        return result
    except Exception as exc:
        emit_process_line(label,'ERRO: '+str(exc))
        raise


class ScenePartsUI:
    def __init__(self, player):
        self.player=player
        self.children=[]
        self.busy=False
        self.cancel=threading.Event()
        self.sidebar=None
        self.identity=None

    def context(self):
        player=self.player
        scene=player._scene_text_key()
        if not scene or player.project_root is None:
            raise ValueError('Abra uma cena de um projeto antes de dublar uma parte.')
        provider=getattr(player,'part_context_provider',None)
        context=dict(provider(scene)) if callable(provider) else {}
        if not context:
            try:
                from .review_tab import DEFAULT_CONFIG
            except ImportError:
                from review_tab import DEFAULT_CONFIG
            config=dict(DEFAULT_CONFIG)
            file=player.project_root/'revisoes'/'revisao_config.json'
            if file.is_file():
                stored=json.loads(file.read_text(encoding='utf-8'))
                if isinstance(stored,dict):config.update(stored)
            reference=player._current_audio_path('original')
            if player.dubbed_folder_name=='dublados personalizados':
                manifest=player.project_root/'dublados personalizados'/'_manifesto_personalizado.json'
                records=json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
                value=records.get(scene,{}).get('voice_model')
                reference=Path(value) if value else None
                if reference and not reference.is_absolute():reference=player.project_root/reference
            context={'config':config,'reference':reference}
        context.update(root=player.project_root,scene=scene,source=player.dubbed_folder_name,original=player._current_audio_path('original'))
        track=player.audio_edit_working.get('dubbed')
        if track is not None:
            context['format']=(track['channels'],track['sample_width'],track['sample_rate'])
        else:
            path=player._current_audio_path('dubbed')
            if path is not None:
                try:
                    with wave.open(str(path),'rb') as wav:context['format']=(wav.getnchannels(),wav.getsampwidth(),wav.getframerate())
                except (OSError,wave.Error):pass
        return context

    def attach(self, parent):
        import tkinter as tk
        surface=self.player.theme.get('surface','#FFFFFF')
        side=tk.Frame(parent,bg=surface,width=150)
        side.pack(side='right',fill='y',padx=(0,5),pady=6)
        side.pack_propagate(False)
        self.player.editor_mode_buttons={}
        for mode,label in (('simple','OUVIR CENA - EDITOR SIMPLES'),('advanced','OUVIR CENA - EDITOR AVANÇADO')):
            selected=mode==getattr(self.player,'editor_mode','advanced')
            button=tk.Button(side,text=label,wraplength=135,font=('Segoe UI',8,'bold'),relief='sunken' if selected else 'raised',bg='#0891B2' if selected else '#475569',fg='white',command=lambda value=mode:self.player.set_editor_mode(value))
            button.pack(fill='x',padx=3,pady=(0,4))
            self.player.editor_mode_buttons[mode]=button
        tk.Label(side,text='PARTES DO TXT E DOS ÁUDIOS ORIGINAIS DUBLADOS',wraplength=100,bg=surface,fg=self.player.theme.get('text','#111827'),font=('Segoe UI',8,'bold')).pack(fill='x',pady=5)
        canvas=tk.Canvas(side,width=88,bg=surface,highlightthickness=0)
        scroll=tk.Scrollbar(side,orient='vertical',command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        self.sidebar=tk.Frame(canvas,bg=surface)
        item=canvas.create_window((0,0),window=self.sidebar,anchor='nw')
        self.sidebar.bind('<Configure>',lambda _e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
        main=tk.Frame(parent,bg=surface);main.pack(side='left',fill='both',expand=True)
        self.identity=None
        self.refresh(force=True)
        return main

    def refresh(self, force=False):
        if self.sidebar is None or not self.sidebar.winfo_exists():return
        player=self.player
        identity=(str(player.project_root),player.dubbed_folder_name,player._scene_text_key())
        if identity==self.identity and not force:return
        self.identity=identity
        for child in self.sidebar.winfo_children():child.destroy()
        if not player.project_root or not identity[2]:return
        parts=list_parts(scene_parts_dir(player.project_root,identity[1],identity[2]))
        import tkinter as tk
        try:
            from .ui_theme import apply_button_style
        except ImportError:
            from ui_theme import apply_button_style
        for part in reversed(parts):
            tile=tk.Frame(self.sidebar,bg=player.theme.get('surface','#FFFFFF'));tile.pack(fill='x',padx=3,pady=3)
            button=tk.Button(tile,text=f"PARTE\n({part['number']})",font=('Segoe UI',11,'bold'),height=3,relief='flat',command=lambda p=part:self.open_part(p))
            apply_button_style(button,player.theme,'secondary')
            if part.get('kind')=='original':
                button.configure(text=f"ÁUDIO\n({part['number']})",bg='#A78BFA',fg='#111827',activebackground='#C4B5FD')
            if part.get('title'):button.configure(text=part['title'],wraplength=90,height=0)
            button.pack(fill='x')
            tk.Button(tile,text='✎',width=2,relief='raised',command=lambda item=part:self.rename_part(item)).pack(side='right')
        if not parts:tk.Label(self.sidebar,text='As partes\ngeradas\naparecerão\naqui.',bg=player.theme.get('surface','#FFFFFF'),fg=player.theme.get('text','#111827')).pack(pady=15)

    def rename_part(self,part):
        from tkinter import simpledialog,messagebox
        title=simpledialog.askstring('Nome da parte','Título desta parte:',initialvalue=part.get('title',''),parent=self.player.window)
        if title is None:return
        title=' '.join(title.split())[:160]
        path=part['audio'].parent/'info.json'
        try:
            data=json.loads(path.read_text(encoding='utf-8'));data['title']=title
            temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temporary,path)
            self.refresh(force=True)
        except (OSError,ValueError) as exc:messagebox.showerror('Nome da parte',str(exc),parent=self.player.window)

    def composer_original(self):
        """Edit a private copy with the existing waveform editor, never the source."""
        from tkinter import messagebox
        from audio_player import AudioPlayerManager
        try:
            if self.busy:
                raise ValueError('Aguarde a dublagem da parte atual terminar.')
            context=self.context()
            original=Path(context['original'])
            from scene_audio_choices import sources,choose_one,LABELS
            selected=choose_one(self.player.window or self.player.parent,sources(context['root'],original))
            if selected is None:return
            source_kind,original=selected
            source_label=LABELS[source_kind]
            folder=scene_parts_dir(context['root'],context['source'],context['scene'])/'rascunhos_audio'
            folder.mkdir(parents=True,exist_ok=True)
            draft=Path(tempfile.mkdtemp(prefix='recorte_',dir=folder))
            reference=draft/'original.wav'
            shutil.copy2(original,reference)
            text_path=draft/'texto.txt'
            text=self.player.scene_text_box.get('1.0','end-1c') if self.player.scene_text_box is not None else ''
            text_path.write_text(text,encoding='utf-8')
            child=AudioPlayerManager(self.player.parent,Path(context['root']))
            child.is_part_window=True
            child.original_reference_editor=True
            progress={'clone_progress':0,'dub_progress':0,'phase':'Pronto para dublar o recorte'}
            child.set_review_snapshot_provider(lambda key=None:dict(progress))
            child.part_file=reference
            child.clipboard_target=self.player
            child.set_loaded_audio_pairs({reference:(original,reference)})
            child.apply_theme(dict(self.player.theme))
            def save_text(_key,value):
                try:
                    text_path.write_text(value.strip()+'\n',encoding='utf-8')
                    return True,'Texto do recorte salvo; TXT principal preservado.'
                except OSError as exc:return False,str(exc)
            child.set_scene_text_integration(lambda key:{'text':text_path.read_text(encoding='utf-8'),'path':text_path,'title':'TEXTO DO RECORTE — EDITÁVEL'},save_text)
            def generate(_key=None):
                if self.busy:return
                value=child.scene_text_box.get('1.0','end-1c').strip()
                if not value:
                    messagebox.showwarning('Texto vazio','Digite somente a fala deste recorte.',parent=child.window);return
                child._save_audio_edit()
                if child.audio_edit_dirty:
                    messagebox.showerror('Salvar recorte','Não foi possível salvar a edição. A dublagem não iniciou.',parent=child.window);return
                saved,message=save_text(None,value)
                if not saved:
                    messagebox.showerror('Salvar texto',message,parent=child.window);return
                snapshot=draft/f'referencia_{time.time_ns()}.wav'
                shutil.copy2(reference,snapshot)
                context['kind']='original'
                self.busy=True;self.cancel.clear()
                progress.update(clone_progress=0,dub_progress=0,phase='Preparando recorte')
                result={};done=threading.Event()
                def worker():
                    try:
                        def update(clone,dub,phase):progress.update(clone_progress=clone,dub_progress=dub,phase=phase)
                        result['part']=generate_part(context,value,snapshot,self.cancel,runner=lambda command,cancel:run_command(command,cancel,update))
                    except Exception as exc:result['error']=str(exc)
                    finally:
                        try:snapshot.unlink(missing_ok=True)
                        except OSError:pass
                        done.set()
                def poll():
                    if not done.is_set():
                        if child.window is None or not child.window.winfo_exists():self.cancel.set()
                        else:child.emit_status('Dublando somente com o recorte salvo…')
                        self.player.parent.after(150,poll);return
                    self.busy=False
                    progress.update(clone_progress=100 if 'part' in result else progress['clone_progress'],dub_progress=100 if 'part' in result else progress['dub_progress'],phase='Parte salva' if 'part' in result else 'Falha ao gerar parte')
                    if 'error' in result:
                        messagebox.showerror('Dublar recorte',result['error'],parent=self.player.window);return
                    self.refresh(force=True)
                    self.open_part(result['part'],context)
                    child.emit_status('Parte gerada e salva em revisões. Original preservado.')
                threading.Thread(target=worker,daemon=True).start()
                self.player.parent.after(150,poll)
            child.set_scene_integration(review_actions={'redub':generate})
            child.play_one(reference,f"EDITAR RECORTE — {source_label} — {context['scene']}",scene_key=context['scene'],force_editor=True)
            child.stop(announce=False)
            child._toggle_audio_edit()
            child._set_audio_edit_status('Edite a onda inferior: ela é uma cópia do ORIGINAL. Ajuste o texto e clique em SALVAR E DUBLAR RECORTE.')
            self.children.append(child)
            # Keep this editor above its scene window after the source dialog closes.
            crop_window=child.window
            owner=self.player.window or self.player.parent
            crop_window.transient(owner)
            def foreground_crop():
                try:
                    if child.window is not crop_window or not crop_window.winfo_exists():return
                    crop_window.deiconify()
                    crop_window.lift(owner)
                    crop_window.focus_force()
                except Exception:pass
            foreground_crop()
            focus_job=crop_window.after_idle(foreground_crop)
            def cancel_focus(event):
                if event.widget is crop_window:
                    try:crop_window.after_cancel(focus_job)
                    except Exception:pass
            crop_window.bind('<Destroy>',cancel_focus,add='+')
        except Exception as exc:
            messagebox.showerror('Dublar parte do áudio original',str(exc),parent=self.player.window)

    def composer(self):
        import tkinter as tk
        from tkinter import filedialog,messagebox
        try:
            from .ui_theme import apply_button_style
        except ImportError:
            from ui_theme import apply_button_style
        if self.busy:
            messagebox.showinfo('Dublar parte','Aguarde a parte atual terminar.',parent=self.player.window);return
        try:context=self.context()
        except Exception as exc:
            messagebox.showerror('Dublar parte',str(exc),parent=self.player.window);return
        theme=dict(self.player.theme);surface=theme.get('surface','#FFFFFF');fg=theme.get('text','#111827')
        window=tk.Toplevel(self.player.window);window.title(f"DUBLAR PARTE DO TXT — {context['scene']}");window.geometry('820x500');window.minsize(660,400);window.configure(bg=surface)
        window.grid_columnconfigure(0,weight=1)
        window.grid_rowconfigure(1,weight=1)
        tk.Label(window,text='Deixe somente o texto desta parte. O TXT e o áudio principal serão preservados.',bg=surface,fg=fg,wraplength=610,font=('Segoe UI',10)).grid(row=0,column=0,sticky='ew',padx=15,pady=12)
        editor=tk.Frame(window,bg=surface)
        editor.grid(row=1,column=0,sticky='nsew',padx=15)
        editor.grid_rowconfigure(0,weight=1);editor.grid_columnconfigure(0,weight=1)
        box=tk.Text(editor,height=8,wrap='word',undo=True,bg=theme.get('input',surface),fg=theme.get('input_text',fg),insertbackground=fg,font=('Segoe UI',11))
        box.grid(row=0,column=0,sticky='nsew')
        scrollbar=tk.Scrollbar(editor,orient='vertical',command=box.yview)
        scrollbar.grid(row=0,column=1,sticky='ns');box.configure(yscrollcommand=scrollbar.set)
        main_text=self.player.scene_text_box.get('1.0','end-1c') if self.player.scene_text_box is not None else ''
        draft=scene_parts_dir(context['root'],context['source'],context['scene'])/'rascunho.txt'
        try:initial_text=draft.read_text(encoding='utf-8-sig') if draft.is_file() else main_text
        except (OSError,UnicodeError):initial_text=main_text
        box.insert('1.0',initial_text)
        reference=context.get('reference')
        status=tk.StringVar(value=('Rascunho salvo carregado. ' if draft.is_file() else '')+'Referência: '+(Path(reference).name if reference else 'Escolha outro áudio.'))
        tk.Label(window,textvariable=status,bg=surface,fg=fg,wraplength=610,anchor='w',justify='left').grid(row=2,column=0,sticky='ew',padx=15,pady=8)
        row=tk.Frame(window,bg=surface);row.grid(row=3,column=0,sticky='ew',padx=15,pady=(0,12))
        for column,weight in enumerate((1,1,2)):row.grid_columnconfigure(column,weight=weight)
        buttons=[]
        closing=[False]
        def close():
            if self.busy and getattr(self,'composer_window',None) is window:
                closing[0]=True;self.cancel.set();status.set('Cancelando… aguarde.');return
            window.destroy()
        window.protocol('WM_DELETE_WINDOW',close)
        window.bind('<Destroy>',lambda event:self.cancel.set() if event.widget is window and self.busy and getattr(self,'composer_window',None) is window else None)
        def save_draft():
            if self.busy:return
            text=box.get('1.0','end-1c').strip()
            if not text:
                messagebox.showwarning('Texto vazio','Digite o texto da parte antes de salvar.',parent=window);return
            temporary=None
            try:
                draft.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=draft.parent,suffix='.tmp',delete=False) as stream:
                    temporary=Path(stream.name);stream.write(text+'\n')
                os.replace(temporary,draft)
                status.set('Alteração salva no rascunho desta parte. O TXT principal permanece intacto.')
            except OSError as exc:
                messagebox.showerror('Salvar alteração',str(exc),parent=window)
            finally:
                if temporary is not None:temporary.unlink(missing_ok=True)
        def restore_main_text():
            if self.busy:return
            box.delete('1.0','end');box.insert('1.0',main_text)
            status.set('TXT principal carregado na janela. Deixe somente a próxima parte e salve se desejar.')
        def start(other=False):
            if self.busy:return
            text=box.get('1.0','end-1c').strip()
            if not text:messagebox.showwarning('Texto vazio','Digite a parte que deseja dublar.',parent=window);return
            ref=context.get('reference')
            if other:
                selected=filedialog.askopenfilename(parent=window,title='Referência para esta parte',filetypes=[('Áudios','*.wav *.mp3 *.flac *.ogg *.m4a *.aac *.aiff'),('Todos','*.*')])
                if not selected:return
                ref=Path(selected)
            if ref is None or not Path(ref).is_file():
                messagebox.showwarning('Referência','Modelo de voz não encontrado. Use REDUBLAR COM OUTRO ÁUDIO.',parent=window);return
            treated=getattr(self.player,'audacity_ui',None)
            if treated is not None:
                confirmed,ref=treated.choose_reference(ref,'Dublar parte do TXT','Dublar somente o texto desta parte com a referência escolhida?',parent=window)
                if not confirmed:return
            self.busy=True;self.cancel.clear();self.composer_window=window
            for button in buttons:button.configure(state='disabled')
            box.configure(state='disabled')
            result={};done=threading.Event();started=time.monotonic()
            def worker():
                try:result['part']=generate_part(context,text,ref,self.cancel)
                except Exception as exc:result['error']=str(exc)
                finally:done.set()
            def poll():
                if not done.is_set():
                    if window.winfo_exists():status.set(f"Dublando parte… {int(time.monotonic()-started)} s" if not self.cancel.is_set() else 'Cancelando…')
                    self.player.parent.after(150,poll);return
                self.busy=False
                if window.winfo_exists():
                    box.configure(state='normal')
                    for button in buttons:button.configure(state='normal')
                if 'error' in result:
                    if window.winfo_exists():
                        if closing[0]:window.destroy()
                        else:
                            status.set('Não foi possível dublar esta parte. Ajuste ou tente novamente.')
                            messagebox.showerror('Dublar parte',result['error'],parent=window)
                    return
                self.refresh(force=True)
                if window.winfo_exists():window.destroy()
                self.open_part(result['part'],context)
            threading.Thread(target=worker,daemon=True).start()
            self.player.parent.after(150,poll)
        for column,(text,command,role) in enumerate([('SALVAR ALTERAÇÃO',save_draft,'primary'),('REDUBLAR',lambda:start(False),'success'),('REDUBLAR COM OUTRO ÁUDIO',lambda:start(True),'accent')]):
            button=tk.Button(row,text=text,command=command,relief='flat',padx=8,pady=9,font=('Segoe UI',9,'bold'))
            apply_button_style(button,theme,role);button.grid(row=0,column=column,sticky='ew',padx=3,pady=(0,6));buttons.append(button)
        restore=tk.Button(row,text='CARREGAR TXT PRINCIPAL',command=restore_main_text,relief='flat',padx=8,pady=6,font=('Segoe UI',9,'bold'))
        apply_button_style(restore,theme,'secondary');restore.grid(row=1,column=0,columnspan=2,sticky='ew',padx=3);buttons.append(restore)
        cancel=tk.Button(row,text='CANCELAR / FECHAR',command=close,relief='flat',padx=8,pady=6,font=('Segoe UI',9,'bold'))
        apply_button_style(cancel,theme,'secondary');cancel.grid(row=1,column=2,sticky='ew',padx=3)
        box.focus_set()

    def open_part(self, part, context=None):
        from tkinter import messagebox
        try:
            from .audio_player import AudioPlayerManager
        except ImportError:
            from audio_player import AudioPlayerManager
        try:
            context=context or self.context()
            for child in self.children:
                if getattr(child,'part_file',None)==part['audio'] and child.window is not None and child.window.winfo_exists():
                    child.window.lift();return
            child=AudioPlayerManager(self.player.parent,Path(context['root']))
            child.is_part_window=True;child.clipboard_target=self.player;child.part_file=part['audio']
            child.set_loaded_audio_pairs({part['audio']:(part.get('reference') or context.get('original'),part['audio'])})
            child.set_dubbed_folder_name(context['source'])
            child.apply_theme(dict(self.player.theme))
            def load(_key):return {'text':part['text'].read_text(encoding='utf-8-sig'),'path':part['text'],'title':f"PARTE {part['number']}"}
            def save(_key,text):
                try:part['text'].write_text(text.strip()+'\n',encoding='utf-8');return True,'TXT desta parte salvo; o texto principal não foi alterado.'
                except OSError as exc:return False,str(exc)
            child.set_scene_text_integration(load,save)
            child.play_one(part['audio'],f"OUVIR PARTE {part['number']} — {context['scene']}",scene_key=context['scene'])
            if child.window is not None:child._toggle_audio_edit()
            self.children=[c for c in self.children if c.window is not None]+[child]
        except Exception as exc:
            messagebox.showerror('Abrir parte',str(exc),parent=self.player.window or self.player.parent)
