"""Basic editor view from the supplied ZIP, using current safe audio operations."""
from audio_player import (TK_AVAILABLE, Toplevel, i18n, StringVar, Frame, Label,
                          Button, apply_button_style, Canvas, Text, Scrollbar)

def show_simple_window(self, title: str, initial_text: str):
    if not TK_AVAILABLE:
        return
    # Preserva pending_paths: play_one/play_all já colocaram os arquivos na fila.
    self._destroy_window(clear_pending=False)
    window = Toplevel(self.parent)
    window.title(i18n.tr(title)+' — EDITOR SIMPLES')
    try:
        available_height = max(600, int(window.winfo_screenheight()) - 80)
    except Exception:
        available_height = 760
    window.geometry(f"1100x{min(600, available_height)}")
    window.minsize(900, min(600, available_height))
    window.resizable(True, True)
    # Mantém a decoração normal do Windows para que o botão nativo de
    # maximizar/restaurar apareça junto de minimizar e X FECHAR.
    try:
        window.wm_attributes("-toolwindow", False)
    except Exception:
        pass
    window.protocol("WM_DELETE_WINDOW", self.close_window)
    window.bind("<space>", self._on_edit_space, add="+")
    try:
        window.lift()
        window.focus_force()
    except Exception:
        pass
    self.window = window
    self.audacity_ui = None
    self.waveform_zoom_slider = None
    self.window_status = StringVar(value=i18n.tr(initial_text))
    surface = self.theme.get("surface", "#FFFFFF")
    text = self.theme.get("text", "#1F2937")
    border_color = self.window_border_color
    window.configure(bg=border_color)
    try:
        window.configure(highlightthickness=2, highlightbackground=border_color, highlightcolor=border_color)
    except Exception:
        pass
    # O status detalhado continua disponível internamente para callbacks e logs,
    # mas não ocupa mais espaço visual na janela OUVIR CENA.
    self.window_body = None
    self.window_content = Frame(window, bg=surface, bd=0, highlightthickness=0)
    self.window_content.pack(fill="both", expand=True, padx=3, pady=3)
    content = self.window_content
    from scene_parts import ScenePartsUI
    if not hasattr(self,'scene_parts_ui'):self.scene_parts_ui=ScenePartsUI(self)
    content=self.scene_parts_ui.attach(content)
    self.waveform_panel = Frame(content, bg=surface, bd=1, relief="solid")
    self.waveform_panel.pack(side="top", fill="x", expand=False, padx=14, pady=(0, 8))
    self.waveform_widgets = [self.waveform_panel]
    waveform_title = Label(self.waveform_panel, text=i18n.tr("FORMAS DE ONDA E COMPRIMENTO"), bg=surface, fg=text, font=("Segoe UI", 9, "bold"), anchor="w")
    waveform_title.pack(fill="x", padx=10, pady=(7, 3))
    self.waveform_widgets.append(waveform_title)
    edit_toolbar = Frame(self.waveform_panel, bg=surface)
    edit_toolbar.pack(fill="x", padx=10, pady=(0, 5))
    self.waveform_widgets.append(edit_toolbar)
    self.audio_edit_status_var = StringVar(value=i18n.tr("Clique em EDITAR para selecionar trechos nas ondas."))
    edit_status = Label(edit_toolbar, textvariable=self.audio_edit_status_var, bg=surface, fg=self.theme.get("muted", "#64748B"), font=("Segoe UI", 7), anchor="w")
    edit_status.pack(side="left", fill="x", expand=True)
    self.waveform_widgets.append(edit_status)
    # O modo EDITAR/SAIR DO EDITAR fica separado das ações destrutivas e
    # de edição. As ações permanecem juntas, com SALVAR abrindo o grupo
    # um pouco mais à esquerda, conforme o layout da janela de referência.
    edit_mode_button = Button(edit_toolbar, text=i18n.tr("EDITAR"), command=self._toggle_audio_edit, relief="flat", font=("Segoe UI", 7, "bold"), padx=7, pady=2)
    apply_button_style(edit_mode_button, self.theme, "accent")
    edit_mode_button.pack(side="right", padx=(16, 0))
    self.audio_edit_button = edit_mode_button

    edit_actions = Frame(edit_toolbar, bg=surface)
    edit_actions.pack(side="right")
    edit_buttons = (
        ("audio_undo_button", "DESFAZER", self._undo_audio_edit, "secondary"),
        ("audio_redo_button", "REFAZER", self._redo_audio_edit, "secondary"),
        ("audio_save_button", "SALVAR", self._save_audio_edit, "primary"),
        ("audio_paste_button", "COLAR", self._paste_audio_clip, "success"),
        ("audio_copy_button", "COPIAR", self._copy_audio_selection, "secondary"),
        ("audio_delete_button", "DELETE", self._delete_audio_selection, "danger"),
        ("audio_cut_button", "RECORTAR", self._cut_audio_selection, "danger"),
    )
    for attribute, label, command, role in edit_buttons:
        button = Button(edit_actions, text=i18n.tr(label), command=command, relief="flat", font=("Segoe UI", 7, "bold"), padx=7, pady=2)
        apply_button_style(button, self.theme, role)
        # DESFAZER e REFAZER ficam juntos; o grupo recebe uma lacuna
        # maior antes de SALVAR, e SALVAR também fica afastado de COLAR.
        gap_after_button = 12 if attribute in {"audio_redo_button", "audio_save_button"} else 2
        button.pack(side="left", padx=(0, gap_after_button))
        setattr(self, attribute, button)
    self._update_audio_edit_buttons()
    waveform_labels = (
        ("original", i18n.tr("ORIGINAL"), i18n.tr("▶  INICIAR ORIGINAL")),
        ("dubbed", i18n.tr("DUBLADO"), i18n.tr("▶  INICIAR DUBLADO")),
    )
    for kind, label, start_label in waveform_labels:
        row = Frame(self.waveform_panel, bg=surface)
        row.pack(fill="x", padx=10, pady=(0, 4))
        heading = Frame(row, bg=surface)
        heading.pack(fill="x")
        label_widget = Label(heading, text=f"{label}  —  {start_label}", bg=surface, fg=text, font=("Segoe UI", 8, "bold"), anchor="w")
        label_widget.pack(side="left")
        duration_var = StringVar(value=i18n.tr("Duração: calculando..."))
        self.waveform_duration_vars[kind] = duration_var
        duration_label = Label(heading, textvariable=duration_var, bg=surface, fg=self.theme.get("muted", "#64748B"), font=("Segoe UI", 8), anchor="e")
        duration_label.pack(side="right")
        self.waveform_widgets.extend((row, heading, label_widget, duration_label))
        self.waveform_duration_labels[kind] = duration_label
        canvas = Canvas(row, width=900, height=62, highlightthickness=0, bd=1, relief="solid", bg=self.theme.get("input", "#FFFFFF"))
        canvas.pack(fill="x", expand=True, pady=(2, 0))
        self.waveform_canvases[kind] = canvas
        canvas.bind("<Configure>", lambda _event, waveform_kind=kind: self._draw_waveform(waveform_kind))
        canvas.bind("<Button-1>", lambda event, waveform_kind=kind: self._on_waveform_press(waveform_kind, event))
        canvas.bind("<B1-Motion>", lambda event, waveform_kind=kind: self._on_waveform_motion(waveform_kind, event))
        canvas.bind("<ButtonRelease-1>", lambda event, waveform_kind=kind: self._on_waveform_release(waveform_kind, event))
        canvas.bind("<Control-c>", self._copy_audio_selection)
        canvas.bind("<Control-x>", self._cut_audio_selection)
        canvas.bind("<Control-v>", self._paste_audio_clip)
        canvas.bind("<Control-z>", self._undo_audio_edit)
        canvas.bind("<Control-y>", self._redo_audio_edit)
        canvas.bind("<Delete>", self._delete_audio_selection)
        canvas.bind("<BackSpace>", self._delete_audio_selection)
        canvas.bind("<space>", self._toggle_edit_play_pause)
        canvas.configure(cursor="hand2", takefocus=True)
    text_panel = Frame(content, bg=surface, bd=1, relief="solid", height=190)
    # Em uma janela maximizada, o painel de texto absorve o espaço livre
    # entre as ondas e os controles inferiores; assim não sobra um vazio
    # central e o rodapé permanece acima da barra de tarefas.
    text_panel.pack(side="top", fill="both", expand=True, padx=14, pady=(0, 8))
    text_panel.pack_propagate(False)
    text_header = Frame(text_panel, bg=surface)
    text_header.pack(fill="x", padx=10, pady=(8, 2))
    Label(text_header, text=i18n.tr("TEXTO EM PORTUGUÊS — EDITÁVEL"), bg=surface, fg=text, font=("Segoe UI", 9, "bold"), anchor="w").pack(side="left")
    self.scene_text_title_var = StringVar(value="")
    Label(text_header, textvariable=self.scene_text_title_var, bg=surface, fg=text, font=("Segoe UI", 9), anchor="e").pack(side="right", fill="x", expand=True, padx=(12, 0))
    scene_text_frame = Frame(text_panel, bg=surface)
    scene_text_frame.pack(fill="both", expand=True, padx=10, pady=(2, 0))
    self.scene_text_box = Text(scene_text_frame, height=4, wrap="word", undo=True, font=("Segoe UI", 10), bg=self.theme.get("input", "#FFFFFF"), fg=self.theme.get("text", "#1F2937"), insertbackground=self.theme.get("text", "#1F2937"), relief="solid", bd=1)
    scene_text_scroll = Scrollbar(scene_text_frame, orient="vertical", command=self.scene_text_box.yview)
    self.scene_text_box.configure(yscrollcommand=scene_text_scroll.set)
    self.scene_text_box.pack(side="left", fill="both", expand=True)
    scene_text_scroll.pack(side="right", fill="y")
    text_footer = Frame(text_panel, bg=surface)
    text_footer.pack(fill="x", padx=10, pady=(4, 8))
    self.scene_text_status_var = StringVar(value="")
    Label(text_footer, textvariable=self.scene_text_status_var, bg=surface, fg=self.theme.get("text", "#1F2937"), font=("Segoe UI", 8), anchor="w").pack(side="left", fill="x", expand=True)
    self.scene_text_save_button = Button(text_footer, text=i18n.tr("Salvar alteração"), command=self._save_scene_text_from_window, relief="flat", font=("Segoe UI", 8, "bold"), padx=10, pady=4)
    apply_button_style(self.scene_text_save_button, self.theme, "primary")
    self.scene_text_save_button.pack(side="right")
    self._refresh_scene_text()
    self._refresh_waveforms()
    controls = Frame(content, bg=surface, height=68)
    controls.pack(side="bottom", fill="x", padx=14, pady=(0, 12))
    controls.pack_propagate(False)
    self.previous_button = Button(controls, text=i18n.tr("◀ ANTERIOR"), command=lambda: self.navigate(-1), relief="flat", padx=8, pady=5)
    apply_button_style(self.previous_button, self.theme, "secondary")
    self.previous_button.pack(side="left", padx=(0, 3))
    self.next_button = Button(controls, text=i18n.tr("PRÓXIMO ▶"), command=lambda: self.navigate(1), relief="flat", padx=8, pady=5)
    apply_button_style(self.next_button, self.theme, "secondary")
    self.next_button.pack(side="left", padx=3)
    play_modes = Frame(controls, bg=surface)
    play_modes.pack(side="left", padx=3)
    self.original_button = Button(play_modes, text=i18n.tr("▶  INICIAR ORIGINAL"), command=self.start_original_pending, relief="flat", padx=12, pady=3)
    apply_button_style(self.original_button, self.theme, "accent")
    self.original_button.pack(side="top", fill="x")
    self.start_button = Button(play_modes, text=i18n.tr("▶  INICIAR DUBLADO"), command=self.start_pending, relief="flat", padx=12, pady=3)
    apply_button_style(self.start_button, self.theme, "success")
    self.start_button.pack(side="top", fill="x", pady=(3, 0))
    self.stop_button = Button(controls, text=i18n.tr("PARAR"), command=self.stop, relief="flat", padx=12, pady=5)
    apply_button_style(self.stop_button, self.theme, "danger")
    self.stop_button.pack(side="left", padx=3)
    if callable(self.review_snapshot_provider):
        self._build_review_progress_controls(controls, surface, text)
    audio_controls = Frame(content, bg=surface, height=88)
    audio_controls.pack(side="bottom", fill="x", padx=10, pady=(0, 5))
    audio_controls.pack_propagate(False)
    audio_definitions = (
        ("open_dubbed", "ABRIR LOCAL DO ÁUDIO DUBLADO"),
        ("open_original", "ABRIR LOCAL DO ÁUDIO ORIGINAL"),
        ("copy_name", "COPIAR NOME DO ÁUDIO"),
        ("copy_dubbed", "COPIAR LOCAL DO ÁUDIO DUBLADO"),
        ("copy_original", "COPIAR LOCAL DO ÁUDIO ORIGINAL"),
    )
    for column in range(3):
        audio_controls.grid_columnconfigure(column, weight=1, uniform="audio_action")
    for index, (action_name, label) in enumerate(audio_definitions):
        row, column = divmod(index, 3)
        button = Button(
            audio_controls,
            text=i18n.tr(label),
            command=lambda name=action_name: self._audio_context_action(name),
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=4,
            wraplength=280,
            justify="center",
        )
        role = "neutral"
        apply_button_style(button, self.theme, role)
        button.grid(row=row, column=column, sticky="nsew", padx=2, pady=2)
        self.audio_action_buttons.append((button, role))
    audio_controls.grid_rowconfigure(0, weight=1)
    audio_controls.grid_rowconfigure(1, weight=1)
    if self.review_actions:
        review_controls = Frame(content, bg=surface)
        review_controls.pack(side="bottom", fill="x", padx=10, pady=(0, 5))
        self.review_preferences_frame = Frame(review_controls, bg=surface)
        self.review_controls_buttons = Frame(review_controls, bg=surface)
        self.review_controls_buttons.pack(side="bottom", fill="x")
        definitions = (
            ("open_audacity", "Abrir ORIGINAL + DUBLAGEM no Audacity", "warning"),
            ("approve", "Aprovar", "primary"),
            ("reject", "Rejeitar", "danger"),
            ("redub", "REDUBLAR", "success"),
            ("redub_other", "REDUBLAR COM OUTRO ÁUDIO", "accent"),
        )
        for action_name, label, role in definitions:
            callback = self.review_actions.get(action_name)
            if not callable(callback):
                continue
            button = Button(self.review_controls_buttons, text=i18n.tr(label), command=lambda name=action_name: self._invoke_review_action(name), relief="flat", font=("Segoe UI", 8, "bold"), padx=6, pady=4)
            apply_button_style(button, self.theme, role)
            button.pack(side="left", fill="x", expand=True, padx=2)
            self.review_action_buttons.append((button, role))
        self._refresh_review_preferences()
    parts_bar = Frame(content,bg=surface)
    parts_bar.pack(side='bottom',fill='x',padx=10,pady=(0,5))
    self.part_action_buttons=[]
    for label,action,role in [('DUBLAR PARTE\nDO TXT','dub_part','success'),('DUBLAR PARTE DO\nÁUDIO ORIGINAL','dub_original_part','accent')]:
        outline=Frame(parts_bar,bg='#FACC15',padx=2,pady=2)
        outline.pack(side='left',fill='both',expand=True,padx=2)
        button=Button(outline,text=label,command=lambda a=action:self._audio_context_action(a),relief='flat',font=('Segoe UI',8,'bold'),pady=5)
        apply_button_style(button,self.theme,role)
        button.pack(fill='both',expand=True)
        self.part_action_buttons.append(button)
        self.audio_action_buttons.append((button,role))
    self.close_button = Button(controls, text=i18n.tr("X  FECHAR"), command=self.close_window, relief="flat", padx=12, pady=5)
    apply_button_style(self.close_button, self.theme, "secondary")
    self.close_button.pack(side="right", padx=0)
    self._update_original_button()
    self._update_navigation_buttons()
    try:
        window.update_idletasks()
        requested_height = max(560, int(window.winfo_reqheight()))
        fitted_height = min(requested_height, available_height)
        window.geometry(f"1100x{fitted_height}")
        window.minsize(900, fitted_height)
        window.update_idletasks()
    except Exception:
        pass
    return window
