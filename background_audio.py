"""Non-destructive original background editor and floating-point PCM mixer."""
from pathlib import Path
import tempfile
import hashlib
import json
import uuid
import os
import audioop
import time
import tkinter as tk
from tkinter import messagebox
import numpy as np
from pydub import AudioSegment


def segment(track: dict) -> AudioSegment:
    raw = track['frames']
    if track['sample_width'] == 1:
        raw = audioop.bias(raw, 1, -128)  # WAV uses unsigned 8-bit PCM.
    return AudioSegment(data=raw, sample_width=track['sample_width'],
                        frame_rate=track['sample_rate'], channels=track['channels'])


def track_frames(audio: AudioSegment, width: int) -> bytes:
    """Return WAV PCM in the target format, including packed 24-bit samples."""
    raw = audio.raw_data
    if audio.sample_width != width:
        raw = audioop.lin2lin(raw, audio.sample_width, width)
    return audioop.bias(raw, 1, 128) if width == 1 else raw


def mix_background(dub: AudioSegment, background: AudioSegment, gain_db: float) -> AudioSegment:
    """Keep both complete timelines; sum in float and attenuate only on overload."""
    if not np.isfinite(gain_db) or not -60 <= gain_db <= 6:
        raise ValueError('Volume deve ficar entre −60 e +6 dB.')
    if not dub.raw_data:
        raise ValueError('O dublado está vazio.')
    width = dub.sample_width
    # int32 intermediates also support 24-bit sources decoded by pydub.
    front = dub.set_sample_width(4)
    back = background.set_frame_rate(dub.frame_rate).set_channels(dub.channels).set_sample_width(4)
    a = np.array(front.get_array_of_samples(), dtype=np.float64)
    b = np.array(back.get_array_of_samples(), dtype=np.float64)
    if b.size > a.size:
        a = np.pad(a, (0, b.size-a.size))
    a[:b.size] += b * (10 ** (gain_db / 20))
    peak = float(np.max(np.abs(a)))
    ceiling = float(2**31 - 1)
    if peak > ceiling:
        a *= ceiling / peak
    pcm = np.rint(a).clip(-2**31, 2**31 - 1).astype('<i4').tobytes()
    return AudioSegment(pcm, sample_width=4, frame_rate=dub.frame_rate,
                        channels=dub.channels).set_sample_width(width)


def silence_range(audio: AudioSegment, start: int, end: int) -> AudioSegment:
    """Mute a section without moving later sounds out of sync."""
    start, end = sorted((max(0, min(len(audio), int(start))), max(0, min(len(audio), int(end)))))
    return audio[:start] + audio[start:end].apply_gain(-120) + audio[end:]


def combine_sources(tracks, reference):
    """Overlay synchronous sources with headroom; never concatenate or alter inputs."""
    if not tracks: raise ValueError('Selecione ao menos uma faixa.')
    import math
    normalized=[a.set_frame_rate(reference.frame_rate).set_channels(reference.channels).set_sample_width(reference.sample_width) for a in tracks]
    if len(normalized)==1: return normalized[0]
    mixed=AudioSegment.silent(duration=max(map(len,normalized)),frame_rate=reference.frame_rate).set_channels(reference.channels).set_sample_width(reference.sample_width)
    gain=-20*math.log10(len(normalized))
    for audio in normalized: mixed=mixed.overlay(audio.apply_gain(gain),position=0)
    return mixed


