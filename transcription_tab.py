"""Native transcription/translation tab using the existing managed tools."""
from __future__ import annotations
import json,queue,threading,time,os,hashlib
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import audio_translation as local
import transcription_backend as backend
import semantic_review
from translation_output import normalize_translation_output
import translation_context as context_tools
from ui_theme import apply_button_style

SUPPORTED={'.wav','.mp3','.flac','.ogg','.m4a','.mp4','.mkv','.avi','.mov','.txt'}

class GlossaryView:
    """Visual tags only: filtering never changes the saved glossary text."""
    def __init__(self,box,header):
        self.box=box;self.only_rules=tk.BooleanVar(box,value=False)
        self.toggle=ttk.Checkbutton(header,text='SOMENTE LINHAS COM =>',variable=self.only_rules,command=self.refresh)
        self.toggle.pack(side='left',padx=10)
        box.tag_configure('glossary_rule',foreground='#4ADE80')
        box.tag_configure('glossary_hidden',elide=True)
        box.bind('<<Modified>>',self.modified,add='+');box.edit_modified(False);self.refresh()
    def create_adder(self,pane,before,button_factory,bg,fg,field):
        row=tk.Frame(pane,bg=bg);row.pack(fill='x',before=before,pady=(3,5))
        row.columnconfigure(0,weight=1);row.columnconfigure(2,weight=1)
        tk.Label(row,text='Texto',bg=bg,fg=fg,anchor='w').grid(row=0,column=0,sticky='w')
        tk.Label(row,text='Referência / tradução preferida',bg=bg,fg=fg,anchor='w').grid(row=0,column=2,sticky='w')
        self.new_text=tk.Text(row,height=2,width=30,wrap='word',bg=field,fg=fg,insertbackground=fg)
        self.new_reference=tk.Text(row,height=2,width=30,wrap='word',bg=field,fg=fg,insertbackground=fg)
        self.new_text.grid(row=1,column=0,sticky='ew');self.new_reference.grid(row=1,column=2,sticky='ew')
        tk.Label(row,text='=>',bg=bg,fg='#4ADE80',font=('Segoe UI',13,'bold')).grid(row=1,column=1,padx=8)
        def add():
            try:self.add_rule(self.new_text.get('1.0','end-1c'),self.new_reference.get('1.0','end-1c'))
            except ValueError as exc:messagebox.showwarning('Adicionar ao glossário',str(exc),parent=self.box.winfo_toplevel());return
            self.new_text.delete('1.0','end');self.new_reference.delete('1.0','end');self.new_text.focus_set()
        self.add_button=button_factory(row,'ADICIONAR',add,'success');self.add_button.grid(row=1,column=3,padx=(8,0),sticky='ns')
    def add_rule(self,text,reference):
        text=' '.join(text.split());reference=' '.join(reference.split())
        if not text or not reference:raise ValueError('Preencha Texto e Referência antes de adicionar.')
        if '=>' in text+reference or '|' in text:raise ValueError('Digite os conteúdos sem o separador =>; ele é colocado automaticamente.')
        current=self.box.get('1.0','end-1c')
        rules=context_tools.glossary_rules({'glossary':current})
        if any(source.casefold()==text.casefold() for source,_,_ in rules):raise ValueError('Este texto já existe no glossário. Edite a regra existente para alterar a referência.')
        rule=text+' => '+reference
        context_tools.glossary_rules({'glossary':rule})
        addition=('\n' if current and not current.endswith('\n') else '')+'# USUÁRIO — termo incluído manualmente.\n'+rule
        if len(current)+len(addition)>20000:raise ValueError('O glossário atingiu o limite de 20.000 caracteres. Reduza o conteúdo antes de adicionar.')
        self.box.insert('end',addition);self.refresh();self.box.see('end-1c')

    def modified(self,event=None):
        if self.box.edit_modified():self.box.edit_modified(False);self.refresh()
    def refresh(self):
        box=self.box;box.tag_remove('glossary_rule','1.0','end');box.tag_remove('glossary_hidden','1.0','end')
        for index,line in enumerate(box.get('1.0','end-1c').split('\n'),1):
            start=f'{index}.0';end=f'{index+1}.0'
            if '=>' in line:box.tag_add('glossary_rule',start,f'{index}.end')
            elif self.only_rules.get():box.tag_add('glossary_hidden',start,end)

