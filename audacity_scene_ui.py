"""Optional OpenVINO tracks and reference choices for scene players."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from audacity_openvino import KINDS, LABELS, outputs, process_original

COLORS={'instrumental':'#38BDF8','vocals':'#FBBF24','suppression':'#F472B6'}

class AudacitySceneUI:
    def __init__(self,player):
        self.player=player
        self.music=tk.BooleanVar(player.window,value=False)
        self.noise=tk.BooleanVar(player.window,value=False)
        self.visible={k:tk.BooleanVar(player.window,value=True) for k in KINDS}
        self.all_visible=tk.BooleanVar(player.window,value=True)
        self.confirm_effect=tk.BooleanVar(player.window,value=True)
        self.rows={};self.play_buttons={};self.paths={}
        self.busy=False;self.cancel=threading.Event();self.events=queue.Queue()
        self.percent=tk.DoubleVar(player.window,value=0)
        self.status=tk.StringVar(player.window,value='AUDACITY: pronto — original preservado')
        self.failed_source=None;self.source=None

    def attach_heading(self,heading,row):
        p=self.player; bg=p.theme.get('surface','#FFFFFF')
        buttons=tk.Frame(row,bg=bg)
        self.effect_buttons=[]
        for label,suppress in [('AUDACITY Music Separation',False),('AUDACITY Noise Suppression',True)]:
            button=tk.Button(buttons,text=label,bg='#C49A18',activebackground='#D8AD28',fg='#111827',activeforeground='#111827',
                relief='flat',font=('Segoe UI',7,'bold'),padx=6,pady=3,command=lambda s=suppress:self.request_effect(s))
            button.pack(side='left',padx=3);self.effect_buttons.append(button)
        ttk.Checkbutton(buttons,text='Confirmar efeito no Audacity',variable=self.confirm_effect).pack(side='left',padx=4)
        buttons.pack(in_=heading,side='left')
        def reflow_heading(_event=None):
            try:
                needed=sum(w.winfo_reqwidth()+10 for w in heading.winfo_children())+buttons.winfo_reqwidth()+10
                inline=needed<=heading.winfo_width()
                if getattr(buttons,'inline',None)==inline:return
                buttons.pack_forget()
                if inline:buttons.pack(in_=heading,side='left')
                else:buttons.pack(in_=row,fill='x',before=row.winfo_children()[-1])
                buttons.inline=inline
            except tk.TclError:pass
        heading.bind('<Configure>',reflow_heading,add='+')

    def attach_controls(self,parent):
        p=self.player;bg=p.theme.get('surface','#FFFFFF')
        controls=tk.Frame(parent,bg=bg);controls.pack(fill='x',padx=10)
        checks=[ttk.Checkbutton(controls,text='Mostrar ondas tratadas',variable=self.all_visible,command=self.reflow)]
        for kind in KINDS:
            checks.append(ttk.Checkbutton(controls,text=LABELS[kind],variable=self.visible[kind],command=self.reflow))
        def fit_checks(event=None):
            width=event.width if event is not None else 1200
            columns=4 if width>=sum(w.winfo_reqwidth()+6 for w in checks) else 2 if width>=650 else 1
            for index,widget in enumerate(checks):widget.grid(row=index//columns,column=index%columns,sticky='w',padx=3)
        fit_checks();controls.bind('<Configure>',fit_checks)

    def attach_progress(self,parent):
        p=self.player;bg=p.theme.get('surface','#FFFFFF')
        self.progress_row=tk.Frame(parent,bg=bg);self.progress_row.pack(side='top',fill='x',pady=0)
        self.cancel_button=tk.Button(self.progress_row,text='CANCELAR',command=self.cancel.set,relief='flat',font=('Segoe UI',7),padx=1,pady=0,state='disabled')
        self.cancel_button.pack(side='right')
        tk.Label(self.progress_row,textvariable=self.status,bg=bg,fg=p.theme.get('text','#111827'),anchor='w',font=('Segoe UI',7)).pack(side='left')
        self.progress_bar=ttk.Progressbar(self.progress_row,variable=self.percent,maximum=100,length=80)
        self.progress_bar.pack(side='left',fill='x',expand=True,padx=3)


    def attach_tracks(self,parent):
        p=self.player;bg=p.theme.get('surface','#FFFFFF')
        self.attach_controls(parent)
        self.container=tk.Frame(parent,bg=bg);self.container.pack(fill='x',padx=10)
        for kind in KINDS:
            row=tk.Frame(self.container,bg=bg);self.rows[kind]=row
            header=tk.Frame(row,bg=bg);header.pack(fill='x')
            tk.Label(header,text=LABELS[kind],bg=bg,fg=COLORS[kind],font=('Segoe UI',8,'bold')).pack(side='left')
            duration=tk.StringVar(p.window,value='');p.waveform_duration_vars[kind]=duration
            tk.Label(header,textvariable=duration,bg=bg,fg=p.theme.get('muted','#64748B'),font=('Segoe UI',7)).pack(side='right')
            canvas=tk.Canvas(row,height=32,bg=p.theme.get('input','#FFFFFF'),highlightthickness=0)
            canvas.pack(fill='x',pady=(1,3));p.waveform_canvases[kind]=canvas
            p._bind_audio_zoom(canvas)
            canvas.bind('<Configure>',lambda event,k=kind:p._draw_waveform(k))
            canvas.configure(takefocus=True,cursor='hand2')
            canvas.bind('<Button-1>',lambda event,k=kind:p._on_waveform_press(k,event))
            canvas.bind('<B1-Motion>',lambda event,k=kind:p._on_waveform_motion(k,event))
            canvas.bind('<ButtonRelease-1>',lambda event,k=kind:p._on_waveform_release(k,event))
            canvas.bind('<Control-c>',p._copy_audio_selection)
            canvas.bind('<space>',p._toggle_edit_play_pause)

    def attach_playback(self,parent):
        box=tk.Frame(parent,bg=self.player.theme.get('surface','#FFFFFF'))
        box.pack(side='left',padx=3)
        for kind in KINDS:
            short={'instrumental':'ORIGINAL instrumental','vocals':'ORIGINAL vocals','suppression':'ORIGINAL vocals Suppression'}
            button=tk.Button(box,text='▶ '+short[kind],bg=COLORS[kind],fg='#111827',relief='flat',font=('Segoe UI',7,'bold'),pady=1,
                command=lambda k=kind:self.play(k),state='disabled')
            button.pack(fill='x',pady=1);self.play_buttons[kind]=button

    def play(self,kind):
        path=self.paths.get(kind)
        if path:self.player._start_paths([path],kind)

    def request_effect(self,suppression=False):
        if self.busy:return
        effect='AUDACITY Noise Suppression' if suppression else 'AUDACITY Music Separation'
        detail='Aplicar supressão somente à voz separada?' if suppression else 'Separar instrumental e voz do áudio original?'
        if self.confirm_effect.get() and not messagebox.askyesno('Confirmar efeito no Audacity',effect+'\n\n'+detail+'\nO original será preservado e os resultados serão salvos em revisoes.',parent=self.player.window):return
        self.failed_source=None
        self.start(suppression)

    def reflow(self):
        shown=False
        for kind,row in self.rows.items():
            if self.all_visible.get() and self.visible[kind].get() and kind in self.paths:
                row.pack(fill='x');shown=True
            else:row.pack_forget()
        # Empty pack containers retain their previous requested size in Tk.
        # Remove the container itself so hidden tracks contribute no scroll height.
        if shown:self.container.pack(fill='x',padx=10)
        else:self.container.pack_forget()
        from waveform_navigation import scroll_vertical
        self.player.parent.after_idle(lambda:scroll_vertical(self.player))

    def refresh(self):
        p=self.player;source=p._current_audio_path('original')
        self.paths=outputs(p.project_root,source) if source else {}
        for kind,button in self.play_buttons.items():button.configure(state='normal' if kind in self.paths else 'disabled')
        self.reflow()

    def start(self,suppression=False):
        p=self.player;source=p._current_audio_path('original')
        if getattr(p,'audacity_ui',None) is not self or p.window is None:return
        if self.busy:return
        if not source or not p.project_root:return
        # Do not run a second AI workload during cloning/dubbing.
        controller=getattr(p,'translation_controller',None)
        if getattr(controller,'busy',False):
            self.failed_source=str(source)
            self.status.set('Aguarde a dublagem terminar antes de tratar o original.');return
        self.busy=True;self.source=source;self.cancel.clear();self.percent.set(0)
        for button in self.effect_buttons:button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.status.set('Preparando tratamento do original…')
        root=p.project_root
        def worker():
            try:
                result=process_original(root,source,suppression,self.cancel,lambda n,s:self.events.put(('progress',(n,s))))
                self.events.put(('done',result))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()
        p.parent.after(100,self.poll)

    def poll(self):
        p=self.player
        if p.window is None or getattr(p,'audacity_ui',None) is not self:
            self.cancel.set();return
        finished=False
        while True:
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=='progress':
                self.percent.set(value[0]);self.status.set(value[1]);p.emit_status(value[1])
            else:
                self.busy=False;finished=True;self.cancel_button.configure(state='disabled')
                for button in self.effect_buttons:button.configure(state='normal')
                if kind=='error':
                    self.failed_source=str(self.source);self.status.set('Falha — original preservado')
                    p.emit_status('AUDACITY: '+value)
                    messagebox.showerror('AUDACITY OpenVINO',value,parent=p.window)
                else:
                    self.failed_source=None
                    self.status.set('AUDACITY: concluído — escolha a referência ao dublar')
                    p._refresh_waveforms()
        if not finished:p.parent.after(100,self.poll)

    def choose_reference(self,default,title='Refazer cena',message='Usar esta referência para dublar?',parent=None):
        """Sim retains the ordinary reference; left-hand buttons choose a stem."""
        p=self.player
        if self.busy:
            messagebox.showinfo(title,'Aguarde o tratamento AUDACITY terminar ou cancele-o.',parent=parent or p.window)
            return False,default
        source=p._current_audio_path('original')
        paths=outputs(p.project_root,source) if source else {}
        if not paths and not (self.music.get() or self.noise.get()):
            return messagebox.askyesno(title,message,parent=parent or p.window),default
        if (self.music.get() or self.noise.get()) and ('suppression' if self.noise.get() else 'vocals') not in paths:
            messagebox.showwarning(title,'Trate o áudio original pelos botões AUDACITY antes de dublar. Nenhum áudio foi alterado.',parent=parent or p.window)
            return False,default
        window=tk.Toplevel(parent or p.window);window.title(title)
        window.configure(bg=p.theme.get('surface','#FFFFFF'))
        answer=[False,default]
        tk.Label(window,text=message+'\n\nSim: mantém a referência acima. Os botões à esquerda usam a faixa tratada.',
            wraplength=720,justify='left',bg=p.theme.get('surface','#FFFFFF'),fg=p.theme.get('text','#111827'),padx=14,pady=14).pack(fill='x')
        bar=tk.Frame(window,bg=p.theme.get('surface','#FFFFFF'));bar.pack(fill='x',padx=12,pady=12)
        def finish(ok,path):answer[:]=[ok,path];window.destroy()
        for kind in KINDS:
            tk.Button(bar,text='DUBLAR COM\n'+LABELS[kind],bg=COLORS[kind],fg='#111827',relief='flat',padx=8,pady=6,
                state='normal' if kind in paths else 'disabled',command=lambda k=kind:finish(True,paths[k])).pack(side='left',padx=3)
        tk.Button(bar,text='Não',width=7,command=lambda:finish(False,default)).pack(side='right',padx=4)
        tk.Button(bar,text='Sim',width=7,command=lambda:finish(True,default)).pack(side='right',padx=4)
        window.protocol('WM_DELETE_WINDOW',lambda:finish(False,default))
        window.transient(parent or p.window);window.grab_set();window.wait_window()
        return tuple(answer)