class BackgroundEditor:
    @staticmethod
    def busy(owner):
        controllers = [getattr(owner, 'translation_controller', None)]
        controllers += [getattr(cb, '__self__', None) for cb in owner.review_actions.values()]
        return getattr(owner, 'audio_transform_busy', False) or any(getattr(c, 'busy', False) for c in controllers if c)

    def __init__(self, owner, gain=-18.0):
        self.owner = owner
        if getattr(owner, 'original_reference_editor', False):
            raise ValueError('Abra o som de fundo na janela principal Ouvir cena.')
        self.track = owner._load_edit_track('dubbed')
        original = owner._load_edit_track('original')
        if self.track is None or original is None:
            raise ValueError('Selecione uma cena com original e dublado disponíveis.')
        if self.busy(owner):
            raise ValueError('Aguarde a edição em andamento terminar.')
        self.target = Path(self.track['path'])
        self.disk_hash = hashlib.sha256(self.target.read_bytes()).digest()
        self.base_frames = bytes(self.track['frames'])
        self.original = segment(original)
        self.background = self.original
        self.background_source_keys = ("original",)
        self.dub = segment(self.track)
        # Keep the dry dub separately so reopening never stacks the same background.
        root = Path(owner.project_root or self.target.parent)
        key = hashlib.sha256(str(self.target.resolve()).casefold().encode()).hexdigest()[:24]
        self.state_dir = root / 'revisoes' / '_som_de_fundo' / key
        try:
            state = self.state_dir / (self.disk_hash.hex() + '.json')
            if not state.exists():
                state = self.state_dir / 'estado.json'
            data = json.loads(state.read_text(encoding='utf-8'))
            if data['mixed_hash'] == self.disk_hash.hex():
                generation = data['generation']
                if not isinstance(generation, str) or not generation.isalnum():
                    raise ValueError('Identificador de edição inválido.')
                with (self.state_dir / generation / 'dublado_sem_fundo.wav').open('rb') as stream:
                    dry = AudioSegment.from_wav(stream)
                self.dub = dry.set_frame_rate(self.track['sample_rate']).set_channels(self.track['channels']).set_sample_width(self.track['sample_width'])
                with (self.state_dir / generation / 'fundo_editado.wav').open('rb') as stream:
                    self.background = AudioSegment.from_wav(stream)
                gain = float(data['gain_db'])
                self.background_source_keys = tuple(data.get('background_sources', ['original']))
        except Exception:
            # Optional cached editing state must never prevent opening the scene.
            pass
        self.undo, self.redo = [], []
        self.selection = None
        self.seek_ms=0
        self.temp = tempfile.TemporaryDirectory(prefix='dublaskizon_fundo_', ignore_cleanup_errors=True)
        self.window = tk.Toplevel(owner.window)
        self.window.title('Editar som de fundo do original — original preservado')
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        self.window.geometry(f'{min(1240,sw-60)}x{min(740,sh-100)}+25+35')
        self.window.configure(bg='#202B3B')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Destroy>', self.destroyed, add='+')
        self.gain = tk.DoubleVar(self.window, value=gain)
        controls = tk.Frame(self.window, bg='#202B3B'); controls.pack(fill='x', padx=10, pady=8)
        tk.Label(controls, text='Volume do fundo (dB)', bg='#202B3B', fg='white').pack(side='left')
        tk.Scale(controls, from_=-60, to=6, resolution=1, orient='horizontal', variable=self.gain,
                 length=210, bg='#202B3B', fg='white', highlightthickness=0).pack(side='left')
        self.button(controls, 'PARAR', self.stop_preview, '#FB7185')
        self.button(controls, 'EDIÇÃO COMPLETA DO FUNDO', self.advanced_edit, '#FDBA74')
        apply_bar=tk.Frame(self.window,bg='#202B3B')
        apply_bar.pack(fill='x',padx=10,pady=5,before=controls)
        self.apply_button=tk.Button(apply_bar,text='APLICAR E SALVAR DUBLADO COM FUNDO',command=self.apply,
                                    bg='#4ADE80',fg='#111827',font=('Segoe UI',8,'bold'),relief='flat',padx=8,pady=7)
        self.apply_button.pack(side='right')
        self.canvases = []
        self.duration_vars = []
        for label, color in [('ORIGINAL — REFERÊNCIA PRESERVADA','#A78BFA'),
                             ('FUNDO DO ORIGINAL — ARRASTE PARA SELECIONAR','#FDBA74'),
                             ('DUBLADO','#4ADE80')]:
            heading=tk.Frame(self.window,bg='#202B3B')
            heading.pack(fill='x',padx=12,pady=(8,0))
            tk.Label(heading,text=label,bg='#202B3B',fg=color,anchor='w').pack(side='left')
            if label.startswith('FUNDO DO ORIGINAL'):
                self.button(heading, 'ESCOLHER / COMBINAR FAIXAS', self.select_sources, '#FDBA74')
            duration_var=tk.StringVar(self.window)
            self.duration_vars.append(duration_var)
            tk.Label(heading,textvariable=duration_var,bg='#202B3B',fg=color).pack(side='right')
            canvas=tk.Canvas(self.window,height=95,bg='#111827',highlightthickness=0)
            canvas.pack(fill='both',expand=True,padx=12,pady=2)
            canvas.bind('<Configure>', lambda e:self.draw())
            self.canvases.append(canvas)
        for canvas in self.canvases:canvas.bind('<Button-1>',self.seek)
        self.canvases[1].bind('<Button-1>', self.press)
        self.canvases[1].bind('<B1-Motion>', self.drag)
        actions=tk.Frame(self.window,bg='#202B3B'); actions.pack(fill='x',padx=10,pady=8)
        self.button(actions,'−3 dB NA SELEÇÃO',lambda:self.gain_selection(-3),'#FDBA74')
        self.button(actions,'+3 dB NA SELEÇÃO',lambda:self.gain_selection(3),'#FDBA74')
        self.button(actions,'SILENCIAR TRECHO',lambda:self.edit('mute'),'#FDBA74')
        self.button(actions,'MANTER SÓ SELEÇÃO',lambda:self.edit('keep'),'#FDBA74')
        self.button(actions,'REMOVER E JUNTAR',lambda:self.edit('cut'),'#FDBA74')
        self.button(actions,'DESFAZER',self.undo_edit,'#94A3B8')
        self.button(actions,'REFAZER',self.redo_edit,'#94A3B8')
        self.button(actions,'RESTAURAR FUNDO',self.restore_background,'#94A3B8')
        self.status=tk.StringVar(self.window,value='Silenciar / manter seleção preservam as posições. Recortar e juntar desloca os sons seguintes. Volume afeta somente o fundo.')
        tk.Label(self.window,textvariable=self.status,bg='#202B3B',fg='white',wraplength=1000).pack(fill='x',padx=12)
        bottom=tk.Frame(self.window,bg='#202B3B'); bottom.pack(fill='x',padx=10,pady=8)
        self.play_buttons=[]
        starts=tk.Frame(bottom,bg='#202B3B');starts.grid(row=0,column=0,sticky='nsew',padx=3)
        for col in (0,1):bottom.columnconfigure(col,weight=1,uniform='transport')
        for label,kind,color in [('▶ INICIAR ORIGINAL','original','#A78BFA'),
                                 ('▶ INICIAR FUNDO','background','#FDBA74'),
                                 ('▶ OUVIR DUBLADO','dub','#4ADE80')]:
            button=tk.Button(starts,text=label,command=lambda k=kind:self.play_selected(k),bg=color,
                             fg='#111827',font=('Segoe UI',8,'bold'),relief='flat',pady=3)
            button.pack(fill='x',pady=1);self.play_buttons.append(button)
        self.mix_button=tk.Button(bottom,text='▶ INICIAR DUBLADO COM FUNDO DO ORIGINAL',command=self.play_mix,
                                  bg='#38BDF8',fg='#111827',font=('Segoe UI',9,'bold'),wraplength=220,relief='flat')
        self.mix_button.grid(row=0,column=1,sticky='nsew',padx=3)
        self.stop_button=tk.Button(bottom,text='PARAR',command=self.stop_preview,bg='#FB7185',relief='flat',padx=15)
        self.stop_button.grid(row=0,column=2,sticky='nsew',padx=3)
        tk.Button(bottom,text='FECHAR',command=self.close,bg='#94A3B8',relief='flat').grid(row=1,column=2,sticky='ew',pady=4)
        self.gain.trace_add('write', lambda *_: self.draw())
        self.window.after_idle(self.draw)

    @staticmethod
    def button(parent,text,command,color):
        b=tk.Button(parent,text=text,command=command,bg=color,fg='#111827',font=('Segoe UI',8,'bold'),relief='flat',padx=7,pady=5)
        b.pack(side='left',padx=3)
        return b

    def draw(self):
        duration=max(len(self.original),len(self.background),len(self.dub),1)
        for canvas,audio,color in zip(self.canvases,[self.original,self.background,self.dub],['#A78BFA','#FDBA74','#4ADE80']):
            self.duration_vars[self.canvases.index(canvas)].set(f'Duração: {len(audio)/1000:.3f} s | {audio.frame_rate} Hz | {audio.channels} canal(is)')
            canvas.delete('all'); w=max(canvas.winfo_width(),2); h=max(canvas.winfo_height(),2)
            from audio_player import AudioPlayerManager
            data=AudioPlayerManager._waveform_from_pcm(track_frames(audio,audio.sample_width),audio.channels,audio.sample_width,audio.frame_rate,points=max(1,w))
            peaks=data['samples'];span=max(1,int(w*len(audio)/duration))
            for index,peak in enumerate(peaks):
                x=index*span/max(1,len(peaks))
                if canvas is self.canvases[1]:peak*=10**(self.gain.get()/20)
                peak=min(1.0,peak)
                canvas.create_line(x,h/2-peak*h*.46,x,h/2+peak*h*.46,fill=color)
            if canvas==self.canvases[1] and self.selection:
                a,b=sorted(self.selection)
                canvas.create_rectangle(a/duration*w,0,b/duration*w,h,outline='white',fill='#FFFFFF',stipple='gray25')
        self.draw_preview_cursor()

    def draw_preview_cursor(self):
        duration=max(len(self.original),len(self.background),len(self.dub),1)/1000
        kinds=getattr(self,'preview_kinds',())
        for index,canvas in enumerate(self.canvases):
            canvas.delete('play_cursor')
            if index in kinds:
                x=min(canvas.winfo_width(),max(0,getattr(self,'preview_seconds',0)/duration*canvas.winfo_width()))
                canvas.create_line(x,1,x,canvas.winfo_height(),fill='white',width=2,tags='play_cursor')

    def stop_preview(self):
        callback=getattr(self,'preview_after',None)
        if callback:
            try:self.window.after_cancel(callback)
            except tk.TclError:pass
        self.preview_after=None;self.preview_kinds=()
        self.owner.stop(announce=False)
        child=getattr(self,'advanced',None)
        if child is not None:child.stop(announce=False)
        if self.window.winfo_exists():self.draw_preview_cursor()

    def play_selected(self,kind):
        audio={'original':self.original,'background':self.background.apply_gain(self.gain.get()),'dub':self.dub}[kind]
        self.play(audio,kind)

    def position(self,event):
        duration=max(len(self.original),len(self.background),len(self.dub),1)
        return max(0,min(duration,int(event.x/max(1,event.widget.winfo_width())*duration)))

    def seek(self,event):
        self.seek_ms=self.position(event)
        self.preview_seconds=self.seek_ms/1000
        self.preview_kinds=(0,1,2)
        self.draw_preview_cursor()

    def press(self,event):
        self.seek(event)
        p=min(len(self.background),self.seek_ms); self.selection=(p,p); self.draw()

    def gain_selection(self,db):
        if not self.selection or abs(self.selection[0]-self.selection[1])<1:
            self.status.set('Selecione um trecho na onda laranja para alterar o volume.');return
        a,b=sorted(max(0,min(len(self.background),int(v))) for v in self.selection)
        self.change(self.background[:a]+self.background[a:b].apply_gain(db)+self.background[b:])
        self.selection=(a,b);self.draw()
        self.status.set('Volume da seleção alterado em %+.0f dB. DESFAZER reverte o ajuste.'%db)


    def drag(self,event):
        if self.selection:
            self.selection=(self.selection[0],self.position(event)); self.draw()
            a,b=sorted(self.selection)
            self.status.set(f'Seleção do fundo: {a/1000:.3f} s até {b/1000:.3f} s. Silenciar mantém a posição dos sons seguintes.')

    def source_audio(self, keys):
        from scene_audio_choices import sources
        options=sources(self.owner.project_root, self.owner._current_audio_path('original'))
        tracks=[]
        for key in keys:
            path=options.get(key)
            if path is None or not path.is_file(): raise ValueError('Faixa indisponível: '+key)
            with path.open('rb') as stream: tracks.append(AudioSegment.from_wav(stream))
        return combine_sources(tracks, self.original)

    def select_sources(self):
        from scene_audio_choices import sources, choose, LABELS
        try:
            child=getattr(self,'advanced',None)
            if child is not None and child.window is not None and child.window.winfo_exists():
                raise ValueError('Feche a edição completa antes de trocar as faixas de fundo.')
            selected=choose(self.window, sources(self.owner.project_root,self.owner._current_audio_path('original')),
                            'Escolher som de fundo',self.background_source_keys)
            if selected is None: return
            keys=tuple(key for key,_ in selected)
            self.change(self.source_audio(keys), keys)
            self.status.set('Fundo: '+' + '.join(LABELS[key] for key in keys)+'. Faixas combinadas no mesmo tempo; volume ajustável acima.')
        except Exception as exc: messagebox.showerror('Som de fundo',str(exc),parent=self.window)

    def restore_background(self):
        try: self.change(self.source_audio(self.background_source_keys))
        except Exception as exc: messagebox.showerror('Som de fundo',str(exc),parent=self.window)

    def change(self,audio,source_keys=None):
        self.owner.stop(announce=False)
        self.undo.append((self.background,self.background_source_keys)); self.redo.clear(); self.background=audio
        if source_keys is not None: self.background_source_keys=tuple(source_keys)
        self.selection=None; self.draw()

    def edit(self,action):
        if not self.selection or abs(self.selection[0]-self.selection[1])<1:
            self.status.set('Arraste sobre a onda laranja para selecionar o trecho.'); return
        a,b=sorted(self.selection)
        if action=='mute': result=silence_range(self.background,a,b)
        elif action=='keep':
            result=silence_range(silence_range(self.background,0,a),b,len(self.background))
        else: result=self.background[:a]+self.background[b:]
        self.change(result)

    def undo_edit(self):
        if self.undo:
            self.owner.stop(announce=False); self.redo.append((self.background,self.background_source_keys)); self.background,self.background_source_keys=self.undo.pop(); self.selection=None; self.draw()

    def redo_edit(self):
        if self.redo:
            self.owner.stop(announce=False); self.undo.append((self.background,self.background_source_keys)); self.background,self.background_source_keys=self.redo.pop(); self.selection=None; self.draw()

    def play(self,audio,kind='mix'):
        try:
            self.stop_preview()
            path=Path(self.temp.name)/'preview.wav'
            with path.open('wb') as stream:
                audio.export(stream,format='wav')
            start=min(getattr(self,'seek_ms',0)/1000,len(audio)/1000)
            if start>=len(audio)/1000:
                self.status.set('O ponto escolhido está após o final desta faixa. Clique antes do final para ouvir.');return
            self.owner._start_paths([path], 'background_preview',start_seconds=start)
            playback_id=self.owner.playback_id
            self.preview_kinds={'original':(0,),'background':(1,),'dub':(2,),'mix':(0,1,2)}[kind]
            self.preview_seconds=start
            started=time.monotonic()
            def tick():
                self.preview_after=None
                if not self.window.winfo_exists():return
                if playback_id!=self.owner.playback_id:
                    self.preview_kinds=();self.draw_preview_cursor();return
                if self.owner.waveform_active_path==path.resolve():
                    self.preview_seconds=min(len(audio)/1000,start+max(0,time.monotonic()-self.owner.waveform_active_started_at))
                elif time.monotonic()-started>1 and (self.owner.thread is None or not self.owner.thread.is_alive()):
                    self.preview_kinds=();self.draw_preview_cursor();return
                self.draw_preview_cursor()
                self.preview_after=self.window.after(50,tick)
            tick()
        except Exception as exc: messagebox.showerror('Som de fundo',str(exc),parent=self.window)

    def play_mix(self):
        try: self.play(mix_background(self.dub,self.background,self.gain.get()))
        except Exception as exc: messagebox.showerror('Som de fundo',str(exc),parent=self.window)

    def advanced_edit(self):
        """Reuse the full existing editor on a private WAV, never the source file."""
        from audio_player import AudioPlayerManager
        child = getattr(self, 'advanced', None)
        if child is not None and child.window is not None and child.window.winfo_exists():
            child.window.lift()
            return
        try:
            path = Path(self.temp.name) / 'fundo_editavel.wav'
            reference = Path(self.temp.name) / 'referencia.wav'
            for audio, target in [(self.background, path), (self.original, reference)]:
                with target.open('wb') as stream:
                    audio.export(stream, format='wav')
            child = AudioPlayerManager(self.window, self.owner.project_root)
            self.advanced = child
            child.is_part_window = True
            child.original_reference_editor = True
            child.apply_theme(dict(self.owner.theme))
            child.set_loaded_audio_pairs({path:(reference,path)})

            def accept(_key=None):
                saved = child._save_audio_edit()
                if saved is False:
                    return
                if child.audio_edit_dirty:
                    return
                with path.open('rb') as stream:
                    updated = AudioSegment.from_wav(stream)
                if updated.raw_data != self.background.raw_data or updated.frame_rate != self.background.frame_rate:
                    self.change(updated)
                child.close_window()
                self.status.set('Fundo atualizado. Ouça a mistura antes de aplicar e salvar.')

            child.set_scene_integration(review_actions={'redub':accept})
            child.play_one(path, 'EDIÇÃO COMPLETA DO SOM DE FUNDO — cópia do original')
            child.stop(announce=False)
            child._toggle_audio_edit()
            for button, role in child.review_action_buttons:
                button.configure(text='USAR FUNDO EDITADO', bg='#FDBA74')
            child.start_button.configure(text='▶ INICIAR FUNDO EDITÁVEL',bg='#FDBA74')
            child._set_audio_edit_status('Edite a cópia laranja com as ferramentas habituais e clique em USAR FUNDO EDITADO. O original permanece intacto.')
            self.configure_advanced(child)
        except Exception as exc:
            messagebox.showerror('Editar fundo', str(exc), parent=self.window)

    def configure_advanced(self, child):
        """Add the dry dub and mixer transport without duplicating editing logic."""
        surface = child.theme.get('surface', '#202B3B')
        text = child.theme.get('text', 'white')
        # This editor has no transcription, navigation or dubbing job controls.
        for widget in child.window_content.pack_slaves():
            if widget is not child.waveform_panel:
                widget.pack_forget()
        child.project_trash_button.master.pack_forget()
        for widget in child.waveform_panel.winfo_children():
            for item in widget.winfo_children():
                if isinstance(item, tk.Frame):
                    for button in item.winfo_children():
                        if isinstance(button, tk.Button) and 'COLOCAR COMO SOM DE FUNDO' in button.cget('text'):
                            item.pack_forget()
        self.advanced_duration = tk.StringVar(child.window)
        row = tk.Frame(child.waveform_panel, bg=surface)
        row.pack(fill='x', padx=10, pady=4, before=child.waveform_scrollbar)
        tk.Label(row, text='DUBLADO — REFERÊNCIA', fg='#4ADE80', bg=surface, anchor='w').pack(side='left')
        tk.Label(row, textvariable=self.advanced_duration, fg=text, bg=surface).pack(side='right')
        canvas = tk.Canvas(child.waveform_panel, height=70, bg=child.theme.get('input', '#111827'), highlightthickness=0)
        canvas.pack(fill='x', padx=10, pady=3, before=child.waveform_scrollbar)
        child.waveform_canvases['dry_dub'] = canvas
        canvas.bind('<Configure>', lambda e:child._draw_waveform('dry_dub'))
        child._bind_audio_zoom(canvas)

        native_draw = child._draw_waveform
        def draw_with_gain(kind):
            data = child.waveform_data.get(kind)
            if kind != 'dubbed' or not data:
                native_draw(kind)
                return
            samples = data.get('samples')
            data['samples'] = [min(1.0, value*10**(self.gain.get()/20)) for value in (samples or [])]
            try:
                native_draw(kind)
                if getattr(child,'_background_play_kind',None) in ('mix','dry_dub'):
                    child.waveform_canvases[kind].delete('progress')
            finally:
                data['samples'] = samples
        child._draw_waveform = draw_with_gain
        native_refresh = child._refresh_waveforms
        def refresh():
            native_refresh()
            child.waveform_data['dry_dub'] = child._waveform_from_pcm(
                self.dub.raw_data, self.dub.channels, self.dub.sample_width, self.dub.frame_rate, points=5600)
            child.waveform_reference_duration = max(child.waveform_reference_duration, len(self.dub)/1000)
            self.advanced_duration.set(f'Duração: {len(self.dub)/1000:.3f} s | {self.dub.frame_rate} Hz')
            child._draw_waveform('dry_dub')
        child._refresh_waveforms = refresh
        native_save = child._save_audio_edit
        def save_live():
            if getattr(child, 'audio_transform_busy', False):
                child._set_audio_edit_status('Aguarde o ajuste terminar antes de salvar.')
                return False
            native_save()
            if child.audio_edit_dirty:
                return False
            track = child.audio_edit_working.get('dubbed')
            if track is not None:
                updated = segment(track)
                if updated.raw_data != self.background.raw_data or updated.frame_rate != self.background.frame_rate:
                    self.change(updated)
            self.status.set(f'Fundo atualizado: {len(self.background)/1000:.3f} s. Ouça a mistura antes de aplicar.')
            refresh()
            return True
        child._save_audio_edit = save_live
        child.audio_save_button.configure(command=save_live)
        child.window.bind('<Control-s>',lambda e:(save_live(),'break')[1])

        top = tk.Frame(child.window_content, bg=surface)
        top.pack(fill='x', padx=10, pady=5, before=child.waveform_panel)
        def apply_mix():
            if save_live():
                child.close_window()
                self.apply()
        apply_button = tk.Button(top,text='APLICAR E SALVAR DUBLADO COM FUNDO',command=apply_mix,
                                 bg='#4ADE80',fg='#111827',font=('Segoe UI',8,'bold'),padx=9,pady=7,relief='flat')
        apply_button.pack(side='right')
        self.advanced_apply_button = apply_button
        tk.Label(top,text='EDIÇÃO COMPLETA DO SOM DE FUNDO',bg=surface,fg=text,font=('Segoe UI',9,'bold')).pack(side='left')

        bottom = tk.Frame(child.window_content, bg=surface)
        bottom.pack(side='bottom', fill='x', padx=10, pady=8)
        starts = tk.Frame(bottom, bg=surface)
        starts.grid(row=0,column=0,sticky='nsew',padx=3)
        bottom.columnconfigure(0,weight=1,uniform='transport')
        bottom.columnconfigure(1,weight=1,uniform='transport')
        self.advanced_play_buttons=[]
        for label, kind, color in [('▶ INICIAR ORIGINAL','original','#A78BFA'),
                                   ('▶ INICIAR FUNDO EDITÁVEL','dubbed','#FDBA74'),
                                   ('▶ OUVIR DUBLADO','dry_dub','#4ADE80')]:
            button=tk.Button(starts,text=label,command=lambda k=kind:self.play_advanced(child,k),
                             bg=color,fg='#111827',font=('Segoe UI',8,'bold'),relief='flat',pady=4)
            button.pack(fill='x',pady=1)
            self.advanced_play_buttons.append(button)
        mix=tk.Button(bottom,text='▶ INICIAR DUBLADO COM FUNDO DO ORIGINAL',
                      command=lambda:self.play_advanced(child,'mix'),bg='#38BDF8',fg='#111827',
                      font=('Segoe UI',10,'bold'),wraplength=320,relief='flat')
        mix.grid(row=0,column=1,sticky='nsew',padx=4)
        stop=tk.Button(bottom,text='PARAR',command=lambda:child.stop(),bg='#FB7185',fg='#111827',relief='flat',padx=18)
        stop.grid(row=0,column=2,sticky='nsew',padx=4)
        self.advanced_mix_button, self.advanced_stop_button = mix, stop
        tk.Button(bottom,text='FECHAR',command=child.close_window,bg='#94A3B8',relief='flat').grid(row=1,column=2,sticky='ew',pady=4)
        # The regular editor already animates its active waveform. Mirror a mix's
        # clock onto every track, and give the extra dry-dub row the same cursor.
        native_poll = child._poll_waveform_progress
        def poll():
            native_poll()
            kind = getattr(child, '_background_play_kind', None)
            if child.waveform_active_kind is None:
                return
            elapsed = child.waveform_active_offset + max(0,time.monotonic()-child.waveform_active_started_at)
            targets = ['original','dubbed','dry_dub'] if kind == 'mix' else (['dry_dub'] if kind == 'dry_dub' else [])
            for key in targets:
                wave = child.waveform_canvases[key]
                wave.delete('background_cursor')
                duration = (child.waveform_data.get(key) or {}).get('duration', 0)
                if duration:
                    x = 2 + child._waveform_plot_width(key,max(180,wave.winfo_width())) * min(1,elapsed/duration)
                    wave.create_line(x,1,x,wave.winfo_height(),fill='white',width=2,tags='background_cursor')
        child._poll_waveform_progress = poll
        native_begin = child._begin_waveform_progress
        def begin(kind,path,playback_id,start_seconds=0):
            native_begin(kind,path,playback_id,start_seconds)
            if child.waveform_active_kind is not None:
                child.waveform_active_duration=getattr(child,'_background_preview_duration',child.waveform_active_duration)
        child._begin_waveform_progress = begin
        child._play_edit_preview = lambda kind,start_seconds=0:self.play_advanced(child,kind,start_seconds)
        native_stop = child.stop
        def stop_all(*args, **kwargs):
            native_stop(*args, **kwargs)
            for wave in child.waveform_canvases.values():
                try:wave.delete('background_cursor')
                except tk.TclError:pass
        child.stop = stop_all
        stop.configure(command=stop_all)
        def gain_updated(*_):
            if child.window is not None and child.window.winfo_exists():
                child._draw_waveform('dubbed')
        self.gain.trace_add('write',gain_updated)
        tk.Label(top,text='FUNDO dB',bg=surface,fg=text).pack(side='left',padx=8)
        tk.Scale(top,from_=-60,to=6,variable=self.gain,orient='horizontal',length=160,
                 bg=surface,fg=text,highlightthickness=0).pack(side='left')
        refresh()
        child.window.title('Edição completa do som de fundo')

    def play_advanced(self, child, kind, start_seconds=0):
        try:
            if getattr(child,'audio_transform_busy',False):
                return
            child.stop(announce=False)
            self.owner.stop(announce=False)
            background=segment(child.audio_edit_working['dubbed'])
            if kind=='original': audio=self.original
            elif kind=='dubbed': audio=background.apply_gain(self.gain.get())
            elif kind=='dry_dub': audio=self.dub
            else: audio=mix_background(self.dub,background,self.gain.get())
            path=Path(self.temp.name)/'advanced_preview.wav'
            with path.open('wb') as stream:audio.export(stream,format='wav')
            child._background_play_kind=kind
            playback_kind='original' if kind=='original' else 'dubbed'
            # Preview duration can differ from the editable background. The
            # playback clock reads the actual preview file for accurate timing.
            child._background_preview_duration=len(audio)/1000
            child._start_paths([path],playback_kind,start_seconds=start_seconds)
            return True
        except Exception as exc:
            messagebox.showerror('Reproduzir fundo',str(exc),parent=child.window)
            return False

    def apply(self):
        try:
            owner=self.owner
            child = getattr(self, 'advanced', None)
            if child is not None and child.window is not None and child.window.winfo_exists():
                raise ValueError('Conclua ou feche a edição completa do fundo antes de aplicar a mistura.')
            if owner._current_audio_path('dubbed') is None or Path(owner._current_audio_path('dubbed')).resolve()!=self.target.resolve():
                raise ValueError('A cena mudou. Abra o editor novamente na cena desejada.')
            if (owner.audio_edit_working.get('dubbed') is not self.track
                    or bytes(self.track['frames']) != self.base_frames or self.busy(owner)
                    or hashlib.sha256(self.target.read_bytes()).digest() != self.disk_hash):
                raise ValueError('O dublado foi alterado. Reabra o editor para usar a versão atual.')
            mixed=mix_background(self.dub,self.background,self.gain.get())
            if not owner.audio_edit_mode:
                owner._toggle_audio_edit()
            owner._set_edit_frames('dubbed',self.track,track_frames(mixed,self.track['sample_width']))
            owner._save_audio_edit()
            if owner.audio_edit_dirty:
                raise OSError('Não foi possível salvar. A mistura permanece na edição; consulte a mensagem da janela Ouvir cena.')
            owner.background_gain_var.set(self.gain.get())
            try:
                generation = uuid.uuid4().hex
                folder = self.state_dir / generation
                folder.mkdir(parents=True, exist_ok=True)
                with (folder / 'dublado_sem_fundo.wav').open('wb') as stream:
                    self.dub.export(stream, format='wav')
                with (folder / 'fundo_editado.wav').open('wb') as stream:
                    self.background.export(stream, format='wav')
                data = dict(generation=generation, gain_db=self.gain.get(), background_sources=list(self.background_source_keys),
                            mixed_hash=hashlib.sha256(self.target.read_bytes()).hexdigest())
                temporary = self.state_dir / (generation + '.tmp')
                temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
                os.replace(temporary, self.state_dir / 'estado.json')
                (self.state_dir / (data['mixed_hash'] + '.json')).write_text(json.dumps(data, indent=2), encoding='utf-8')
            except OSError as exc:
                messagebox.showwarning('Som de fundo', f'Mistura salva, mas o projeto não permitiu guardar o rascunho do fundo: {exc}', parent=self.window)
            self.status.set('Mistura salva. Original preservado; dublado anterior disponível em RECUPERAR DUBLADO ANTERIOR.')
            self.close()
        except Exception as exc: messagebox.showerror('Som de fundo',str(exc),parent=self.window)

    def close(self):
        self.stop_preview()
        child = getattr(self, 'advanced', None)
        if child is not None:
            child.close_window()
        self.window.destroy()
        self.temp.cleanup()

    def destroyed(self, event):
        if event.widget is self.window:
            self.owner.stop(announce=False)
            child = getattr(self, 'advanced', None)
            if child is not None:
                child.stop(announce=False)
            self.temp.cleanup()