class TranscriptionApp:
    def __init__(self,parent,project_root,project_actions=None,theme=None):
        self.parent=parent;self.root=parent.winfo_toplevel();self.previews=[];self.project_root=Path(project_root);self.actions=project_actions or {};self.theme=theme or {}
        self.pause_event=threading.Event();self.theme_blink_id=None;self.theme_unread=False;self.resume_state=None
        self.running=False;self.discovering=False;self.events=queue.Queue();self.cancel_event=threading.Event();self.files=[];self.file_set=set();self.results={};self.edits={};self.shown=None
        self.relative_paths={};self.file_positions={};self.text_edits={};self.progress_values={"transcribe":0.,"translate":0.};self.stage_counts={}
        from audio_player import AudioPlayerManager
        self.audio_player=AudioPlayerManager(parent,self.project_root,status_callback=lambda text:self.status.set(text))
        self.scene_editor=None
        self.audio_player.set_scene_integration(self.select_from_player)
        self.audio_player.scene_editor_factory=self.build_scene_editor
        self.audio_player.scene_editor_refresh=self.refresh_scene_editor
        self.context=context_tools.load_context(self.project_root)
        self.config=local.load_last_settings();self.provider=tk.StringVar(parent,value=local.TRANSLATOR_LABELS[self.config['translator']]);self.review=tk.BooleanVar(parent,value=False)
        self.source=tk.StringVar(parent,value=self.config['source']);self.target=tk.StringVar(parent,value=self.config['language']);self.status=tk.StringVar(parent,value='Adicione áudio/vídeo ou TXT. Sem seleção na lista, processa todos os arquivos carregados.')
        self.no_theme=tk.BooleanVar(parent,value=self.load_ui_preferences().get('no_theme',False))
        self.context_caption=tk.StringVar(parent,value=self.theme_title())
        self.theme_headline=tk.StringVar(parent,value='Tema: '+self.theme_title())
        self.context_caption.trace_add('write',lambda *args:self.update_theme_heading())
        self.confirm_theme=tk.BooleanVar(parent,value=self.load_ui_preferences().get('confirm_theme',True))
        header=ttk.Frame(parent);header.pack(fill='x',padx=12,pady=8)
        ttk.Label(header,text='TRANSCREVER E TRADUZIR',font=('Segoe UI',14,'bold')).pack(side='left')
        self.button(header,'CHAVE / LUNA / SOL',self.configure_api).pack(side='right',padx=3)
        self.review_api_button=self.button(header,'REVISÃO SEMÂNTICA / APIs',self.configure_review_apis);self.review_api_button.pack(side='right',padx=3)
        self.local_tools_button=self.button(header,'FERRAMENTAS LOCAIS / BAIXAR',self.configure_local);self.local_tools_button.pack(side='right',padx=3)
        self.theme_heading=ttk.Label(header,textvariable=self.theme_headline,font=('Segoe UI',14,'bold'),wraplength=420);self.theme_heading.pack(side='left',padx=15)
        settings_area=ttk.Frame(parent);settings_area.pack(fill='x',padx=12,pady=3);settings_area.columnconfigure(1,weight=1)
        self.theme_button=tk.Button(settings_area,text='TEMA / JOGO /\nGLOSSÁRIO',command=self.configure_context,bg='#2DD4BF',fg='#102A2A',activebackground='#5EEAD4',activeforeground='#102A2A',relief='flat',font=('Segoe UI',9,'bold'),width=20,padx=8,pady=6)
        self.theme_button.grid(row=0,column=0,rowspan=2,sticky='nsew',padx=(0,10))
        ttk.Checkbutton(settings_area,text='SEM TEMA',variable=self.no_theme,command=self.toggle_no_theme).grid(row=2,column=0,sticky='w',padx=6)
        self.update_theme_heading()
        self.transcriber=tk.StringVar(parent,value=self.transcriber_label())
        self.asr_model=tk.StringVar(parent,value=self.config['faster_model' if self.config['engine']=='faster-whisper' else 'whisper_model'])
        self.processing=tk.StringVar(parent,value='GPU (CUDA)' if self.config['device']=='cuda' else 'CPU')
        settings=ttk.Frame(settings_area);settings.grid(row=0,column=1,sticky='ew',pady=3)
        ttk.Label(settings,text='Transcrição desta execução:').pack(side='left')
        self.transcriber_combo=ttk.Combobox(settings,textvariable=self.transcriber,values=tuple(self.TRANSCRIBERS),state='readonly',width=29);self.transcriber_combo.pack(side='left',padx=4)
        ttk.Label(settings,text='Modelo:').pack(side='left')
        self.asr_model_combo=ttk.Combobox(settings,textvariable=self.asr_model,values=local.MODELS,state='readonly',width=10);self.asr_model_combo.pack(side='left',padx=4)
        ttk.Label(settings,text='Idioma:').pack(side='left')
        ttk.Combobox(settings,textvariable=self.source,values=('auto',*(v[0] for v in local.LANGUAGES.values())),state='readonly',width=6).pack(side='left',padx=4)
        ttk.Label(settings,text='Processamento:').pack(side='left')
        ttk.Combobox(settings,textvariable=self.processing,values=('CPU','GPU (CUDA)'),state='readonly',width=13).pack(side='left',padx=4)
        self.transcriber.trace_add('write',self.transcriber_changed);self.asr_model.trace_add('write',self.transcription_changed);self.processing.trace_add('write',self.transcription_changed)
        if self.config.get('transcription_profile')=='whisper-webui-large-v3':self.asr_model_combo.configure(state='disabled')
        settings=ttk.Frame(settings_area);settings.grid(row=1,column=1,sticky='ew',pady=3)
        ttk.Label(settings,text='Tradutor desta execução:').pack(side='left')
        self.provider_combo=ttk.Combobox(settings,textvariable=self.provider,values=tuple(local.TRANSLATOR_LABELS.values()),state='readonly',width=max(len(value) for value in local.TRANSLATOR_LABELS.values())+2)
        self.provider_combo.pack(side='left',padx=4)
        self.provider.trace_add('write',self.provider_changed)
        ttk.Label(settings,text='Idioma da tradução:').pack(side='left')
        self.target_combo=ttk.Combobox(settings,textvariable=self.target,values=tuple(local.LANGUAGES),state='readonly',width=23);self.target_combo.pack(side='left',padx=4)
        self.button(settings,'CADASTRAR CHAVE',lambda:self.configure_provider_key(self.provider.get())).pack(side='left',padx=3)
        self.button(settings,'LINK ADQUIRIR CHAVE DA API',lambda:self.open_key_portal(self.provider.get())).pack(side='left',padx=3)
        ttk.Label(settings,text='Processamento:').pack(side='left',padx=(6,0))
        self.translation_processing=tk.StringVar(parent,value='GPU (auto)' if self.config.get('translation_device','auto')=='auto' else 'CPU')
        self.translation_processing_combo=ttk.Combobox(settings,textvariable=self.translation_processing,values=('CPU','GPU (auto)'),state='readonly',width=12);self.translation_processing_combo.pack(side='left',padx=4)
        self.translation_processing.trace_add('write',self.translation_device_changed);self.refresh_translation_processing()
        context_row=ttk.Frame(settings_area);context_row.grid(row=2,column=1,sticky='ew',pady=4)
        self.reviewer=tk.StringVar(parent,value='Sol — API')
        ttk.Checkbutton(context_row,text='Avaliar/revisar tradução',variable=self.review).pack(side='left',padx=6)
        ttk.Combobox(context_row,textvariable=self.reviewer,values=semantic_review.PROVIDERS,state='readonly',width=30).pack(side='left',padx=4)
        self.button(context_row,'CADASTRAR CHAVE',lambda:self.configure_provider_key(self.reviewer.get())).pack(side='left',padx=3)
        self.button(context_row,'LINK ADQUIRIR CHAVE DA API',lambda:self.open_key_portal(self.reviewer.get())).pack(side='left',padx=3)
        self.workspace=ttk.Panedwindow(parent,orient='vertical');self.workspace.pack(fill='both',expand=True,padx=12,pady=4)
        pane=ttk.Panedwindow(self.workspace,orient='horizontal');self.file_text_pane=pane;self.workspace.add(pane,weight=6)
        left=ttk.Frame(pane);right=ttk.Frame(pane);pane.add(left,weight=1);pane.add(right,weight=4)
        self.count=tk.StringVar(parent,value='0 arquivos | 0 selecionados');ttk.Label(left,textvariable=self.count).pack(anchor='w')
        self.list=tk.Listbox(left,selectmode='extended',exportselection=False,height=12);scroll=ttk.Scrollbar(left,command=self.list.yview);self.list.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.list.pack(fill='both',expand=True);self.list.bind('<<ListboxSelect>>',self.selected);self.list.bind('<Button-3>',self.context_menu);self.list.bind('<Double-Button-1>',self.play_file)
        self.quality_note=tk.StringVar(parent,value='OK = etapas concluídas; tradução exige parecer semântico sem alertas. REVISAR = aviso, falha ou tradução sem avaliação.')
        self.quality_note.trace_add('write',self.render_file_notes)
        self.enable_drop()
        editor_toolbar=ttk.Frame(right);editor_toolbar.pack(fill='x',pady=(0,3))
        ttk.Label(editor_toolbar,text='TEXTOS — EDITÁVEIS').pack(side='left')
        self.split_texts=tk.BooleanVar(parent,value=False);self.active_text='source'
        ttk.Checkbutton(editor_toolbar,text='TRÊS PAINÉIS VERTICAIS',variable=self.split_texts,command=self.rebuild_editors).pack(side='right')
        self.editor_host=ttk.Frame(right);self.editor_host.pack(fill='both',expand=True)
        self.texts={};self.notebook=None;self.text_stack=None;self.rebuild_editors()
        self.initial_dividers_set=False;self.editor_host.bind('<Map>',lambda event:self.parent.after_idle(self.position_initial_dividers),add='+')
        log_frame=ttk.Frame(self.workspace);self.workspace.add(log_frame,weight=4)
        tools=ttk.Frame(log_frame);tools.pack(fill='x',pady=(0,5))
        for label,command in [('CARREGAR WAV ORIGINAIS',self.load_originals),('ADICIONAR ARQUIVOS',self.add_files),('ADICIONAR PASTA',self.add_folder),('REMOVER SELECIONADOS',self.remove_selected),('LIMPAR JANELA',self.clear)]:self.button(tools,label,command).pack(side='left',padx=3)
        self.process_pane=ttk.Panedwindow(log_frame,orient='horizontal');self.process_pane.pack(fill='both',expand=True)
        process_area=ttk.Frame(self.process_pane);notes_area=ttk.Frame(self.process_pane);self.process_pane.add(process_area,weight=4);self.process_pane.add(notes_area,weight=1)
        ttk.Label(process_area,text='PROCESSOS — arraste a divisória para redimensionar').pack(anchor='w')
        self.log_box=tk.Text(process_area,height=12,state='disabled',wrap='word')
        log_scroll=ttk.Scrollbar(process_area,command=self.log_box.yview);self.log_box.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right',fill='y');self.log_box.pack(fill='both',expand=True)
        ttk.Label(notes_area,text='OBSERVAÇÕES DO ARQUIVO SELECIONADO',wraplength=290).pack(anchor='w')
        self.notes_caption=tk.StringVar(parent,value='Selecione um áudio ou vídeo');ttk.Label(notes_area,textvariable=self.notes_caption,wraplength=290).pack(anchor='w')
        self.file_notes=tk.Text(notes_area,height=12,width=32,state='disabled',wrap='word')
        note_scroll=ttk.Scrollbar(notes_area,command=self.file_notes.yview);self.file_notes.configure(yscrollcommand=note_scroll.set)
        note_scroll.pack(side='right',fill='y');self.file_notes.pack(fill='both',expand=True);self.render_file_notes()
        actions=ttk.Frame(parent);actions.pack(fill='x',padx=12,pady=5)
        self.job_buttons=[]
        for label,mode in [('TRANSCREVER','transcribe'),('TRADUZIR TEXTO','translate'),('TRANSCREVER E TRADUZIR','both'),('REVISAR TRADUÇÃO','review')]:
            button=self.button(actions,label,lambda m=mode:self.choose_order(m) if m!='review' else self.start(m),'primary');button.pack(side='left',padx=3);self.job_buttons.append(button)
        ttk.Checkbutton(actions,text='Confirmar tema',variable=self.confirm_theme,command=self.save_ui_preferences).pack(side='left',padx=5)
        self.button(actions,'SALVAR EDIÇÃO',self.save_current,'primary').pack(side='left',padx=3)
        self.button(actions,'EXPORTAR TXT',self.export).pack(side='left',padx=3)
        execution_controls=ttk.Frame(parent);execution_controls.pack(fill='x',padx=12,pady=2)
        ttk.Label(execution_controls,text='Pausa salva ao terminar a etapa atual. Retomada disponível após reabrir o projeto.').pack(side='left')
        self.pause_button=self.button(execution_controls,'PAUSAR',self.toggle_pause);self.pause_button.pack(side='right',padx=3)
        self.button(execution_controls,'RETOMAR DE ONDE PAROU',self.resume_saved).pack(side='right',padx=3)
        self.button(execution_controls,'CANCELAR',self.cancel,'danger').pack(side='right',padx=3)
        self.status_label=ttk.Label(parent,textvariable=self.status,wraplength=1100);self.status_label.pack(fill='x',padx=12,pady=4)
        footer=ttk.Frame(parent);footer.pack(fill='x',padx=12,pady=4)
        self.output_button=self.button(footer,'ABRIR PASTA DE SAÍDA',self.open_output);self.output_button.pack(side='right',anchor='s',padx=(10,0))
        progress_area=ttk.Frame(footer);progress_area.pack(side='left',fill='x',expand=True)
        self.bars={};self.bar_labels={}
        for stage,label in [('transcribe','Transcrição'),('translate','Tradução / revisão')]:
            row=ttk.Frame(progress_area);row.pack(fill='x',pady=2)
            self.bar_labels[stage]=tk.StringVar(parent,value=label+' — aguardando')
            ttk.Label(row,textvariable=self.bar_labels[stage],anchor='w').pack(fill='x')
            self.bars[stage]=ttk.Progressbar(row,mode='determinate',maximum=100);self.bars[stage].pack(fill='x')
        self.progress=self.bars['transcribe']
        # Reserve the fixed controls before giving the remaining height to resizable panes.
        footer.pack_configure(side='bottom',before=self.workspace)
        self.status_label.pack_configure(side='bottom',before=self.workspace)
        execution_controls.pack_configure(side='bottom',before=self.workspace)
        actions.pack_configure(side='bottom',before=self.workspace)
        self.last_output=None;self.apply_theme(self.theme);self.poll_id=parent.after(100,self.poll)
        parent.bind('<Destroy>',self.on_destroy,add='+')

    @property
    def checkpoint_path(self):return self.project_root/'revisoes'/'transcricao-traducao-pendente.json'

    def toggle_pause(self):
        if not self.running:return
        if self.pause_event.is_set():
            self.pause_event.clear();self.pause_button.configure(text='PAUSAR');self.status.set('Retomando processamento…')
        else:
            self.pause_event.set();self.pause_button.configure(text='RETOMAR');self.status.set('Pausa solicitada: a etapa em andamento termina e salva antes de pausar.')

    def wait_if_paused(self):
        while self.pause_event.is_set():
            if self.cancel_event.wait(.2):raise RuntimeError('Operação cancelada; progresso salvo para retomar.')
        if self.cancel_event.is_set():raise RuntimeError('Operação cancelada; progresso salvo para retomar.')

    def blink_theme(self):
        if self.theme_blink_id:self.parent.after_cancel(self.theme_blink_id)
        self.theme_unread=True
        def blink():
            if not self.theme_unread or not self.parent.winfo_exists():return
            color='#FBBF24' if self.theme_button.cget('bg')=='#2DD4BF' else '#2DD4BF'
            self.theme_button.configure(bg=color);self.theme_blink_id=self.parent.after(650,blink)
        blink()

    def resume_saved(self):
        if self.busy:return
        try:
            state=json.loads(self.checkpoint_path.read_text(encoding='utf-8'))
            if state.get('version')!=1 or state.get('complete'):raise ValueError('Não há execução pendente para retomar.')
            paths=[Path(x) if x else None for x in state['paths']]
            for path in paths:
                if path and (not path.is_file() or [path.stat().st_size,path.stat().st_mtime_ns]!=state['fingerprints'][str(path)]):raise ValueError('Arquivo ausente ou modificado desde a pausa: '+str(path))
            self.config.update(state['config']);self.sync_transcription_controls();self.source.set(self.config['source']);self.target.set(self.config['language']);self.provider.set(local.TRANSLATOR_LABELS[self.config['translator']]);self.review.set(state['review']);self.reviewer.set(state['review_provider'])
            self.add_paths([p for p in paths if p])
            for path in paths:
                if path:
                    self.relative_paths[path]=Path(state.get('relative_paths',{}).get(str(path),str(self.relative_paths[path])))
                    self.results[path]=dict(state['records'].get(str(path),{}))
            self.resume_state=state
            self.start(state['mode'],state['order'])
        except (OSError,ValueError,KeyError,TypeError) as exc:messagebox.showwarning('Retomar execução',str(exc),parent=self.parent)
        finally:self.resume_state=None

    def position_initial_dividers(self):
        if self.initial_dividers_set or not self.parent.winfo_exists():return
        width=self.file_text_pane.winfo_width();height=self.workspace.winfo_height()
        if width<300 or height<160:return
        self.file_text_pane.sashpos(0,int(width*.23))
        self.workspace.sashpos(0,int(height*.60))
        self.process_pane.sashpos(0,max(200,self.process_pane.winfo_width()-int(width*.23)))
        self.initial_dividers_set=True

    def render_file_notes(self,*args):
        if not hasattr(self,'file_notes'):return
        self.file_notes.configure(state='normal');self.file_notes.delete('1.0','end');self.file_notes.insert('1.0',self.quality_note.get());self.file_notes.configure(state='disabled');self.file_notes.yview_moveto(0)
        self.notes_caption.set(self.shown.name if self.shown else 'Selecione um áudio ou vídeo')

    def has_theme(self):return any(self.context.get(key,'').strip() for key in ('title','instructions','glossary','asr_hints','research'))
    def theme_title(self):return self.context.get('title','').strip() or self.context.get('domain') or 'Geral'
    def update_theme_heading(self):
        enabled=not self.no_theme.get() and self.has_theme()
        self.theme_headline.set('Tema: '+self.theme_title() if enabled else 'Sem tema')
        if hasattr(self,'theme_heading'):self.theme_heading.configure(foreground='#2DD4BF' if enabled else '#FB923C')
    def toggle_no_theme(self):self.save_ui_preferences();self.update_theme_heading()
    def effective_context(self):return dict(self.context) if not self.no_theme.get() and self.has_theme() else {}

    def load_ui_preferences(self):
        try:
            data=json.loads((self.project_root/'revisoes'/'transcription-ui.json').read_text(encoding='utf-8'))
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError):return {}
    def save_ui_preferences(self):
        try:backend.atomic_json(self.project_root/'revisoes'/'transcription-ui.json',{'confirm_theme':self.confirm_theme.get(),'no_theme':self.no_theme.get()})
        except OSError as exc:self.status.set('Não foi possível salvar a preferência: '+str(exc))
    def confirm_current_theme(self):
        if not self.confirm_theme.get() or self.no_theme.get() or not self.has_theme():return True
        return messagebox.askyesno('Conferir tema','Você já conferiu o tema?\n\nÉ este tema mesmo: “'+self.theme_title()+'”\n\nDeseja aplicá-lo à transcrição, tradução e revisão desta execução?',parent=self.parent)
    def translation_device_changed(self,*args):
        if getattr(self,'updating_translation_device',False):return
        if self.translation_processing.get() in ('CPU','GPU (auto)'):self.config['translation_device']='cpu' if self.translation_processing.get()=='CPU' else 'auto'
    def refresh_translation_processing(self):
        if not hasattr(self,'translation_processing_combo'):return
        self.updating_translation_device=True
        code=self.config['translator']
        value='API — remoto' if code in local.API_TRANSLATORS else 'CPU' if code=='argos' else 'CPU' if self.config.get('translation_device','auto')=='cpu' else 'GPU (auto)'
        self.translation_processing.set(value);self.translation_processing_combo.configure(state='disabled' if code in local.API_TRANSLATORS or code=='argos' else 'readonly')
        self.updating_translation_device=False
    def configure_provider_key(self,provider):
        if self.busy:return
        if provider.startswith(('Luna','Sol')):return self.configure_api()
        from api_settings_ui import configure
        return configure(self.parent,self.theme,provider=provider,luna_callback=self.configure_api)

    def current_text_key(self):
        if self.notebook is not None:
            return ('source','translation','revision')[self.notebook.index(self.notebook.select())]
        return self.active_text

    def rebuild_editors(self):
        # Tk widgets cannot change parents: preserve content and scroll before rebuilding.
        old={key:(box.get('1.0','end-1c'),box.yview()[0]) for key,box in self.texts.items()}
        if self.notebook is not None:self.active_text=self.current_text_key()
        for child in self.editor_host.winfo_children():child.destroy()
        self.texts={};self.notebook=None;self.text_stack=None
        if self.split_texts.get():
            container=ttk.Panedwindow(self.editor_host,orient='vertical');self.text_stack=container
        else:
            container=ttk.Notebook(self.editor_host);self.notebook=container
        container.pack(fill='both',expand=True)
        for key,label in [('source','TRANSCRIÇÃO'),('translation','TRADUÇÃO'),('revision','REVISÃO')]:
            frame=ttk.Frame(container)
            if self.split_texts.get():container.add(frame,weight=1)
            else:container.add(frame,text=label)
            row=ttk.Frame(frame);row.pack(fill='x')
            ttk.Label(row,text=label+' — EDITÁVEL').pack(side='left')
            self.button(row,'SALVAR EDIÇÃO',lambda name=key:self.save_current(name),'primary').pack(side='right',padx=3)
            body=ttk.Frame(frame);body.pack(fill='both',expand=True)
            box=tk.Text(body,wrap='word',height=3 if self.split_texts.get() else 14,undo=True)
            bar=ttk.Scrollbar(body,command=box.yview);box.configure(yscrollcommand=bar.set)
            bar.pack(side='right',fill='y');box.pack(fill='both',expand=True)
            box.insert('1.0',old.get(key,('',0))[0]);box.yview_moveto(old.get(key,('',0))[1])
            box.bind('<FocusIn>',lambda event,name=key:setattr(self,'active_text',name))
            box.bind('<<Modified>>',lambda event,name=key:self.main_text_changed(name));box.edit_modified(False)
            if self.running:box.configure(state='disabled')
            self.texts[key]=box
        if self.notebook is not None:self.notebook.select(('source','translation','revision').index(self.active_text))
        self.apply_theme(self.theme)

    def on_destroy(self,event):
        if event.widget is self.parent and self.theme_blink_id:
            self.parent.after_cancel(self.theme_blink_id);self.theme_blink_id=None;self.theme_unread=False
        if event.widget is not self.parent:return
        self.cancel_event.set()
        self.audio_player.stop(announce=False)
        for preview in self.previews:
            if not preview.closed:preview.close()
        try:self.parent.after_cancel(self.poll_id)
        except tk.TclError:pass

    def button(self,parent,text,command,role='secondary'):
        button=tk.Button(parent,text=text,command=command,relief='flat',font=('Segoe UI',8,'bold'),padx=6,pady=5)
        apply_button_style(button,self.theme,role);return button

    def apply_theme(self,theme):
        self.theme=theme or {}
        if hasattr(self,'audio_player'):self.audio_player.apply_theme(self.theme)
        for preview in getattr(self,'previews',[]):
            if not preview.closed:preview.apply_theme(self.theme)
        for box in [*getattr(self,'texts',{}).values(),getattr(self,'log_box',None),getattr(self,'file_notes',None),getattr(self,'list',None)]:
            if box is not None:
                box.configure(bg=self.theme.get('input','#FFFFFF'),fg=self.theme.get('input_text',self.theme.get('text','#111827')),selectbackground=self.theme.get('select','#2563EB'))
                if isinstance(box,tk.Text):box.configure(insertbackground=self.theme.get('input_text',self.theme.get('text','#111827')))
        def buttons(widget):
            for child in widget.winfo_children():
                if isinstance(child,tk.Button):apply_button_style(child,self.theme)
                buttons(child)
        buttons(self.parent)
        if hasattr(self,'theme_button'):self.theme_button.configure(bg='#2DD4BF',fg='#102A2A',activebackground='#5EEAD4',activeforeground='#102A2A')

    @property
    def busy(self):return self.running or self.discovering
    def refresh_for_project(self):pass
    def cancel(self):
        self.cancel_event.set();self.status.set('Cancelando… chamadas API em andamento encerram ao responder ou atingir o tempo limite.')
    TRANSCRIBERS={'Faster-Whisper':'faster-whisper','Whisper (OpenAI)':'openai-whisper','Whisper-WebUI / large-v3 (local)':local.WEBUI_LOCAL_PROFILE}
    def transcriber_label(self):
        if self.config.get('transcription_profile')=='whisper-webui-large-v3':return 'Whisper-WebUI / large-v3 (local)'
        return 'Faster-Whisper' if self.config['engine']=='faster-whisper' else 'Whisper (OpenAI)'
    def transcription_changed(self,*args):
        if getattr(self,'syncing_transcriber',False):return
        key='faster_model' if self.config['engine']=='faster-whisper' else 'whisper_model'
        self.config[key]=self.asr_model.get();self.config['device']='cuda' if self.processing.get()=='GPU (CUDA)' else 'cpu'
    def transcriber_changed(self,*args):
        if getattr(self,'syncing_transcriber',False):return
        engine=self.TRANSCRIBERS[self.transcriber.get()];self.syncing_transcriber=True
        if engine==local.WEBUI_LOCAL_PROFILE:self.config.update(engine='faster-whisper',faster_model='large-v3',transcription_profile='whisper-webui-large-v3')
        else:self.config['engine']=engine;self.config.pop('transcription_profile',None)
        self.asr_model.set(self.config['faster_model' if self.config['engine']=='faster-whisper' else 'whisper_model'])
        self.asr_model_combo.configure(state='disabled' if engine==local.WEBUI_LOCAL_PROFILE else 'readonly');self.syncing_transcriber=False
    def sync_transcription_controls(self):
        self.syncing_transcriber=True
        self.transcriber.set(self.transcriber_label());self.asr_model.set(self.config['faster_model' if self.config['engine']=='faster-whisper' else 'whisper_model'])
        self.processing.set('GPU (CUDA)' if self.config['device']=='cuda' else 'CPU')
        self.asr_model_combo.configure(state='disabled' if self.config.get('transcription_profile')=='whisper-webui-large-v3' else 'readonly');self.syncing_transcriber=False

    def provider_changed(self,*args):
        value=self.provider.get()
        code=next((code for code,label in local.TRANSLATOR_LABELS.items() if value==label),None)
        if code is None:
            code='luna-api' if value.startswith('Luna') else 'sol-api' if value.startswith('Sol') else 'qwen-game-local' if value.startswith('IA local') else None
        if code:self.config['translator']=code
        self.refresh_translation_processing()

    def configure_local(self):
        if self.busy:return
        # The tools dialog and main selector represent one choice, not two translators.
        self.provider_changed()
        try:local.save_last_settings(dict(self.config,source=self.source.get(),language=self.target.get()))
        except OSError as exc:messagebox.showerror('Salvar configuração',str(exc),parent=self.parent);return
        value=local.choose_settings(self.parent,self.config,workspace=True)
        if value:
            self.config=value;self.source.set(value['source']);self.target.set(value['language'])
            self.provider.set(local.TRANSLATOR_LABELS[value['translator']]);self.sync_transcription_controls();self.refresh_translation_processing()
    def use_large_v3(self):
        if self.busy:return
        self.config.update(engine='faster-whisper',faster_model='large-v3',whisper_model='large-v3')
        local.save_last_settings(self.config)
        self.status.set('Perfil Faster-Whisper large-v3 selecionado. FERRAMENTAS LOCAIS / BAIXAR prepara o modelo e permite escolher CPU/GPU.')

    def configure_context(self):
        self.theme_unread=False
        if self.theme_blink_id:self.parent.after_cancel(self.theme_blink_id);self.theme_blink_id=None
        self.theme_button.configure(bg='#2DD4BF')
        if self.busy:return
        window=tk.Toplevel(self.parent);window.title('Tema, jogo e terminologia do projeto');window.geometry(f'{min(1120,window.winfo_screenwidth()-50)}x{min(880,window.winfo_screenheight()-80)}');window.minsize(720,620)
        bg=self.theme.get('surface','#202B3B');fg=self.theme.get('text','#F8FAFC');field=self.theme.get('input','#111827')
        window.configure(bg=bg)
        tools=tk.Frame(window,bg=bg)
        preset=tk.StringVar(window,value=self.context.get('preset','Geral'))
        title=tk.StringVar(window,value=self.context.get('title',''));domain=tk.StringVar(window,value=self.context.get('domain','Geral'));model=tk.StringVar(window,value=self.context.get('ollama_model') or 'qwen2.5:7b');enforce=tk.BooleanVar(window,value=self.context.get('enforce_terms',True))
        row=tk.Frame(window,bg=bg);row.pack(fill='x',padx=12,pady=7)
        tk.Label(row,text='Perfil:',bg=bg,fg=fg).pack(side='left')
        choice=ttk.Combobox(row,textvariable=preset,values=tuple(context_tools.PRESETS),state='readonly',width=24);choice.pack(side='left',padx=6)
        tk.Label(row,text='Tipo:',bg=bg,fg=fg).pack(side='left')
        ttk.Combobox(row,textvariable=domain,values=('Geral','Jogo','Filme','Documentário','Personalizado'),width=20).pack(side='left',padx=6)
        self.button(row,'RESETAR TEMA SALVO',lambda:reset_theme()).pack(side='left',padx=3)
        self.button(row,'EXPORTAR TEMA PRESENTE',lambda:export_theme()).pack(side='left',padx=3)
        self.button(row,'IMPORTAR TEMA',lambda:import_theme()).pack(side='left',padx=3)
        row=tk.Frame(window,bg=bg);row.pack(fill='x',padx=12,pady=5)
        tk.Label(row,text='Jogo / filme / tema:',bg=bg,fg=fg).pack(side='left')
        tk.Entry(row,textvariable=title,bg=field,fg=fg,insertbackground=fg).pack(side='left',fill='x',expand=True,padx=6)
        footer=tk.Frame(window,bg=bg);footer.pack(side='bottom',fill='x',padx=12,pady=8)
        text_area=ttk.Panedwindow(window,orient='vertical');text_area.pack(fill='both',expand=True,padx=12,pady=3)
        boxes={}
        for key,label,height in [('instructions','Contexto e instruções de tradução/revisão',3),('glossary','Glossário: origem => termo preferido | variantes a evitar (uma regra por linha)',7),('asr_hints','Vocabulário original para ajudar o Whisper (não é tradução)',2)]:
            pane=tk.Frame(text_area,bg=bg);text_area.add(pane,weight=5 if key=='glossary' else 2)
            editor_heading=tk.Frame(pane,bg=bg);editor_heading.pack(fill='x',pady=(3,1))
            tk.Label(editor_heading,text=label,bg=bg,fg=fg,anchor='w').pack(side='left')
            editor=tk.Frame(pane,bg=bg);editor.pack(fill='both',expand=True)
            box=tk.Text(editor,height=height,wrap='word',bg=field,fg=fg,insertbackground=fg);scroll=ttk.Scrollbar(editor,command=box.yview);box.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');box.pack(fill='both',expand=True);box.insert('1.0',self.context.get(key,''));boxes[key]=box
            if key=='glossary':
                box.glossary_view=GlossaryView(box,editor_heading)
                box.glossary_view.create_adder(pane,editor,self.button,bg,fg,field)
        tk.Checkbutton(window,text='Aplicar variantes preferidas na tradução quando o termo original aparecer',variable=enforce,bg=bg,fg=fg,selectcolor=field,activebackground=bg,activeforeground=fg).pack(anchor='w',padx=12,pady=4)
        import theme_research
        research_provider=tk.StringVar(window,value=self.context.get('research_provider') or 'OpenAI / ChatGPT — API')
        research_mode=tk.StringVar(window,value='local' if research_provider.get().startswith('IA local') else 'api')
        if research_provider.get().startswith('IA local'):research_provider.set('OpenAI / ChatGPT — API')
        engines=tk.Frame(window,bg=bg);engines.pack(fill='x',padx=12,pady=4)
        controls=tk.Frame(engines,bg=bg);controls.pack(side='left',fill='x',expand=True)
        local_row=tk.Frame(controls,bg=bg);local_row.pack(fill='x',pady=2)
        ttk.Radiobutton(local_row,text='IA LOCAL (Ollama)',variable=research_mode,value='local').pack(side='left')
        local_combo=ttk.Combobox(local_row,textvariable=model,values=('qwen2.5:7b','qwen2.5:3b'),width=25);local_combo.pack(side='left',padx=6)
        api_row=tk.Frame(controls,bg=bg);api_row.pack(fill='x',pady=2)
        ttk.Radiobutton(api_row,text='IA POR API — pesquisar o tema',variable=research_mode,value='api').pack(side='left')
        api_combo=ttk.Combobox(api_row,textvariable=research_provider,values=theme_research.PROVIDERS[:-1],state='readonly',width=25);api_combo.pack(side='left',padx=5)
        register=self.button(api_row,'CADASTRAR / ATIVAR API',lambda:self.configure_provider_key(research_provider.get()));register.pack(side='left',padx=3)
        research_controls=engines
        def mode_changed(*args):
            local=research_mode.get()=='local';local_combo.configure(state='normal' if local else 'disabled');api_combo.configure(state='disabled' if local else 'readonly');register.configure(state='disabled' if local else 'normal')
        research_mode.trace_add('write',mode_changed);mode_changed()
        tk.Label(window,text='O tema orienta a IA, mas não cria conhecimento oficial do jogo. A transcrição continua fiel ao áudio. Argos aplica o glossário; raciocínio contextual exige IA local ou API.',bg=bg,fg=fg,wraplength=810,justify='left').pack(fill='x',padx=12,pady=5)
        def load_preset(event=None):
            value=context_tools.PRESETS[preset.get()];title.set(value['title']);domain.set(value['domain'])
            for key,box in boxes.items():box.delete('1.0','end');box.insert('1.0',value[key])
        choice.bind('<<ComboboxSelected>>',load_preset)
        def values_snapshot():
            return {'preset':preset.get(),'title':title.get(),'domain':domain.get(),'ollama_model':model.get(),'enforce_terms':enforce.get(),'research_provider':'IA local — Ollama' if research_mode.get()=='local' else research_provider.get(),'research':research_notes[0] if research_title[0]==title.get().strip() else '',**{key:box.get('1.0','end-1c') for key,box in boxes.items()}}
        known_rules={line.strip() for line in self.context.get('glossary','').splitlines() if '=>' in line and not line.lstrip().startswith('#')}
        def save():
            if self.busy:return False
            values=values_snapshot()
            values['glossary']=theme_research.mark_manual_changes(values['glossary'],known_rules)
            try:self.context=context_tools.save_context(self.project_root,values)
            except Exception as exc:messagebox.showerror('Tema',str(exc),parent=window);return False
            self.no_theme.set(False);self.save_ui_preferences();self.context_caption.set(self.theme_title())
            window.destroy();return True
        research_notes=[self.context.get('research','')]
        research_title=[self.context.get('title','')]
        research_events=queue.Queue()
        def research():
            if self.busy:return
            query=title.get().strip();provider='IA local — Ollama' if research_mode.get()=='local' else research_provider.get()
            if not query:messagebox.showwarning('Pesquisa','Informe o jogo, filme ou tema.',parent=window);return
            if not provider.startswith(('IA local','Luna','Sol')) and not semantic_review.ready(provider):messagebox.showwarning('Pesquisa','Configure a chave e o modelo da IA escolhida em CADASTRAR / ATIVAR API.',parent=window);return
            if provider.startswith(('Luna','Sol')) and not backend.load_key():messagebox.showwarning('Pesquisa','Configure a chave Luna/Sol antes de pesquisar.',parent=window);return
            snapshot={'domain':domain.get(),'model':model.get(),'instructions':boxes['instructions'].get('1.0','end-1c')}
            research_button.configure(state='disabled');research_status.set('Coletando fontes on-line e preparando análise com '+provider+'…')
            self.running=True;self.cancel_event.clear()
            def worker():
                try:
                    sources,result=theme_research.deep_research(query,snapshot['domain'],provider,lambda text:self.events.put(('log',text)),self.cancel_event.is_set,snapshot['model'],snapshot['instructions'])
                    research_events.put(('ok',(sources,result)))
                except Exception as exc:research_events.put(('error',str(exc)))
            def poll_research():
                try:kind,value=research_events.get_nowait()
                except queue.Empty:
                    if self.parent.winfo_exists():self.parent.after(100,poll_research)
                    return
                self.running=False
                if not window.winfo_exists():return
                research_button.configure(state='normal')
                if kind=='error':research_status.set(value);return
                sources,result=value
                preview=tk.Toplevel(window);preview.title('Pesquisa do tema — confira contexto, termos e evidências');preview.geometry('1000x780')
                body=ttk.Frame(preview,padding=10);body.pack(fill='both',expand=True)
                notebook=ttk.Notebook(body);notebook.pack(fill='both',expand=True)
                editors={}
                values={'instructions':result['instructions'],'glossary':theme_research.glossary_text(result),'asr_hints':', '.join(result['asr_hints']),'evidence':theme_research.dossier(result,sources,provider)}
                for key,label in [('instructions','CONTEXTO / ORIENTAÇÕES'),('glossary','GLOSSÁRIO PROPOSTO'),('asr_hints','VOCABULÁRIO ORIGINAL'),('evidence','FONTES / EVIDÊNCIAS / INCERTEZAS')]:
                    page=ttk.Frame(notebook);notebook.add(page,text=label)
                    text=tk.Text(page,wrap='word',bg=field,fg=fg,insertbackground=fg);scroll=ttk.Scrollbar(page,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True);text.insert('1.0',values[key]);editors[key]=text
                ttk.Label(body,text='Termos proposed são sugestões de adaptação, não localização oficial. Confira obra/edição e as fontes. Aplicar acrescenta às suas regras; nada é alterado antes disso.',wraplength=940).pack(fill='x',pady=8)
                def apply():
                    if title.get().strip()!=query:messagebox.showwarning('Tema alterado','O título mudou durante a pesquisa. Pesquise novamente para aplicar ao tema correto.',parent=preview);return
                    raw_rules=editors['glossary'].get('1.0','end-1c').strip()
                    rules=theme_research.mark_manual_changes(raw_rules,{line.strip() for line in values['glossary'].splitlines() if '=>' in line and not line.lstrip().startswith('#')})
                    editors['glossary'].delete('1.0','end');editors['glossary'].insert('1.0',rules)
                    try:context_tools.glossary_rules({'glossary':rules})
                    except ValueError as exc:messagebox.showerror('Glossário',str(exc),parent=preview);return
                    for key in ('instructions','glossary','asr_hints'):
                        value=editors[key].get('1.0','end-1c').strip()
                        if value:boxes[key].insert('end',('\n' if boxes[key].get('1.0','end-1c').strip() else '')+value)
                    known_rules.update(line.strip() for line in rules.splitlines() if '=>' in line and not line.lstrip().startswith('#'))
                    research_notes[0]=sources;research_title[0]=query
                    folder=self.project_root/'revisoes'/'pesquisa_tema';folder.mkdir(parents=True,exist_ok=True)
                    backend.atomic_json(folder/(str(time.time_ns())+'.json'),{'title':query,'provider':provider,'sources':sources,'proposal':result,'applied':{key:editors[key].get('1.0','end-1c') for key in editors}})
                    preview.destroy();research_status.set('Proposta aplicada aos campos. Clique SALVAR TEMA para usar na transcrição, tradução e revisão.')
                self.button(body,'APLICAR CONTEXTO E GLOSSÁRIO',apply,'primary').pack(side='right',pady=5)
                from ui_theme import theme_dialog
                theme_dialog(preview,self.theme)
                research_status.set('Pesquisa concluída com '+provider+'. Confira a proposta e as evidências na janela aberta.')
            threading.Thread(target=worker,daemon=True).start();self.parent.after(100,poll_research)
        research_status=tk.StringVar(window,value='Pesquisa aprofundada em categorias + rodada complementar; pode executar até 5 análises de IA e gerar cobrança de API. Resumos web são referências, não prova de localização oficial. IA local ou API conforme ativado. Confira evidências antes de aplicar.')
        research_button=self.button(research_controls,'PESQUISAR TEMA\nNA INTERNET',research,'success');research_button.configure(bg='#22C55E',fg='#052E16',activebackground='#4ADE80',font=('Segoe UI',11,'bold'),width=24,pady=14);research_button.pack(side='left',fill='both',expand=True,padx=6)
        self.button(research_controls,'CANCELAR\nPESQUISA',self.cancel_event.set,'danger').pack(side='left',fill='y',padx=3)
        tk.Label(window,textvariable=research_status,bg=bg,fg=fg,wraplength=810,justify='left').pack(fill='x',padx=12)
        def prepare():
            if self.busy:return
            selected_model=model.get().strip()
            self.running=True;self.cancel_event.clear();prepare_button.configure(state='disabled')
            def worker():
                try:backend.prepare_local_ai(selected_model,lambda value:self.events.put(('log',value)),self.cancel_event.is_set);done='IA local preparada.'
                except Exception as exc:done='ERRO: '+str(exc)
                research_events.put(('prepare_done',done))
            def poll_prepare():
                try:kind,message=research_events.get_nowait()
                except queue.Empty:
                    if self.parent.winfo_exists():self.parent.after(100,poll_prepare)
                    return
                self.running=False;self.events.put(('log',message))
                if window.winfo_exists():prepare_button.configure(state='normal');research_status.set(message)
            threading.Thread(target=worker,daemon=True).start();self.parent.after(100,poll_prepare)
        prepare_button=self.button(local_row,'PREPARAR IA LOCAL',prepare);prepare_button.pack(side='left',padx=3)
        self.button(footer,'SALVAR TEMA',save,'primary').pack(side='right',padx=3)
        baseline=values_snapshot()
        def fill_theme(value):
            preset.set(value.get('preset','Geral'));title.set(value.get('title',''));domain.set(value.get('domain','Geral'));model.set(value.get('ollama_model') or 'qwen2.5:7b');enforce.set(value.get('enforce_terms',True))
            for key,box in boxes.items():box.delete('1.0','end');box.insert('1.0',value.get(key,''))
            provider=value.get('research_provider') or 'OpenAI / ChatGPT — API';research_mode.set('local' if provider.startswith('IA local') else 'api')
            if not provider.startswith('IA local'):research_provider.set(provider)
            research_notes[0]=value.get('research','');research_title[0]=value.get('title','')
        def reset_theme():
            nonlocal baseline
            if self.busy:return
            if not messagebox.askyesno('Resetar tema','Remover o contexto, glossário, vocabulário e pesquisa do tema salvo neste projeto?',parent=window):return
            try:self.context=context_tools.save_context(self.project_root,dict(context_tools.DEFAULTS))
            except OSError as exc:messagebox.showerror('Tema',str(exc),parent=window);return
            fill_theme(self.context);baseline=values_snapshot();self.context_caption.set(self.theme_title());self.update_theme_heading();research_status.set('Tema salvo resetado. Nenhum tema será aplicado até cadastrar um novo.')
        def export_theme():
            value=values_snapshot()
            try:context_tools.glossary_rules(value)
            except ValueError as exc:messagebox.showerror('Tema',str(exc),parent=window);return
            file=filedialog.asksaveasfilename(parent=window,title='Exportar tema presente',initialfile='tema.json',defaultextension='.json',filetypes=[('Tema Dublaskizon','*.json')])
            if not file:return
            try:backend.atomic_json(Path(file),{'format':'dublaskizon-theme','version':1,'theme':context_tools.normalized_context(value)})
            except OSError as exc:messagebox.showerror('Exportar tema',str(exc),parent=window)
        def import_theme():
            if self.busy:return
            file=filedialog.askopenfilename(parent=window,title='Importar tema',filetypes=[('Tema Dublaskizon','*.json')])
            if not file:return
            try:
                path=Path(file)
                if path.stat().st_size>500000:raise ValueError('Arquivo de tema muito grande.')
                data=json.loads(path.read_text(encoding='utf-8-sig'));value=data.get('theme',data) if isinstance(data,dict) else None
                if not isinstance(value,dict) or not any(key in value for key in ('title','glossary','instructions')):raise ValueError('Arquivo não contém um tema válido.')
                value=context_tools.normalized_context(value);context_tools.glossary_rules(value)
            except (OSError,ValueError) as exc:messagebox.showerror('Importar tema',str(exc),parent=window);return
            known_rules.update(line.strip() for line in value.get('glossary','').splitlines() if '=>' in line and not line.lstrip().startswith('#'))
            fill_theme(value);research_status.set('Tema importado nos campos. Confira e clique SALVAR TEMA para ativar.')

        def close():
            if self.busy:messagebox.showinfo('Em andamento','Cancele a pesquisa/preparação e aguarde terminar antes de fechar.',parent=window);return
            if values_snapshot()!=baseline:
                if messagebox.askyesno('Salvar tema','Há alterações não salvas. Deseja salvar o tema antes de fechar?',parent=window):
                    save();return
            window.destroy()
        window.protocol('WM_DELETE_WINDOW',close)
        # Text panes are packed last for allocation, keeping all fixed controls visible.
        text_area.pack_forget();text_area.pack(fill='both',expand=True,padx=12,pady=3)
        def size_editors():
            if not window.winfo_exists():return
            height=text_area.winfo_height()
            if height>120:text_area.sashpos(0,int(height*.27));text_area.sashpos(1,int(height*.78))
        window.after_idle(size_editors)
        return window

    def choose_batch_theme(self):
        if self.busy:
            messagebox.showinfo('Tema','Aguarde a operação atual de transcrição/tradução terminar.',parent=self.parent);return None
        window=self.configure_context()
        if window is not None:
            window.transient(self.parent.winfo_toplevel());window.grab_set();self.parent.wait_window(window)
        return self.effective_context()

    def configure_review_apis(self):
        if self.busy:return
        from api_settings_ui import configure
        return configure(self.parent,self.theme,luna_callback=self.configure_api,local_callback=self.configure_local,context_callback=self.configure_context)

    def configure_api(self):
        if self.busy:return
        window=tk.Toplevel(self.parent);window.title('Luna / Sol — chave e modelos do provedor');window.geometry('780x440')
        surface=self.theme.get('surface','#202B3B');fg=self.theme.get('text','#F8FAFC');window.configure(bg=surface)
        config=backend.api_settings();variables={key:tk.StringVar(window,value=value) for key,value in config.items() if key in backend.API_DEFAULTS};variables['key']=tk.StringVar(window,value=backend.load_key())
        for key,label in [('base_url','URL base da API'),('luna_model','Modelo Luna — tradução'),('sol_model','Modelo Sol — revisão'),('key','Chave da API')]:
            row=tk.Frame(window,bg=surface);row.pack(fill='x',padx=12,pady=8)
            tk.Label(row,text=label,width=27,anchor='w',bg=surface,fg=fg).pack(side='left')
            if key=='key':self.button(row,'LINK ADQUIRIR CHAVE DA API',lambda:self.open_key_portal('Luna')).pack(side='right',padx=(8,0))
            tk.Entry(row,textvariable=variables[key],show='•' if key=='key' else '',bg=self.theme.get('input','#111827'),fg=fg,insertbackground=fg).pack(side='left',fill='x',expand=True)
        tk.Label(window,text='Use o identificador de modelo aceito pelo seu provedor. Luna/Sol podem ser aliases.\nA API envia o texto ao provedor e pode ter cobrança. A chave é protegida pelo Windows neste computador.',bg=surface,fg=fg,wraplength=680,justify='left').pack(fill='x',padx=12,pady=8)
        def import_file():
            path=filedialog.askopenfilename(parent=window,title='Importar configuração .env',filetypes=[('Configuração','.env'),('Todos','*.*')])
            if path:
                try:
                    for key,value in backend.import_env(Path(path)).items():variables[key].set(value)
                except Exception:messagebox.showerror('Importar','Não foi possível ler a configuração.',parent=window)
        def save():
            try:backend.save_api({k:variables[k].get() for k in backend.API_DEFAULTS},variables['key'].get())
            except Exception as exc:messagebox.showerror('Configuração',str(exc),parent=window);return
            window.destroy()
        row=tk.Frame(window,bg=surface);row.pack(fill='x',padx=12,pady=12)
        self.button(row,'IMPORTAR .ENV',import_file).pack(side='left')
        self.button(row,'LIMPAR CHAVE',lambda:variables['key'].set('')).pack(side='left',padx=6)
        self.button(row,'SALVAR E ATIVAR',save,'primary').pack(side='right')
        status=tk.StringVar(window,value='Verificar modelos consulta disponibilidade, sem enviar textos para tradução.')
        tk.Label(window,textvariable=status,bg=surface,fg=fg,wraplength=680,justify='left').pack(fill='x',padx=12,pady=4)
        def verify():
            values={key:variables[key].get() for key in backend.API_DEFAULTS};credential=variables['key'].get()
            verify_button.configure(state='disabled');status.set('Verificando acesso aos modelos…')
            events=queue.Queue()
            def worker():
                try:events.put(backend.check_models(values,credential))
                except Exception as exc:events.put(str(exc))
            def poll():
                if not window.winfo_exists():return
                try:message=events.get_nowait()
                except queue.Empty:window.after(100,poll);return
                status.set(message);verify_button.configure(state='normal')
            threading.Thread(target=worker,daemon=True).start();window.after(100,poll)
        verify_button=self.button(row,'VERIFICAR MODELOS',verify);verify_button.pack(side='left',padx=6)


    def add_files(self):
        if self.busy:return
        paths=filedialog.askopenfilenames(parent=self.parent,title='Áudios, vídeos ou textos',filetypes=[('Áudio / vídeo / TXT','*.wav *.mp3 *.flac *.ogg *.m4a *.mp4 *.mkv *.avi *.mov *.txt'),('Todos','*.*')])
        self.add_paths(map(Path,paths))
    def enable_drop(self):
        try:
            from tkinterdnd2 import DND_FILES
            self.list.drop_target_register(DND_FILES)
            self.list.dnd_bind('<<Drop>>',self.drop)
        except (ImportError,AttributeError,tk.TclError):
            # Plain Tk used by embedded hosts: try loading the optional Tcl bridge.
            try:
                import tkinterdnd2
                tkinterdnd2.TkinterDnD._require(self.parent.winfo_toplevel())
                self.list.drop_target_register('DND_Files');self.list.dnd_bind('<<Drop>>',self.drop)
            except (ImportError,AttributeError,tk.TclError):pass
    def drop(self,event):
        if self.busy:return
        paths=[Path(value) for value in self.parent.tk.splitlist(event.data)]
        self.discover_paths(paths)
    def relative_name(self,path,root=None):
        if root is not None:return path.relative_to(root)
        try:return path.relative_to(self.project_root/'WAV ORIGINAIS')
        except ValueError:return Path(path.name)
    def add_paths(self,paths,root=None):
        destinations={r.with_suffix('.txt') for r in self.relative_paths.values()}
        for path in paths:
            path=Path(path)
            if path.suffix.lower() in SUPPORTED and path.is_file() and path not in self.file_set:
                relative=self.relative_name(path,root)
                # Same-named files from different sources must never overwrite each other.
                if relative.with_suffix('.txt') in destinations:
                    relative=Path(path.parent.name+'_'+hashlib.sha256(str(path).encode()).hexdigest()[:8])/relative
                destinations.add(relative.with_suffix('.txt'))
                self.relative_paths[path]=relative
                self.file_positions[path]=len(self.files);self.file_set.add(path);self.files.append(path);self.list.insert('end',str(relative))
        self.update_count()
    def load_originals(self):
        if self.busy:return
        directory=self.project_root/'WAV ORIGINAIS'
        if not directory.is_dir():
            messagebox.showwarning('WAV ORIGINAIS','A pasta WAV ORIGINAIS não existe no projeto atual.',parent=self.parent);return
        self.discover_paths([directory],allowed=SUPPORTED-{'.txt'},root_override=directory)

    def add_folder(self):
        if self.busy:return
        path=filedialog.askdirectory(parent=self.parent,title='Pasta de áudio/vídeo ou TXT',initialdir=str(self.project_root/'WAV ORIGINAIS'))
        if not path:return
        self.discover_paths([Path(path)])
    def discover_paths(self,paths,*,allowed=None,root_override=None):
        if self.busy:return
        allowed=frozenset(SUPPORTED if allowed is None else allowed)
        self.discovering=True;self.cancel_event.clear();self.status.set('Localizando arquivos… CANCELAR interrompe a busca.')
        def discover():
            try:
                for entry in paths:
                    if self.cancel_event.is_set():break
                    root=root_override if root_override is not None else entry.parent if entry.is_dir() else None
                    candidates=entry.rglob('*') if entry.is_dir() else [entry]
                    chunk=[]
                    for file in candidates:
                        if self.cancel_event.is_set():break
                        if file.is_file() and file.suffix.lower() in allowed:
                            chunk.append(file)
                            if len(chunk)>=200:self.events.put(('add',chunk,root));chunk=[]
                    if chunk:self.events.put(('add',chunk,root))
            except OSError as exc:self.events.put(('log','Falha ao listar pasta: '+str(exc)))
            finally:self.events.put(('scan_done',None))
        threading.Thread(target=discover,daemon=True).start()
    def remember_edits(self):
        self.text_edits[self.shown]={name:box.get('1.0','end-1c') for name,box in self.texts.items()}
        if self.shown is not None:self.edits[self.shown]=self.text_edits[self.shown]['source']
    def remove_selected(self):
        if self.busy:return
        self.remember_edits()
        for index in reversed(self.list.curselection()):
            key=self.files.pop(index);self.file_set.discard(key);self.relative_paths.pop(key,None);self.results.pop(key,None);self.edits.pop(key,None);self.text_edits.pop(key,None);self.list.delete(index)
            if self.shown==key:
                self.shown=None
                for box in self.texts.values():box.delete('1.0','end')
        self.file_positions={path:index for index,path in enumerate(self.files)};self.update_count()
    def reset_progress(self,totals=None):
        self.stage_counts={stage:{'total':int((totals or {}).get(stage,0)),'current':0,'finished':set(),'failed':set(),'skipped':set()} for stage in self.bars}
        for stage,bar in self.bars.items():
            self.progress_values[stage]=0.;bar.configure(value=0);self.render_progress_label(stage)
    def render_progress_label(self,stage):
        label='Transcrição' if stage=='transcribe' else 'Tradução / revisão'
        counts=self.stage_counts.get(stage,{})
        total=counts.get('total',0)
        if not total:
            self.bar_labels[stage].set(label+' — aguardando / não solicitado');return
        finished=len(counts['finished']);remaining=max(0,total-finished)
        extra=(f" | falhas {len(counts['failed'])}" if counts['failed'] else '')+(f" | pulados {len(counts['skipped'])}" if counts['skipped'] else '')
        self.bar_labels[stage].set(f"{label} — arquivo {counts['current']}/{total} | processados {finished}/{total} | faltam {remaining}{extra} — {self.progress_values[stage]:.0f}%")
    def update_stage_item(self,stage,index,state):
        counts=self.stage_counts.get(stage)
        if not counts or not 1<=index<=counts['total']:return
        counts['current']=max(counts['current'],index)
        if state in ('done','failed','skipped'):counts['finished'].add(index)
        if state=='failed':counts['failed'].add(index)
        if state=='skipped':counts['skipped'].add(index)
        self.render_progress_label(stage)
    def advance_progress(self,stage,value):
        value=max(self.progress_values[stage],min(100,max(0,value)))
        self.progress_values[stage]=value;self.bars[stage].configure(value=value);self.render_progress_label(stage)
    def final_path(self,path,translated=False):
        relative=self.relative_paths.get(path,Path('texto_editavel.txt'))
        return self.project_root/'TRANSCRIÇÕES E TRADUÇÕES'/('TRADUÇÕES' if translated else 'TRANSCRIÇÕES')/relative.with_suffix('.txt')
    @staticmethod
    def write_final(path,text):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+'.'+str(time.time_ns())+'.tmp')
        try:temporary.write_text(text.rstrip()+'\n',encoding='utf-8');os.replace(temporary,path)
        finally:temporary.unlink(missing_ok=True)
    def save_current(self,name=None):
        if self.busy:return
        name=name or self.current_text_key()
        record=self.results.get(self.shown,{})
        path=record.get('paths',{}).get(name)
        if not path:messagebox.showwarning('Salvar','Ainda não existe TXT finalizado nesta guia. Gere o resultado ou use EXPORTAR TXT.',parent=self.parent);return
        text=self.texts[name].get('1.0','end-1c')
        try:self.write_final(Path(path),text)
        except OSError as exc:messagebox.showerror('Salvar',str(exc),parent=self.parent);return
        record[{'source':'transcript','translation':'translation','revision':'revision'}[name]]=text
        if name in ('translation','revision') and record.get('paths',{}).get('translation')==record.get('paths',{}).get('revision'):
            record['translation']=text;record['revision']=text
            for other in ('translation','revision'):
                self.texts[other].delete('1.0','end');self.texts[other].insert('1.0',text)
        record.pop('semantic_review',None);record['status']='review'
        record['quality_warnings']=list(record.get('asr_warnings',[]))+['Texto editado; refaça a avaliação semântica.']
        self.update_file_state(self.shown,'review');self.quality_note.set('Texto editado; refaça a avaliação semântica.')
        metadata=record.get('metadata_path')
        if metadata:
            try:
                previous=json.loads(Path(metadata).read_text(encoding='utf-8'));previous.update(record);previous.pop('semantic_review',None);backend.atomic_json(Path(metadata),previous)
            except (OSError,ValueError) as exc:self.events.put(('log','TXT salvo, mas não foi possível atualizar o relatório: '+str(exc)))
        self.remember_edits();self.status.set('TXT salvo: '+str(path))
    def clear(self):
        if self.busy:return
        self.files.clear();self.file_set.clear();self.file_positions.clear();self.relative_paths.clear();self.results.clear();self.edits.clear();self.text_edits.clear();self.list.delete(0,'end');self.shown=None;self.update_count()
        for box in self.texts.values():box.delete('1.0','end')
        self.log_box.configure(state='normal');self.log_box.delete('1.0','end');self.log_box.configure(state='disabled')
        self.reset_progress();self.quality_note.set('Selecione um áudio ou vídeo para consultar as observações.')
    def update_count(self):self.count.set(f'{len(self.files)} arquivos | {len(self.list.curselection())} selecionados')
    def selected(self,event=None):
        self.update_count()
        if not self.running:self.remember_edits()
        indexes=self.list.curselection()
        if not indexes:return
        key=getattr(event,'context_path',None) or self.files[indexes[0]];self.shown=key;record=self.load_saved_result(key)
        source=self.edits.get(key,record.get('transcript',''))
        if not source and key.suffix.lower()=='.txt':
            try:source=key.read_text(encoding='utf-8-sig')
            except (OSError,UnicodeError):source=''
        for name,value in [('source',source),('translation',record.get('translation','')),('revision',record.get('revision',''))]:
            self.texts[name].configure(state='normal');self.texts[name].delete('1.0','end');self.texts[name].insert('1.0',self.text_edits.get(key,{}).get(name,value))
            if self.running:self.texts[name].configure(state='disabled')
        self.quality_note.set('\n'.join(record.get('quality_warnings',[])) or 'Sem alertas registrados. Para tradução, OK exige parecer semântico; o revisor também pode errar.')
        for box in self.texts.values():box.edit_modified(False)
        self.refresh_scene_editor()

    def play_file(self,event):
        if not self.files:return 'break'
        index=self.list.nearest(event.y);bounds=self.list.bbox(index)
        if not bounds or not bounds[1]<=event.y<bounds[1]+bounds[3]:return 'break'
        path=self.files[index]
        if path.suffix.lower()=='.txt':return 'break'
        if path.suffix.lower() not in SUPPORTED:return 'break'
        if not path.is_file():
            messagebox.showwarning('Reproduzir','Arquivo não encontrado: '+str(path),parent=self.parent)
            return 'break'
        try:
            if self.audio_player.playback_mode=='windows':
                self.audio_player.stop(announce=False)
                for preview in self.previews:
                    if not preview.closed:preview.close()
                os.startfile(str(path))
            elif path.suffix.lower() in {'.mp4','.mkv','.avi','.mov'}:
                from video_preview import VideoPreview
                self.previews=[preview for preview in self.previews if not preview.closed]
                if self.previews:self.previews[-1].close()
                self.audio_player.stop(announce=False)
                from types import SimpleNamespace
                owner=SimpleNamespace(root=self.root,project_root=self.project_root,theme=self.theme,files=[item for item in self.files if item.suffix.lower() in {'.mp4','.mkv','.avi','.mov'}])
                self.previews.append(VideoPreview(owner,path))
            else:
                for preview in self.previews:
                    if not preview.closed:preview.close()
                playlist=[item for item in self.files if item.suffix.lower() not in {'.txt','.mp4','.mkv','.avi','.mov'}]
                self.audio_player.play_one(path,title='OUVIR ORIGINAL — TRANSCRIÇÃO / TRADUÇÃO',playlist=playlist,index=playlist.index(path),scene_key=str(path),scene_keys=[str(item) for item in playlist])
            self.status.set('Reprodução: '+path.name)
        except OSError as exc:messagebox.showerror('Reproduzir','Não foi possível abrir o player: '+str(exc),parent=self.parent)
        return 'break'

    def select_from_player(self,scene_key,index):
        path=Path(scene_key) if scene_key else None
        if path not in self.file_set:return
        target=self.file_positions[path]
        self.list.selection_clear(0,'end');self.list.selection_set(target);self.list.activate(target);self.list.see(target)
        from types import SimpleNamespace
        self.selected(SimpleNamespace(context_path=path))
    def build_scene_editor(self,parent):
        from transcription_scene_editor import SceneTexts
        self.scene_editor=SceneTexts(self,parent)
        self.refresh_scene_editor()
    def refresh_scene_editor(self):
        editor=self.scene_editor
        if editor is None or not editor.exists():return
        key=self.audio_player.current_context_key
        path=Path(key) if key else None
        if editor.path!=path:
            for name in editor.texts:editor.changed(name)
        if path not in self.file_set:editor.show(None,{});return
        record=self.load_saved_result(path)
        values={name:self.text_edits.get(path,{}).get(name,record.get(field,'')) for name,field in [('source','transcript'),('translation','translation'),('revision','revision')]}
        if path==self.shown:values={name:box.get('1.0','end-1c') for name,box in self.texts.items()}
        editor.show(path,values)
    def main_text_changed(self,name):
        box=self.texts.get(name)
        if box is None or not box.edit_modified():return
        box.edit_modified(False)
        if self.running:return
        value=box.get('1.0','end-1c');self.text_edits.setdefault(self.shown,{})[name]=value
        if name=='source' and self.shown is not None:self.edits[self.shown]=value
        self.refresh_scene_editor()
    def scene_editor_changed(self,path,name,value):
        self.text_edits.setdefault(path,{})[name]=value
        if name=='source':self.edits[path]=value
        if path==self.shown:
            box=self.texts[name];box.delete('1.0','end');box.insert('1.0',value);box.edit_modified(False)
    def save_scene_editor(self,name):
        if self.busy:return
        path=self.scene_editor.path if self.scene_editor else None
        if path not in self.file_set:return
        self.scene_editor.changed(name)
        self.select_from_player(str(path),0);self.save_current(name);self.refresh_scene_editor()
    def open_key_portal(self,provider):
        from api_settings_ui import open_key_portal
        if not open_key_portal(provider):messagebox.showinfo('Chave','Este mecanismo é local e não usa chave de API.',parent=self.parent)

    def load_saved_result(self,path):
        record=self.results.setdefault(path,{})
        for name,field in [('source','transcript'),('translation','translation')]:
            file=self.final_path(path,name=='translation')
            if field not in record and file.is_file():
                try:
                    record[field]=file.read_text(encoding='utf-8-sig')
                    record.setdefault('paths',{})[name]=str(file)
                except (OSError,UnicodeError):pass
        return record

    def context_menu(self,event):
        if not self.files:return
        index=self.list.nearest(event.y);bounds=self.list.bbox(index)
        if not bounds or not bounds[1]<=event.y<bounds[1]+bounds[3]:return
        if not self.list.selection_includes(index):self.list.selection_clear(0,'end');self.list.selection_set(index)
        path=self.files[index]
        from types import SimpleNamespace
        self.selected(SimpleNamespace(context_path=path))
        record=self.load_saved_result(path)
        menu=tk.Menu(self.list,tearoff=False,bg=self.theme.get('surface','#283445'),fg=self.theme.get('text','#F8FAFC'),activebackground='#52647D',activeforeground='white')
        def copy(value):self.parent.clipboard_clear();self.parent.clipboard_append(str(value))
        def open_path(value):
            try:os.startfile(str(value))
            except OSError as exc:messagebox.showerror('Abrir',str(exc),parent=self.parent)
        def reveal(value):
            from audio_player import reveal_in_file_manager
            reveal_in_file_manager(Path(value))
        menu.add_command(label='ABRIR ÁUDIO / VÍDEO ORIGINAL',command=lambda:open_path(path))
        menu.add_command(label='ABRIR LOCAL DO ORIGINAL',command=lambda:reveal(path))
        menu.add_command(label='COPIAR NOME DO ARQUIVO',command=lambda:copy(path.name))
        menu.add_command(label='COPIAR CAMINHO DO ORIGINAL',command=lambda:copy(path))
        menu.add_separator()
        for name,label in [('source','TRANSCRIÇÃO'),('translation','TRADUÇÃO'),('revision','REVISÃO')]:
            target=record.get('paths',{}).get(name)
            menu.add_command(label='ABRIR TXT — '+label,state='normal' if target and Path(target).exists() else 'disabled',command=lambda p=target:open_path(p))
            menu.add_command(label='COPIAR CAMINHO — '+label,state='normal' if target else 'disabled',command=lambda p=target:copy(p))
        menu.add_command(label='ABRIR PASTA DE SAÍDA',command=self.open_output)
        menu.add_command(label='VERIFICAR / LIMPAR APRESENTAÇÃO DA TRADUÇÃO',state='disabled' if self.busy else 'normal',command=lambda:self.clean_saved_translation(path))
        menu.add_separator()
        for label,mode in [('TRANSCREVER SELECIONADOS','transcribe'),('TRADUZIR SELECIONADOS','translate'),('TRANSCREVER E TRADUZIR SELECIONADOS','both'),('REVISÃO SEMÂNTICA DOS SELECIONADOS','review')]:
            menu.add_command(label=label,state='disabled' if self.busy else 'normal',command=lambda m=mode:self.choose_order(m) if m!='review' else self.start(m))
        for label,callback in [('TEMA / CONTEXTO',self.configure_context),('FERRAMENTAS LOCAIS / BAIXAR',self.configure_local),('CHAVE / LUNA / SOL',self.configure_api),('REVISÃO SEMÂNTICA / APIs',self.configure_review_apis)]:
            menu.add_command(label=label,state='disabled' if self.busy else 'normal',command=callback)
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()

    def clean_saved_translation(self,path):
        record=self.load_saved_result(path);target=record.get('paths',{}).get('translation')
        if not target:messagebox.showwarning('Tradução','Não há TXT traduzido salvo para este arquivo.',parent=self.parent);return
        try:
            original=Path(target).read_text(encoding='utf-8-sig')
            cleaned,notices=normalize_translation_output(record.get('transcript',''),original)
            if cleaned!=original.strip():
                backup=self.project_root/'revisoes'/'limpeza_traducao'/str(time.time_ns())/self.relative_paths[path].with_suffix('.txt')
                self.write_final(backup,original);self.write_final(target,cleaned)
                record['translation']=cleaned;record.pop('semantic_review',None);record['quality_warnings']=notices
                self.text_edits.pop(path,None);self.shown=None;self.update_file_state(path,'review')
                from types import SimpleNamespace
                self.selected(SimpleNamespace(context_path=path))
                self.status.set('Tradução limpa; versão anterior preservada em '+str(backup))
            else:self.status.set('Nenhuma apresentação explicativa reconhecida no TXT.')
        except (OSError,RuntimeError) as exc:messagebox.showwarning('Revisar tradução',str(exc),parent=self.parent)

    def choose_order(self,mode):
        if self.busy:return
        window=tk.Toplevel(self.parent);window.title('Escolher a ordem do processamento');window.geometry('760x330');window.transient(self.parent);window.grab_set()
        frame=ttk.Frame(window,padding=16);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='COMO PROCESSAR OS ARQUIVOS?',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=6)
        choices=[]
        if mode!='both':choices.append(('Somente '+('transcrever' if mode=='transcribe' else 'traduzir os textos já disponíveis'),'only'))
        choices.extend([('Transcrever todo o lote primeiro; depois traduzir (reaproveita o transcritor)','stages'),('Arquivo por arquivo: transcrever e traduzir cada um antes do próximo','per_file')])
        value=tk.StringVar(window,value='stages' if mode=='both' else 'only')
        for label,code in choices:ttk.Radiobutton(frame,text=label,variable=value,value=code).pack(anchor='w',pady=7)
        ttk.Label(frame,text='Por etapas pode reduzir carregamentos do modelo. A revisão opcional segue sua configuração.\nDurante o processamento você pode selecionar arquivos para consultar os resultados já salvos.',wraplength=710).pack(anchor='w',pady=10)
        def begin():
            selected=value.get();window.destroy();self.start(mode if selected=='only' else 'both',order=selected)
        ttk.Button(frame,text='INICIAR',command=begin).pack(side='right',padx=4)
        ttk.Button(frame,text='CANCELAR',command=window.destroy).pack(side='right',padx=4)

    def update_file_state(self,path,state):
        if path not in self.file_set:return
        index=self.file_positions[path];was_selected=self.list.selection_includes(index);top=self.list.yview()[0]
        label={'ok':'OK','review':'REVISAR','transcribed':'TRANSCRITO','transcribing':'TRANSCREVENDO','translating':'TRADUZINDO','queued':'PENDENTE'}.get(state,'PENDENTE')
        self.list.delete(index);self.list.insert(index,f'[{label}] '+str(self.relative_paths[path]))
        if state in ('ok','review'):self.list.itemconfigure(index,foreground='#FFFFFF' if state=='ok' else '#FFD84D',background='#253040',selectforeground='#FFFFFF' if state=='ok' else '#FFD84D')
        if was_selected:self.list.selection_set(index)
        self.list.yview_moveto(top)

    def start(self,mode,order='per_file'):
        if self.busy:return
        if not self.confirm_current_theme():return
        resume=self.resume_state
        indexes=self.list.curselection();paths=[self.files[i] for i in indexes] if indexes else list(self.files)
        if resume:paths=[Path(x) if x else None for x in resume['paths']]
        edited=self.texts['source'].get('1.0','end-1c').strip()
        self.remember_edits()
        if not paths:
            if mode in ('transcribe','both') or not edited:messagebox.showwarning('Entrada','Adicione áudio/vídeo ou escreva um texto.',parent=self.parent);return
            paths=[None]
        self.provider_changed();self.transcription_changed()
        extended=self.config['translator'] in semantic_review.TRANSLATION_PROVIDERS
        use_api=self.config['translator'] in local.API_TRANSLATORS;review=self.review.get();review_local=self.reviewer.get().startswith('IA local');review_provider=self.reviewer.get()
        profile=dict(resume['profile']) if resume else self.effective_context()
        if profile.get('title') and mode=='both':order='stages'
        config=dict(self.config,source=self.source.get(),language=self.target.get(),context_profile=profile)
        profile['translation_device']=config.get('translation_device','auto')
        if self.provider.get().startswith('IA local'):config['translator']='qwen-game-local'
        elif not use_api and config['translator'] in local.API_TRANSLATORS:config['translator']='argos'
        api=backend.api_settings();key=backend.load_key()
        if self.provider.get().startswith('Sol'):api={**api,'luna_model':api['sol_model'],'translation_label':'Tradução Sol'}
        if extended and mode in ('translate','both') and not semantic_review.ready(semantic_review.TRANSLATION_PROVIDERS[config['translator']]):messagebox.showwarning('APIs',semantic_review.configuration_problem(semantic_review.TRANSLATION_PROVIDERS[config['translator']]) or 'Confira chave e modelo em REVISÃO SEMÂNTICA / APIs.',parent=self.parent);return
        if use_api and not extended and mode in ('translate','both') and not key:messagebox.showwarning('Chave','Configure CHAVE / LUNA / SOL antes de usar a API.',parent=self.parent);return
        if (mode=='review' or review and mode in ('translate','both')) and not semantic_review.ready(review_provider):messagebox.showwarning('Revisão semântica','Configure o modelo e a chave do revisor em REVISÃO SEMÂNTICA / APIs. Sol usa CHAVE / LUNA / SOL; a IA local precisa estar preparada.',parent=self.parent);return
        if mode in ('transcribe','both') and any(path is None or path.suffix.lower()=='.txt' for path in paths):messagebox.showwarning('Entrada','Para transcrever, selecione somente áudio/vídeo.',parent=self.parent);return
        try:
            drafts={path:{**self.results.get(path,{}),**{k:self.text_edits[path][k] for k in ('translation','revision') if path in self.text_edits}} for path in paths};texts={path:(self.edits[path] if path in self.edits else (path.read_text(encoding='utf-8-sig') if path and path.suffix.lower()=='.txt' else drafts[path].get('transcript',''))) for path in paths}
        except (OSError,UnicodeError) as exc:
            messagebox.showerror('Ler texto','Não foi possível ler um dos TXTs como UTF-8. '+str(exc),parent=self.parent);return
        if resume:
            drafts={path:dict(resume['records'].get(str(path or ''),{})) for path in paths};texts={path:drafts[path].get('transcript',resume.get('texts',{}).get(str(path or ''),'')) for path in paths}
        if paths==[None] and not resume:texts[None]=edited
        if mode in ('translate','review') and any(not texts[p].strip() for p in paths):messagebox.showwarning('Texto','Transcreva o áudio primeiro ou forneça um TXT.',parent=self.parent);return
        if mode=='review' and any(not drafts[p].get('translation') for p in paths):
            if len(paths)==1 and self.texts['translation'].get('1.0','end-1c').strip():drafts[paths[0]]['translation']=self.texts['translation'].get('1.0','end-1c').strip()
            else:messagebox.showwarning('Revisão','Gere ou cole uma tradução na guia TRADUÇÃO antes de revisar.',parent=self.parent);return
        if mode=='translate' and not use_api and config['source']=='auto' and any(not drafts[p].get('source_language') for p in paths):
            messagebox.showwarning('Idioma de origem','Para traduzir TXT com o tradutor local, selecione o idioma de origem. Luna pode identificar pelo texto.',parent=self.parent);return
        local.save_last_settings(config)
        self.running=True;self.cancel_event.clear();self.pause_event.clear();self.pause_button.configure(text='PAUSAR');self.reset_progress({'transcribe':len(paths) if mode in ('transcribe','both') else 0,'translate':len(paths) if mode in ('translate','both','review') else 0})
        for box in self.texts.values():box.configure(state='disabled')
        for button in self.job_buttons:button.configure(state='disabled')
        folder=self.project_root/'revisoes'/'transcricoes_traducoes'/('sessao_'+str(time.time_ns()));self.last_output=self.project_root/'TRANSCRIÇÕES E TRADUÇÕES'
        emit=lambda text:self.events.put(('log',text))
        def worker():
            try:
                folder.mkdir(parents=True,exist_ok=True)
                if self.cancel_event.is_set():raise RuntimeError('Operação cancelada.')
                records={path:dict(drafts[path]) for path in paths};failed=set()
                bases={path:folder/(f'{number:05d}_'+(path.stem if path else 'texto_editavel')) for number,path in enumerate(paths,1)}
                total=len(paths)
                transcribed=set(resume.get('transcribed',[])) if resume else set();completed=set(resume.get('completed',[])) if resume else set()
                fingerprints=resume['fingerprints'] if resume else {str(p):[p.stat().st_size,p.stat().st_mtime_ns] for p in paths if p}
                research_signature=[resume.get('research_signature','') if resume else '']
                def checkpoint(complete=False):
                    state={'version':1,'mode':mode,'order':order,'paths':[str(p or '') for p in paths],'fingerprints':fingerprints,'relative_paths':{str(p):str(self.relative_paths[p]) for p in paths if p},'research_signature':research_signature[0],'config':config,'profile':profile,'review':review,'review_provider':review_provider,'records':{str(p or ''):r for p,r in records.items()},'texts':{str(p or ''):t for p,t in texts.items()},'transcribed':sorted(transcribed),'completed':sorted(completed),'complete':complete}
                    backend.atomic_json(self.checkpoint_path,state)
                def enrich_theme():
                    if not profile.get('title'):return
                    self.wait_if_paused()
                    import theme_research
                    corpus='\n\n'.join(str(records[p].get('transcript',texts[p])) for p in paths if p not in failed)
                    if not corpus.strip():return
                    signature=hashlib.sha256(corpus.encode('utf-8')).hexdigest()
                    if research_signature[0]==signature:return
                    emit('TEMA: pesquisando terminologia a partir dos transcritos. Usa a IA escolhida no tema e pode gerar cobrança de API.')
                    try:
                        updated=theme_research.enrich_from_transcripts(profile,corpus,emit,self.cancel_event.is_set)
                        profile.update(updated);config['context_profile']=profile;research_signature[0]=signature
                        context_tools.save_context(self.project_root,profile);checkpoint();self.events.put(('context_research',dict(profile)))
                    except Exception as exc:
                        if self.cancel_event.is_set():raise
                        emit('AVISO: pesquisa dos transcritos não concluída; preservado o tema anterior. '+str(exc))
                checkpoint()
                def publish(path,record,finished=False,translated=False):
                    record['quality_warnings']=list(record.get('asr_warnings',[]))
                    record['quality_warnings']=backend.assess_text_result(record,path,config['source'],translated)
                    if translated:
                        verdict=record.get('semantic_review',{})
                        if not verdict.get('evaluated'):record['quality_warnings'].append('Tradução sem avaliação semântica; ative Avaliar/revisar tradução para conferir sentido e naturalidade.')
                        elif verdict.get('needs_review'):record['quality_warnings'].extend(verdict.get('issues') or ['Revisor semântico pediu conferência.'])
                    record['metadata_path']=str(Path(str(bases[path])+'.json'))
                    record['status']='review' if record['quality_warnings'] else 'ok' if finished else 'transcribed'
                    snapshot=json.loads(json.dumps(record,ensure_ascii=False))
                    backend.atomic_json(Path(str(bases[path])+'.json'),{**snapshot,'input':str(path or ''),'local_settings':config,'api_models':{k:api[k] for k in ('luna_model','sol_model')}})
                    checkpoint();self.events.put(('result',path,snapshot))
                def report_for(number,revision=False):
                    def report(line):
                        if line.startswith('DUBLASKIZON_PHASE '):
                            try:
                                phase=json.loads(line.split(' ',1)[1]);stage=phase['stage'];fraction=float(phase['fraction'])
                                if stage=='translate' and review and mode!='review':fraction=.5*fraction+(.5 if revision else 0)
                                self.events.put(('progress',stage,100*((number-1)+fraction)/total))
                            except (ValueError,KeyError,TypeError):pass
                        else:emit(line)
                    return report
                def failed_item(path,record,exc):
                    if self.cancel_event.is_set():raise RuntimeError('Operação cancelada.')
                    record['error']=str(exc);failed.add(path);publish(path,record)
                    emit('REVISAR: '+str(path or 'texto')+' — '+str(exc))
                def accept_transcription(index,data):
                    path=paths[index];record=records[path]
                    record['paths']=dict(record.get('paths',{}));record['quality_warnings']=[];record.pop('error',None)
                    if mode=='both':
                        for field in ('translation','revision','semantic_review'):record.pop(field,None);record['paths'].pop(field,None)
                    if data.get('error'):failed_item(path,record,data['error'])
                    else:
                        record.update(data);record['asr_warnings']=list(data.get('quality_warnings',[]));record['paths']['source']=str(self.final_path(path));self.write_final(record['paths']['source'],record['transcript'])
                        transcribed.add(str(path or ''))
                        if mode=='transcribe':completed.add(str(path or ''))
                        publish(path,record,finished=mode=='transcribe')
                    self.events.put(('stage_item','transcribe',index+1,'failed' if path in failed else 'done'))
                    self.events.put(('progress','transcribe',100*(index+1)/total))
                    self.wait_if_paused()
                def transcribe_one(index):
                    self.wait_if_paused()
                    if str(paths[index] or '') in transcribed:
                        self.events.put(('stage_item','transcribe',index+1,'done'));return
                    path=paths[index];self.events.put(('file_state',path,'transcribing'));self.events.put(('stage_item','transcribe',index+1,'active'))
                    try:accept_transcription(index,backend.run_local(path,None,config,True,report_for(index+1),self.cancel_event.is_set))
                    except Exception as exc:
                        failed_item(path,records[path],exc);self.events.put(('stage_item','transcribe',index+1,'failed'))
                def translate_one(index):
                    self.wait_if_paused()
                    if str(paths[index] or '') in completed:
                        self.events.put(('result',paths[index],dict(records[paths[index]])));self.events.put(('stage_item','translate',index+1,'done'));return
                    path=paths[index];record=records[path];record['paths']=dict(record.get('paths',{}));base=bases[path]
                    record.pop('error',None);text=record.get('transcript',texts[path]);record['transcript']=text
                    self.events.put(('file_state',path,'translating'));self.events.put(('stage_item','translate',index+1,'active'));report=report_for(index+1)
                    try:
                        if mode in ('translate','both'):
                            if extended:translated=semantic_review.translate(text,config['language'],config['translator'],report,self.cancel_event.is_set,context=profile)
                            elif use_api:translated=backend.translate_api(text,config['language'],api,key,report,self.cancel_event.is_set,checkpoint=lambda partial:Path(str(base)+'.luna-parcial.txt').write_text(partial,encoding='utf-8'),context=profile)
                            else:
                                local_config=dict(config)
                                if local_config['source']=='auto':local_config['source']=record.get('source_language','auto')
                                translated=backend.run_local(None,text,local_config,False,report,self.cancel_event.is_set)['translation']
                            translated,notices=normalize_translation_output(text,translated)
                            for notice in notices:report(notice)
                            record.pop('semantic_review',None);record['translation']=translated;record['paths']['translation']=str(self.final_path(path,True));self.write_final(record['paths']['translation'],translated)
                            publish(path,record,finished=not review,translated=True)
                            self.events.put(('progress','translate',100*(index+(.5 if review else 1))/total))
                        if mode=='review' or review and mode in ('translate','both'):
                            report=report_for(index+1,revision=True)
                            verdict=semantic_review.review(text,record['translation'],config['language'],profile,review_provider,report,self.cancel_event.is_set)
                            corrected,notices=normalize_translation_output(text,verdict['corrected_translation'])
                            if notices:verdict['needs_review']=True;verdict['issues']=list(verdict['issues'])+notices
                            verdict['corrected_translation']=corrected
                            record['semantic_review']=verdict;record['revision']=corrected
                            record['revision_engine']='local' if review_local else 'sol-api' if review_provider.startswith('Sol') else review_provider
                            Path(str(base)+'.revisao-semantica.txt').write_text(record['revision']+'\n',encoding='utf-8')
                            record['unrevised_translation']=record['translation'];record['translation']=record['revision']
                            record['paths']['translation']=record['paths']['revision']=str(self.final_path(path,True));self.write_final(record['paths']['revision'],record['revision'])
                        completed.add(str(path or ''));publish(path,record,finished=True,translated=True)
                        self.events.put(('stage_item','translate',index+1,'done'));self.events.put(('progress','translate',100*(index+1)/total));emit('CONCLUÍDO: '+str(base))
                    except Exception as exc:
                        failed_item(path,record,exc);self.events.put(('stage_item','translate',index+1,'failed'))
                if mode in ('translate','review'):enrich_theme()
                for path in paths:self.events.put(('file_state',path,records[path].get('status','queued') if str(path or '') in completed else 'queued'))
                for index,path in enumerate(paths):
                    if str(path or '') in transcribed:self.events.put(('stage_item','transcribe',index+1,'done'))
                if mode in ('transcribe','both') and (order=='stages' or mode=='transcribe'):
                    emit('ETAPA 1: transcrever o lote mantendo somente o transcritor carregado. Tradução começa após liberar esse processo.')
                    pending=[i for i,p in enumerate(paths) if str(p or '') not in transcribed]
                    if len(pending)>1:
                        self.events.put(('stage_item','transcribe',1,'active'))
                        def batch_log(line):
                            if line.startswith('DUBLASKIZON_PHASE '):
                                data=json.loads(line.split(' ',1)[1]);index=pending[int(data.get('batch_index',0))];self.events.put(('file_state',paths[index],'transcribing'));self.events.put(('stage_item','transcribe',index+1,'active'));report_for(index+1)(line)
                            else:emit(line)
                        backend.run_local_batch([paths[i] for i in pending],config,batch_log,self.cancel_event.is_set,lambda index,data:accept_transcription(pending[index],data))
                    elif pending:transcribe_one(pending[0])
                    enrich_theme()
                    if mode=='both':
                        emit('ETAPA 2: traduzir os textos concluídos; revisão conforme configurada.')
                        for index,path in enumerate(paths):
                            if self.cancel_event.is_set():raise RuntimeError('Operação cancelada.')
                            if path not in failed:translate_one(index)
                            else:self.events.put(('stage_item','translate',index+1,'skipped'))
                else:
                    for index,path in enumerate(paths):
                        if self.cancel_event.is_set():raise RuntimeError('Operação cancelada.')
                        emit(f'[{index+1}/{total}] {path.name if path else "texto_editavel"}')
                        if mode in ('transcribe','both'):transcribe_one(index)
                        else:records[path]['transcript']=texts[path]
                        if mode!='transcribe':
                            if path not in failed:translate_one(index)
                            else:self.events.put(('stage_item','translate',index+1,'skipped'))
                checkpoint(complete=len(completed)==total)
                if profile.get('title'):self.events.put(('theme_ready',))
                review_count=sum(record.get('status')=='review' for record in records.values())
                if mode in ('transcribe','both'):self.events.put(('progress','transcribe',100))
                if mode in ('translate','both','review'):self.events.put(('progress','translate',100))
                self.events.put(('done',f'Concluído: {total} arquivos processados; {review_count} para REVISAR ({len(failed)} com falha). Resultados em '+str(self.last_output)))
            except Exception as exc:self.events.put(('done','ERRO: '+str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        if not self.parent.winfo_exists():return
        for _ in range(100):
            try:event=self.events.get_nowait()
            except queue.Empty:break
            kind=event[0]
            if kind=='add':
                self.add_paths(event[1],event[2] if len(event)>2 else None);break
            elif kind=='file_state':self.update_file_state(event[1],event[2])
            elif kind=='stage_item':self.update_stage_item(event[1],event[2],event[3])
            elif kind=='progress':self.advance_progress(event[1],event[2])
            elif kind=='theme_ready':self.blink_theme()
            elif kind=='context_research':
                try:self.context=context_tools.save_context(self.project_root,event[1])
                except OSError as exc:self.events.put(('log','Não foi possível guardar a pesquisa: '+str(exc)))
            elif kind=='scan_done':self.discovering=False
            elif kind=='log':
                self.log_box.configure(state='normal');self.log_box.insert('end',str(event[1])+'\n')
                if int(self.log_box.index('end-1c').split('.')[0])>1000:self.log_box.delete('1.0','200.0')
                self.log_box.see('end');self.log_box.configure(state='disabled');self.status.set(str(event[1])[-200:])
                callback=self.actions.get('central_log')
                if callback:callback('TRANSCREVER E TRADUZIR',str(event[1]))
            elif kind=='result':
                self.results[event[1]]=event[2];self.text_edits.pop(event[1],None);self.edits.pop(event[1],None)
                self.update_file_state(event[1],event[2].get('status','queued'))
                if self.shown is None:self.shown=event[1]
                if self.shown==event[1] or event[1] is None:
                    self.quality_note.set('\n'.join(event[2].get('quality_warnings',[])) or 'Sem alertas registrados pelo processamento/revisor; confira o conteúdo.')
                    for name,key in [('source','transcript'),('translation','translation'),('revision','revision')]:
                        self.texts[name].configure(state='normal');self.texts[name].delete('1.0','end');self.texts[name].insert('1.0',event[2].get(key,''))
                        if self.running:self.texts[name].configure(state='disabled')
                self.refresh_scene_editor()
            elif kind=='done':
                self.running=False;self.pause_event.clear();self.pause_button.configure(text='PAUSAR');self.status.set(event[1])
                self.list.configure(state='normal')
                for box in self.texts.values():box.configure(state='normal')
                self.events.put(('log',event[1]))
                for button in self.job_buttons:button.configure(state='normal')
                self.refresh_scene_editor()
        self.poll_id=self.parent.after(100,self.poll)
    def export(self):
        selected=self.current_text_key()
        text=self.texts[selected].get('1.0','end-1c')
        if not text.strip():messagebox.showinfo('Exportar TXT','A guia selecionada está vazia. Selecione Transcrição, Tradução ou Revisão com texto para exportar.',parent=self.parent);return
        suffix={'source':'transcricao','translation':'traducao','revision':'revisao'}[selected]
        path=filedialog.asksaveasfilename(parent=self.parent,title='Exportar '+suffix+' — cópia do texto atual',initialfile=(self.shown.stem if self.shown else 'texto')+'_'+suffix+'.txt',initialdir=str(self.project_root),defaultextension='.txt',filetypes=[('Texto','*.txt')])
        if not path:return
        try:self.write_final(Path(path),text)
        except OSError as exc:messagebox.showerror('Exportar TXT','Não foi possível salvar o TXT: '+str(exc),parent=self.parent);return
        self.status.set('TXT exportado: '+str(path))

    def open_output(self):
        folder=self.last_output or self.project_root/'TRANSCRIÇÕES E TRADUÇÕES'
        try:folder.mkdir(parents=True,exist_ok=True);os.startfile(folder)
        except OSError as exc:messagebox.showerror('Pasta de saída',str(exc),parent=self.parent)
