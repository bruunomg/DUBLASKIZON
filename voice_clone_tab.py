"""Aba gráfica para preparar áudios destinados a clonagem de voz."""
from __future__ import annotations

import math
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

try:
    from .audio_clone_preprocessor import AudioCloneProcessor, AudioInfo, AudioProcessingError, MODES, format_bytes, format_seconds
    from .audio_player import AudioPlayerManager
    from .duration_converter_tab import executable_path, FFMPEG_WINDOWS_URL, SOX_WINDOWS_URL, TOOLS_DIR_NAME, HoverTooltip, update_download_progress
    from .ui_theme import apply_button_style, apply_button_style_to_tree, configure_ttk_button_styles, surface_color
    from . import i18n
except ImportError:
    from audio_clone_preprocessor import AudioCloneProcessor, AudioInfo, AudioProcessingError, MODES, format_bytes, format_seconds
    from audio_player import AudioPlayerManager
    from duration_converter_tab import executable_path, FFMPEG_WINDOWS_URL, SOX_WINDOWS_URL, TOOLS_DIR_NAME, HoverTooltip, update_download_progress
    from ui_theme import apply_button_style, apply_button_style_to_tree, configure_ttk_button_styles, surface_color
    import i18n

try:
    from tkinter import END, StringVar, Text, filedialog, messagebox, ttk
    from tkinter import Button, Entry, Frame, Label, Listbox, Scrollbar
    TK_AVAILABLE = True
except ModuleNotFoundError as exc:
    TK_AVAILABLE = False
    TK_IMPORT_ERROR = str(exc)
    END = "end"

try:
    from tkinterdnd2 import DND_FILES  # type: ignore
except Exception:
    DND_FILES = "DND_Files"

if TK_AVAILABLE:
    messagebox = i18n.localized_messagebox(messagebox)

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".wave", ".flac", ".m4a", ".ogg", ".aac", ".aiff", ".aif", ".wma", ".opus"}
TARGET_CHOICES = ("omnivoice", "eleven_instant", "eleven_pro")
TARGET_LABELS = {
    "omnivoice": "OmniVoice VoiceStudio",
    "eleven_instant": "ElevenLabs Instant",
    "eleven_pro": "ElevenLabs Professional",
}
OUTPUT_FORMATS = ("wav", "mp3", "flac", "ogg", "aiff", "m4a")
CLONE_OUTPUT_FOLDER_NAME = "REDIMENSIONAR ÁUDIO PARA CLONAR"
TARGET_HELP_TEXTS = {
    "omnivoice": "OmniVoice VoiceStudio\n\nPadrão: 10 segundos em WAV PCM 16-bit, 44,1 kHz, mono.\nFaixa recomendada: 5–20 segundos; máximo interno: 25 segundos.\nUse uma fala limpa, sem música, ruído ou silêncio excessivo. O conjunto escolhido é unido antes do corte.",
    "eleven_instant": "ElevenLabs Instant\n\nPadrão: 120 segundos em MP3 256 kbps, 44,1 kHz, mono, para boa compatibilidade e upload menor.\nFaixa recomendada: 60–180 segundos. Limite de tamanho tratado pelo app: 400 MB como margem conservadora.\nEscolha uma voz limpa, contínua e sem música; o excedente é cortado no final.",
    "eleven_pro": "ElevenLabs Professional\n\nPadrão: blocos de 30 minutos em FLAC ou WAV, 44,1 kHz, mono.\nO app organiza o conjunto em blocos de 30–45 minutos, com total de até 180 minutos.\nLimite de tamanho tratado pelo app: 450 MB por bloco como margem conservadora. O excedente total é cortado no final.",
}
FORMAT_BITRATE_ESTIMATES = {"mp3": 256000, "ogg": 192000, "m4a": 192000}
FORMAT_COMPRESSION_FACTORS = {"flac": 0.65}
FORMAT_HELP_TEXT = (
    "WAV: sem compressão; melhor para edição e para preservar a maior qualidade.\n\n"
    "FLAC: sem perdas e menor que WAV; bom para arquivar e editar sem perda.\n\n"
    "MP3: maior compatibilidade e arquivos menores; use 256 kbps ou mais para clonagem.\n\n"
    "OGG: compacto e útil em jogos ou streaming quando a plataforma aceitar.\n\n"
    "AIFF: sem perdas e adequado a alguns fluxos de DAW/macOS.\n\n"
    "M4A/AAC: compacto e eficiente para armazenamento e reprodução geral; confirme a aceitação da plataforma."
)
TOOLS_HELP_TEXT = (
    "FFmpeg converte e exporta os áudios.\n\n"
    "FFprobe lê duração, tamanho, taxa de amostragem e canais.\n\n"
    "FFplay é usado pelo aplicativo para reprodução quando disponível.\n\n"
    "SoX é mantido disponível para compatibilidade com ferramentas de áudio do projeto."
)


class VoiceClonePreprocessorApp:
    TITLE = "REDIMENSIONAR ÁUDIO PARA CLONAR"

    def __init__(self, root, embedded=True, project_root: Path | None = None, project_actions=None):
        if not TK_AVAILABLE:
            raise RuntimeError(f"Tkinter indisponível: {TK_IMPORT_ERROR}")
        self.root = root
        self.embedded = embedded
        self.project_actions = project_actions or {}
        self.central_log_callback = self.project_actions.get("central_log")
        self.project_root = Path(project_root or Path.cwd()).expanduser().resolve()
        self.theme = {"mode": "claro", "root": "#F5F6FA", "surface": "#FFFFFF", "text": "#1F2937", "muted": "#64748B", "input": "#FFFFFF", "input_text": "#1F2937", "select": "#DBEAFE", "border": "#CBD5E1"}
        self.files: list[Path] = []
        self.info_by_path: dict[Path, AudioInfo] = {}
        self.pending_paths: set[Path] = set()
        self.worker: threading.Thread | None = None
        self.drop_thread: threading.Thread | None = None
        self.last_drop_signature = ""
        self.last_drop_time = 0.0
        self.running = False
        self.dependencies_running = False
        self.dependency_thread: threading.Thread | None = None
        self.tool_alert_after_id = None
        self.tool_alert_until = 0.0
        self.tool_alert_on = False
        self.cancel_event = threading.Event()
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.mode_var = StringVar(value="omnivoice")
        self.format_var = StringVar(value="wav")
        self.channels_var = StringVar(value="1")
        self.output_dir_var = StringVar(value=str(self.project_root / CLONE_OUTPUT_FOLDER_NAME))
        self.silence_db_var = StringVar(value="-35")
        self.silence_seconds_var = StringVar(value="0.20")
        self.omnivoice_seconds_var = StringVar(value="10")
        self.block_minutes_var = StringVar(value="30")
        self.normalize_var = StringVar(value="1")
        self.summary_var = StringVar(value="Arquivos: 0 | Duração total: 00:00:00 | Tamanho total: 0 B")
        self.selected_summary_var = StringVar(value="Selecionados: 0 | Duração: 00:00:00 | Tamanho: 0 B")
        self.mode_hint_var = StringVar(value="")
        self.status_var = StringVar(value="Adicione áudios para começar.")
        self.download_status_var = StringVar(value="Ferramentas: não verificadas")
        self.load_progress_var = StringVar(value="Carregamento: aguardando")
        self.process_progress_var = StringVar(value="Processamento: aguardando")
        self.audio_player = AudioPlayerManager(self.root, self.project_root, status_callback=lambda text: (self.status_var.set(text), self._log_central(text, "info")))
        self.build_ui()
        self.refresh_for_project()
        self.root.after(150, self.poll_messages)

    def build_ui(self):
        self.root.configure(bg="#F5F6FA")
        header = Frame(self.root, bg="#F5F6FA")
        header.pack(fill="x", padx=16, pady=(8, 3))
        Label(header, text=self.TITLE, bg="#F5F6FA", fg="#1F2937", font=("Segoe UI", 13, "bold")).pack(side="left")
        Label(header, text="  Corte, junção e normalização para clonagem de voz", bg="#F5F6FA", fg="#64748B", font=("Segoe UI", 9)).pack(side="left", padx=(12, 0))
        Label(self.root, textvariable=self.status_var, bg="#F5F6FA", fg="#64748B", anchor="w").pack(fill="x", padx=16, pady=(0, 6))

        source = Frame(self.root, bg="#FFFFFF", bd=1, relief="solid")
        source.pack(fill="x", padx=16, pady=(0, 7))
        Label(source, text="Áudios carregados — suporte a MP3, WAV, FLAC, M4A, OGG e AAC", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold"), anchor="w").grid(row=0, column=0, columnspan=5, sticky="ew", padx=10, pady=(8, 3))
        self.source_hint = Label(source, text="Arraste arquivos para a tabela ou use ADICIONAR ÁUDIOS. Use Ctrl/Shift para marcar somente os áudios desejados; sem marcação, todos serão usados.", bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8), anchor="w")
        self.source_hint.grid(row=1, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 5))
        table_frame = Frame(source, bg="#FFFFFF")
        table_frame.grid(row=2, column=0, columnspan=5, sticky="nsew", padx=10, pady=(0, 7))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        columns = ("name", "duration", "size", "format", "rate", "channels", "path")
        self.file_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended", height=7)
        headings = {"name": "Arquivo", "duration": "Duração", "size": "Tamanho", "format": "Formato", "rate": "Amostragem", "channels": "Canais", "path": "Caminho"}
        widths = {"name": 220, "duration": 92, "size": 90, "format": 105, "rate": 92, "channels": 65, "path": 320}
        for column in columns:
            self.file_tree.heading(column, text=headings[column])
            self.file_tree.column(column, width=widths[column], minwidth=55, anchor="w", stretch=column in {"name", "path"})
        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.file_tree.yview)
        tree_horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=tree_scroll.set, xscrollcommand=tree_horizontal.set)
        self.file_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        tree_horizontal.grid(row=1, column=0, sticky="ew")
        self.file_tree.bind("<Double-Button-1>", self._open_selected_file)
        self.file_tree.bind("<<TreeviewSelect>>", lambda _event: self._update_selected_metrics())
        self._enable_drag_drop(self.file_tree)
        self._enable_drag_drop(source)
        metrics = Frame(source, bg="#FFFFFF")
        metrics.grid(row=3, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 6))
        metrics.columnconfigure(1, weight=1)
        metrics.columnconfigure(3, weight=1)
        self.selected_info_var = StringVar(value="Selecione um arquivo para ver as barras de tamanho e duração.")
        Label(metrics, textvariable=self.selected_info_var, bg="#FFFFFF", fg="#475569", font=("Segoe UI", 8, "bold"), anchor="w").grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 3))
        self.size_meter_label = Label(metrics, text="Tamanho", bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8), anchor="w")
        self.size_meter_label.grid(row=1, column=0, sticky="w", padx=(0, 6))
        self.size_progress = ttk.Progressbar(metrics, orient="horizontal", mode="determinate", maximum=100, value=0, style="VoiceClone.Size.Horizontal.TProgressbar")
        self.size_progress.grid(row=1, column=1, sticky="ew", padx=(0, 12))
        self.duration_meter_label = Label(metrics, text="Duração", bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8), anchor="w")
        self.duration_meter_label.grid(row=1, column=2, sticky="w", padx=(0, 6))
        self.duration_progress = ttk.Progressbar(metrics, orient="horizontal", mode="determinate", maximum=100, value=0, style="VoiceClone.Duration.Horizontal.TProgressbar")
        self.duration_progress.grid(row=1, column=3, sticky="ew")
        loading_bar = Frame(source, bg="#FFFFFF")
        loading_bar.grid(row=4, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 5))
        Label(loading_bar, textvariable=self.load_progress_var, bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8), anchor="w").pack(side="left", padx=(0, 8))
        self.load_progress = ttk.Progressbar(loading_bar, orient="horizontal", mode="determinate", maximum=100, value=0, style="Download.Horizontal.TProgressbar")
        self.load_progress.pack(side="left", fill="x", expand=True)
        process_bar = Frame(source, bg="#FFFFFF")
        process_bar.grid(row=5, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 5))
        Label(process_bar, textvariable=self.process_progress_var, bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8), anchor="w").pack(side="left", padx=(0, 8))
        self.process_progress = ttk.Progressbar(process_bar, orient="horizontal", mode="determinate", maximum=100, value=0, style="Download.Horizontal.TProgressbar")
        self.process_progress.pack(side="left", fill="x", expand=True)
        actions = Frame(source, bg="#FFFFFF")
        actions.grid(row=6, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 8))
        self.add_button = Button(actions, text="ADICIONAR ÁUDIOS", command=self.add_files, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.add_button, self.theme, "primary")
        self.add_button.pack(side="left")
        self.open_folder_button = Button(actions, text="ABRIR PASTA", command=self.choose_folder, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.open_folder_button, self.theme, "teal")
        self.open_folder_button.pack(side="left", padx=6)
        self.load_format_button = Button(actions, text="CARREGAR DA CONVERSÃO DE FORMATOS", command=lambda: self.project_actions.get("load_voice_clone_from_format", self.load_from_format_conversion)(), relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2")
        apply_button_style(self.load_format_button, self.theme, "warning")
        self.load_format_button.pack(side="left", padx=6)
        self.select_all_button = Button(actions, text="SELECIONAR TODOS", command=self.select_all_files, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.select_all_button, self.theme, "secondary")
        self.select_all_button.pack(side="left", padx=6)
        self.clear_selection_button = Button(actions, text="LIMPAR SELEÇÃO", command=self.clear_selection, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.clear_selection_button, self.theme, "secondary")
        self.clear_selection_button.pack(side="left", padx=6)
        self.play_scene_button = Button(actions, text="▶ OUVIR CENA", command=self.play_selected_audio, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.play_scene_button, self.theme, "teal")
        self.play_scene_button.pack(side="left", padx=6)
        self.stop_audio_button = Button(actions, text="PARAR ÁUDIO", command=self.stop_audio, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.stop_audio_button, self.theme, "danger")
        self.stop_audio_button.pack(side="left", padx=6)
        self.clear_button = Button(actions, text="LIMPAR LISTA", command=self.clear_files, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.clear_button, self.theme, "danger")
        self.clear_button.pack(side="left", padx=6)
        summary_labels = Frame(source, bg="#FFFFFF")
        summary_labels.grid(row=7, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 8))
        Label(summary_labels, textvariable=self.summary_var, bg="#FFFFFF", fg="#475569", font=("Segoe UI", 8, "bold"), anchor="w").pack(side="left", fill="x", expand=True)
        Label(summary_labels, textvariable=self.selected_summary_var, bg="#FFFFFF", fg="#0F766E", font=("Segoe UI", 8, "bold"), anchor="e").pack(side="right")
        for index in range(5):
            source.grid_columnconfigure(index, weight=1 if index == 0 else 0)
        source.grid_rowconfigure(2, weight=1)

        options = Frame(self.root, bg="#FFFFFF", bd=1, relief="solid")
        options.pack(fill="x", padx=16, pady=(0, 7))
        Label(options, text="Destino da clonagem", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(8, 2))
        target_controls = Frame(options, bg="#FFFFFF")
        target_controls.grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(0, 8))
        target_values = [TARGET_LABELS[key] for key in TARGET_CHOICES]
        self.target_combo = ttk.Combobox(target_controls, values=target_values, state="readonly", width=30)
        self.target_combo.current(0)
        self.target_combo.pack(side="left")
        self.target_combo.bind("<<ComboboxSelected>>", self._target_changed)
        self.help_button = Button(target_controls, text="?", command=self.show_target_help, relief="flat", font=("Segoe UI", 9, "bold"), width=2, padx=0, pady=3, cursor="hand2")
        apply_button_style(self.help_button, self.theme, "secondary")
        self.help_button.pack(side="left", padx=(5, 0))
        self.target_help_tooltip = HoverTooltip(self.help_button, TARGET_HELP_TEXTS["omnivoice"])
        Label(options, text="Formato", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=6, pady=(8, 2))
        format_controls = Frame(options, bg="#FFFFFF")
        format_controls.grid(row=1, column=1, sticky="w", padx=6, pady=(0, 8))
        self.format_combo = ttk.Combobox(format_controls, textvariable=self.format_var, values=OUTPUT_FORMATS, state="readonly", width=10)
        self.format_combo.pack(side="left")
        self.format_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_selected_metrics())
        self.format_help_button = Button(format_controls, text="?", command=self.show_format_help, relief="flat", font=("Segoe UI", 9, "bold"), width=2, padx=0, pady=3, cursor="hand2")
        apply_button_style(self.format_help_button, self.theme, "secondary")
        self.format_help_button.pack(side="left", padx=(5, 0))
        self.format_help_tooltip = HoverTooltip(self.format_help_button, FORMAT_HELP_TEXT)
        Label(options, text="Canais", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=6, pady=(8, 2))
        self.channels_combo = ttk.Combobox(options, textvariable=self.channels_var, values=("1 — mono", "2 — estéreo"), state="readonly", width=14)
        self.channels_combo.current(0)
        self.channels_combo.grid(row=1, column=2, sticky="w", padx=6, pady=(0, 8))
        self.channels_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_selected_metrics())
        Label(options, text="Pasta de saída", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w", padx=6, pady=(8, 2))
        self.output_entry = Entry(options, textvariable=self.output_dir_var, relief="flat", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 8))
        self.output_entry.grid(row=1, column=3, sticky="ew", padx=6, pady=(0, 8))
        self.choose_output_button = Button(options, text="ESCOLHER", command=self.choose_output, relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=4, cursor="hand2")
        apply_button_style(self.choose_output_button, self.theme, "secondary")
        self.choose_output_button.grid(row=1, column=4, padx=(0, 10), pady=(0, 8))
        Label(options, textvariable=self.mode_hint_var, bg="#FFFFFF", fg="#475569", font=("Segoe UI", 8), justify="left", anchor="w", wraplength=940).grid(row=2, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 7))
        Label(options, text="Silêncio (dB)", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 8, "bold")).grid(row=3, column=0, sticky="w", padx=(10, 6), pady=(0, 2))
        Entry(options, textvariable=self.silence_db_var, width=9, relief="flat", bg="#FFFFFF", fg="#1F2937").grid(row=4, column=0, sticky="w", padx=(10, 6), pady=(0, 8))
        Label(options, text="Silêncio mínimo (s)", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 8, "bold")).grid(row=3, column=1, sticky="w", padx=6, pady=(0, 2))
        Entry(options, textvariable=self.silence_seconds_var, width=12, relief="flat", bg="#FFFFFF", fg="#1F2937").grid(row=4, column=1, sticky="w", padx=6, pady=(0, 8))
        Label(options, text="Alvo OmniVoice (s)", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 8, "bold")).grid(row=3, column=2, sticky="w", padx=6, pady=(0, 2))
        Entry(options, textvariable=self.omnivoice_seconds_var, width=12, relief="flat", bg="#FFFFFF", fg="#1F2937").grid(row=4, column=2, sticky="w", padx=6, pady=(0, 8))
        Label(options, text="Bloco Pro (min)", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 8, "bold")).grid(row=3, column=3, sticky="w", padx=6, pady=(0, 2))
        Entry(options, textvariable=self.block_minutes_var, width=12, relief="flat", bg="#FFFFFF", fg="#1F2937").grid(row=4, column=3, sticky="w", padx=6, pady=(0, 8))
        self.normalize_check = ttk.Checkbutton(options, text="Normalizar pico para −1 dBFS", variable=self.normalize_var, onvalue="1", offvalue="0")
        self.normalize_check.grid(row=4, column=4, sticky="e", padx=(6, 10), pady=(0, 8))
        for column in (0, 3):
            options.grid_columnconfigure(column, weight=1)

        bottom = Frame(self.root, bg="#F5F6FA")
        bottom.pack(fill="x", padx=16, pady=(0, 6))
        self.process_button = Button(bottom, text="PROCESSAR ÁUDIOS SELECIONADOS", command=self.start_processing, relief="flat", font=("Segoe UI", 10, "bold"), padx=16, pady=7, cursor="hand2")
        apply_button_style(self.process_button, self.theme, "success")
        self.process_button.pack(side="right")
        self.open_output_button = Button(bottom, text="ABRIR SAÍDA", command=self.open_output_folder, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2")
        apply_button_style(self.open_output_button, self.theme, "teal")
        self.open_output_button.pack(side="right", padx=(0, 6))
        tools_bar = Frame(self.root, bg="#F5F6FA")
        tools_bar.pack(fill="x", padx=16, pady=(0, 6))
        self.dependencies_button = Button(tools_bar, text="BAIXAR / PREPARAR FERRAMENTAS", command=self.start_dependency_setup, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2")
        apply_button_style(self.dependencies_button, self.theme, "teal")
        self.dependencies_button.pack(side="left")
        self.tools_help_button = Button(tools_bar, text="?", command=self.show_tools_help, relief="flat", font=("Segoe UI", 9, "bold"), width=2, padx=0, pady=3, cursor="hand2")
        apply_button_style(self.tools_help_button, self.theme, "secondary")
        self.tools_help_button.pack(side="left", padx=(5, 8))
        self.download_progress = ttk.Progressbar(tools_bar, orient="horizontal", mode="determinate", maximum=100, value=0, style="Download.Horizontal.TProgressbar")
        self.download_progress.pack(side="left", fill="x", expand=True, padx=(0, 8))
        Label(tools_bar, textvariable=self.download_status_var, bg="#F5F6FA", fg="#64748B", font=("Segoe UI", 8), anchor="w").pack(side="left", padx=(0, 5))
        Label(self.root, textvariable=self.mode_hint_var, bg="#F5F6FA", fg="#64748B", anchor="w", font=("Segoe UI", 8)).pack(fill="x", padx=16)
        self.log_box = Text(self.root, height=5, wrap="word", state="disabled", font=("Consolas", 8), bg="#111827", fg="#E5E7EB")
        self.log_box.pack(fill="x", padx=16, pady=(3, 7))
        self.folder_bar = Frame(self.root, bg="#F5F6FA")
        self.folder_bar.pack(fill="x", padx=16, pady=(0, 9))
        self.refresh_folder_buttons()
        self._target_changed()
        self._update_selected_metrics()

    def _enable_drag_drop(self, widget):
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", lambda event: self.handle_drop(event.data))
        except Exception:
            pass

    def _target_changed(self, _event=None):
        target = self.current_target()
        if target == "omnivoice":
            hint = "OmniVoice: escolhe um segmento de 5–20 s, no máximo 25 s, preferencialmente entre pausas."
        elif target == "eleven_instant":
            hint = "ElevenLabs Instant: alvo de 60–180 s; a recomendação atual é cerca de 1–2 min de áudio limpo. Limite interno de 400 MB."
        else:
            hint = "ElevenLabs Professional: junta os áudios e divide em blocos de 30–45 min, para um total de até 180 min. Limite interno de 450 MB por bloco."
        self.mode_hint_var.set(i18n.tr(hint))
        if hasattr(self, "target_help_tooltip"):
            self.target_help_tooltip.text = TARGET_HELP_TEXTS.get(target, TARGET_HELP_TEXTS["omnivoice"])
        self._update_selected_metrics()

    def show_target_help(self):
        target = self.current_target()
        messagebox.showinfo(i18n.tr("Destino da clonagem"), i18n.tr(TARGET_HELP_TEXTS.get(target, TARGET_HELP_TEXTS["omnivoice"])), parent=self.root)

    def folder_button_definitions(self):
        return (
            ("WAV ORIGINAL", self.project_root / "WAV ORIGINAIS", "primary"),
            ("WAV DUBLADO", self.project_root / "dublado", "accent"),
            ("REVISÕES", self.project_root / "revisoes", "success"),
            ("TXT PT", self.project_root / "TXT TEXTO PORTUGUES", "warning"),
            ("TXT ORIGINAL", self.project_root / "TXT TEXTO ORIGINAL", "secondary"),
            ("TXT TRANSCRITO", self.project_root / "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO", "teal"),
            ("OUTRAS TRADUÇÕES", self.project_root / "OUTRAS TRADUÇÕES", "accent"),
            (CLONE_OUTPUT_FOLDER_NAME, self.project_root / CLONE_OUTPUT_FOLDER_NAME, "highlight"),
        )

    def refresh_folder_buttons(self):
        if not hasattr(self, "folder_bar"):
            return
        for child in self.folder_bar.winfo_children():
            child.destroy()
        for label, path, role in self.folder_button_definitions():
            self.make_folder_button(self.folder_bar, label, path, role).pack(side="left", padx=3)

    def make_folder_button(self, parent, text: str, path: Path, role: str):
        button = Button(parent, text=i18n.tr(text), command=lambda target=path, name=text: self.open_folder(target, name), relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=4, cursor="hand2")
        apply_button_style(button, self.theme, role)
        return button

    def open_folder(self, path: Path, label: str):
        folder = Path(path).expanduser().resolve()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(folder))
            elif os.sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.status_var.set(f"Pasta aberta: {i18n.tr(label)}")
        except Exception as exc:
            messagebox.showerror("Pasta", f"Não foi possível abrir {label}:\n{folder}\n\n{exc}", parent=self.root)

    def selected_paths(self, fallback_to_all: bool = True) -> list[Path]:
        if not hasattr(self, "file_tree"):
            return []
        selected_ids = {str(item) for item in self.file_tree.selection()}
        selected = [path for path in self.files if str(path) in selected_ids]
        if not selected and fallback_to_all:
            return list(self.files)
        return selected

    def select_all_files(self):
        if self.files:
            self.file_tree.selection_set(*(str(path) for path in self.files))
            self._update_selected_metrics()
            self.status_var.set(f"{len(self.files)} áudio(s) marcado(s) para processamento e junção.")

    def clear_selection(self):
        self.file_tree.selection_remove(*self.file_tree.selection())
        self._update_selected_metrics()
        if self.files:
            self.status_var.set("Nenhuma marcação específica: PROCESSAR ÁUDIOS usará toda a lista carregada.")

    def play_selected_audio(self):
        paths = self.selected_paths(fallback_to_all=False)
        if not paths:
            messagebox.showinfo("OUVIR CENA", "Selecione um áudio na tabela para ouvir.", parent=self.root)
            return
        self.audio_player.play_one(paths[0], f"OUVIR CENA — {paths[0].name}", playlist=paths, index=0)

    def stop_audio(self):
        self.audio_player.stop()
        self.status_var.set("Reprodução parada.")

    def _estimate_encoded_size(self, duration_seconds: float, output_format: str, channels: int) -> int:
        duration_seconds = max(0.0, float(duration_seconds))
        output_format = str(output_format).casefold().lstrip(".")
        channels = 2 if channels == 2 else 1
        if output_format in FORMAT_BITRATE_ESTIMATES:
            return int(duration_seconds * FORMAT_BITRATE_ESTIMATES[output_format] / 8)
        if output_format in {"wav", "aiff"}:
            return int(duration_seconds * 44100 * 2 * channels + 4096)
        if output_format == "flac":
            return int(duration_seconds * 44100 * 2 * channels * FORMAT_COMPRESSION_FACTORS["flac"] + 4096)
        return int(duration_seconds * 44100 * 2 * channels + 4096)

    def _estimated_output(self, input_duration: float) -> tuple[float, int, int | None]:
        target = self.current_target()
        mode = MODES[target]
        try:
            channels = 2 if self.channels_combo.get().startswith("2") else 1
        except Exception:
            channels = 1
        output_format = i18n.source_text(self.format_var.get()) or "wav"
        final_duration = min(max(0.0, input_duration), mode.maximum_seconds)
        estimated_total = self._estimate_encoded_size(final_duration, output_format, channels)
        estimated_peak = None
        if target == "eleven_pro":
            try:
                block_seconds = float(self.block_minutes_var.get().strip()) * 60.0
            except (AttributeError, ValueError):
                block_seconds = 30.0 * 60.0
            block_seconds = max(mode.block_minimum_seconds or 1800.0, min(mode.block_maximum_seconds or 2700.0, block_seconds))
            estimated_peak = self._estimate_encoded_size(min(block_seconds, final_duration or block_seconds), output_format, channels)
            estimated_total = self._estimate_encoded_size(final_duration, output_format, channels)
        return final_duration, estimated_total, estimated_peak

    def _update_selected_metrics(self):
        if not hasattr(self, "file_tree"):
            return
        explicit_selection = bool(self.file_tree.selection())
        selected = self.selected_paths(fallback_to_all=True)
        if not selected:
            self.selected_info_var.set(i18n.tr("Selecione um arquivo para ver as barras de tamanho e duração."))
            self.selected_summary_var.set(i18n.tr("Selecionados: 0 | Duração: 00:00:00 | Tamanho: 0 B"))
            self.size_meter_label.configure(text=i18n.tr("Saída estimada"))
            self.duration_meter_label.configure(text=i18n.tr("Duração final"))
            self.size_progress.configure(value=0)
            self.duration_progress.configure(value=0)
            return
        infos = [self.info_by_path[path] for path in selected if path in self.info_by_path]
        if not infos:
            return
        total_size = sum(info.size_bytes for info in infos)
        total_duration = sum(info.duration for info in infos)
        target = self.current_target()
        mode = MODES[target]
        final_duration, estimated_total, estimated_peak = self._estimated_output(total_duration)
        size_for_bar = estimated_peak if target == "eleven_pro" and estimated_peak is not None else estimated_total
        channels = 2 if self.channels_combo.get().startswith("2") else 1
        format_name = i18n.source_text(self.format_var.get()) or "wav"
        natural_max_size = self._estimate_encoded_size(mode.maximum_seconds, format_name, channels)
        size_limit = natural_max_size
        if mode.maximum_bytes is not None:
            size_limit = min(mode.maximum_bytes, natural_max_size) if natural_max_size > 0 else mode.maximum_bytes
        size_limit = max(1, size_limit)
        duration_limit = mode.maximum_seconds
        size_percent = min(100.0, size_for_bar / size_limit * 100.0)
        duration_percent = min(100.0, final_duration / max(1.0, duration_limit) * 100.0)
        self.size_progress.configure(value=size_percent)
        self.duration_progress.configure(value=duration_percent)
        count_label = i18n.tr("Selecionados:") if explicit_selection else i18n.tr("Conjunto completo:")
        format_label = str(i18n.source_text(self.format_var.get()) or "wav").upper()
        output_size_label = format_bytes(estimated_total)
        if target == "eleven_pro" and estimated_peak is not None:
            output_size_label = f"{output_size_label} total; {format_bytes(estimated_peak)} maior bloco"
        if explicit_selection and len(infos) == 1:
            selection_detail = f"{infos[0].path.name} | "
        else:
            selection_detail = ""
        self.selected_info_var.set(f"{count_label} {selection_detail}{len(infos)} | entrada: {format_bytes(total_size)} / {format_seconds(total_duration)} | saída {format_label}: {output_size_label} / {format_seconds(final_duration)}")
        self.selected_summary_var.set(f"{i18n.tr('Selecionados:')} {len(infos)} / {len(self.files)} | {i18n.tr('Duração final')}: {format_seconds(final_duration)} | {i18n.tr('Saída estimada')}: {output_size_label}")
        self.size_meter_label.configure(text=f"{i18n.tr('Saída estimada')} ({output_size_label})")
        self.duration_meter_label.configure(text=f"{i18n.tr('Duração final')} ({format_seconds(final_duration)})")

    def current_target(self) -> str:
        try:
            index = self.target_combo.current()
            if 0 <= index < len(TARGET_CHOICES):
                return TARGET_CHOICES[index]
        except Exception:
            pass
        selected = self.target_combo.get()
        source = i18n.source_text(selected)
        for key, label in TARGET_LABELS.items():
            if selected == label or selected == i18n.tr(label) or source == label:
                return key
        return "omnivoice"

    def make_processor(self, silence_db: int = -35, silence_seconds: float = 0.20) -> AudioCloneProcessor:
        ffmpeg_path = executable_path("ffmpeg", self.project_root)
        ffprobe_path = executable_path("ffprobe", self.project_root)
        return AudioCloneProcessor(ffmpeg=ffmpeg_path or "ffmpeg", ffprobe=ffprobe_path or "ffprobe", silence_db=silence_db, silence_seconds=silence_seconds)

    def _parse_paths(self, raw: str) -> list[Path]:
        try:
            values = list(self.root.tk.splitlist(raw))
        except Exception:
            values = [raw]
        return [Path(str(value).strip().strip('"')).expanduser().resolve() for value in values if str(value).strip()]

    def add_files(self):
        selected = filedialog.askopenfilenames(parent=self.root, title="Selecionar áudios para clonar", filetypes=[("Áudios", "*.mp3 *.wav *.wave *.flac *.m4a *.ogg *.aac"), ("Todos os arquivos", "*.*")])
        if selected:
            self._add_paths([Path(item) for item in selected])

    def choose_folder(self):
        selected = filedialog.askdirectory(parent=self.root, title="Escolher pasta com áudios para clonar")
        if selected:
            folder = Path(selected).expanduser().resolve()
            self._add_paths([path for path in folder.rglob("*") if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS])

    def load_from_format_conversion(self, files: list[Path] | None = None):
        source_files = [Path(path) for path in (files or [])]
        if not source_files:
            output_folder = self.project_root / "AUDIO FORMATOS CONVERTIDOS"
            if output_folder.is_dir():
                source_files = [path for path in output_folder.rglob("*") if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS]
        if not source_files:
            self.status_var.set("Nenhum áudio disponível na aba CONVERTER FORMATOS.")
            return
        self._begin_async_load(source_files, "CONVERSÃO DE FORMATOS")

    def _begin_async_load(self, paths: list[Path], source_label: str):
        if self.pending_paths or (self.drop_thread is not None and self.drop_thread.is_alive()):
            self.status_var.set("Aguarde o carregamento de áudios já iniciado terminar.")
            return
        candidates: list[Path] = []
        seen = {str(path).casefold() for path in self.files}
        seen.update(str(path).casefold() for path in self.pending_paths)
        for raw in paths:
            path = Path(raw).expanduser().resolve()
            key = str(path).casefold()
            if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS and key not in seen:
                seen.add(key)
                candidates.append(path)
        if not candidates:
            self.status_var.set("Nenhum áudio novo compatível para carregar.")
            return
        self.pending_paths.update(candidates)
        self.files.extend(candidates)
        self.files.sort(key=lambda path: str(path).casefold())
        self.load_progress.stop()
        self.load_progress.configure(mode="determinate", value=0)
        self.load_progress_var.set(f"Carregando {len(candidates)} áudio(s) de {source_label}: 0%")
        self.status_var.set(f"{len(candidates)} áudio(s) exibido(s); lendo duração e metadados em segundo plano...")
        self._refresh_file_tree()
        self.drop_thread = threading.Thread(target=self._probe_dropped_paths, args=(candidates, source_label), daemon=True)
        self.drop_thread.start()

    def handle_drop(self, raw: str):
        signature = str(raw or "").strip()
        now = time.monotonic()
        if signature and signature == self.last_drop_signature and now - self.last_drop_time < 1.0:
            return
        self.last_drop_signature = signature
        self.last_drop_time = now
        paths: list[Path] = []
        for item in self._parse_paths(raw):
            if item.is_dir():
                try:
                    paths.extend(path for path in item.rglob("*") if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS)
                except (OSError, PermissionError):
                    continue
            elif item.is_file() and item.suffix.casefold() in SUPPORTED_EXTENSIONS:
                paths.append(item)
        if not paths:
            self.status_var.set(i18n.tr("Nenhum áudio compatível foi carregado."))
            return
        self._begin_async_load(paths, "ARRASTE")

    def _probe_dropped_paths(self, paths: list[Path], source_label: str = "ARRASTE"):
        probed: dict[Path, AudioInfo] = {}
        errors: list[str] = []
        processor = self.make_processor()
        total = len(paths)
        for index, raw in enumerate(paths, start=1):
            path = raw.expanduser().resolve()
            try:
                probed[path] = processor.probe(path)
            except AudioProcessingError as exc:
                errors.append(f"Ignorado {path.name}: {exc}")
            self.queue.put(("load_progress", (source_label, index, total)))
        self.queue.put(("load_ready", (paths, probed, errors, source_label)))

    def _add_paths(self, paths: list[Path], probed_infos: dict[Path, AudioInfo] | None = None):
        probed_infos = probed_infos or {}
        seen = {str(path).casefold() for path in self.files}
        for raw in paths:
            path = raw.expanduser().resolve()
            if not path.is_file() or path.suffix.casefold() not in SUPPORTED_EXTENSIONS or str(path).casefold() in seen:
                continue
            try:
                info = probed_infos.get(path) or self.make_processor().probe(path)
            except AudioProcessingError as exc:
                self.append_log(f"Ignorado {path.name}: {exc}")
                continue
            self.files.append(path)
            self.info_by_path[path] = info
            seen.add(str(path).casefold())
        self.files.sort(key=lambda path: str(path).casefold())
        self._refresh_file_tree()
        if self.files:
            self.status_var.set(f"{len(self.files)} {i18n.tr('áudio(s) carregado(s).')}")
        else:
            self.status_var.set(i18n.tr("Nenhum áudio compatível foi carregado."))

    def _refresh_file_tree(self):
        selected_ids = set(self.file_tree.selection()) if hasattr(self, "file_tree") else set()
        self.file_tree.delete(*self.file_tree.get_children())
        total_duration = 0.0
        total_size = 0
        for path in self.files:
            info = self.info_by_path.get(path)
            if info is None:
                values = (path.name, "carregando...", "carregando...", path.suffix.upper(), "—", "—", str(path))
            else:
                total_duration += info.duration
                total_size += info.size_bytes
                values = (path.name, format_seconds(info.duration), format_bytes(info.size_bytes), info.format_name or path.suffix.upper(), f"{info.sample_rate or 0} Hz", str(info.channels or "?"), str(path))
            self.file_tree.insert("", END, iid=str(path), values=values)
        for item in selected_ids:
            if self.file_tree.exists(item):
                self.file_tree.selection_add(item)
        self.summary_var.set(f"{i18n.tr('Arquivos:')} {len(self.files)} | {i18n.tr('Duração total:')} {format_seconds(total_duration)} | {i18n.tr('Tamanho total:')} {format_bytes(total_size)}")
        self._update_selected_metrics()

    def clear_files(self):
        if self.running:
            return
        self.audio_player.stop(announce=False)
        self.files = []
        self.info_by_path.clear()
        self.pending_paths.clear()
        self.load_progress.stop()
        self.load_progress.configure(mode="determinate", value=0)
        self.load_progress_var.set("Carregamento: aguardando")
        self._refresh_file_tree()
        self.status_var.set(i18n.tr("Lista limpa. Nenhum arquivo do disco foi alterado."))

    def choose_output(self):
        selected = filedialog.askdirectory(parent=self.root, title="Escolher pasta raiz de saída")
        if selected:
            self.output_dir_var.set(str(Path(selected).expanduser().resolve()))

    def open_output_folder(self):
        # O botão ABRIR SAÍDA aponta sempre para a pasta principal da ferramenta,
        # exatamente a mesma exibida na barra inferior; as subpastas dos destinos
        # ficam dentro dela.
        path = (self.project_root / CLONE_OUTPUT_FOLDER_NAME).expanduser().resolve()
        try:
            path.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(path))
            elif os.sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            messagebox.showerror("Pasta de saída", f"Não foi possível abrir a pasta:\n{path}\n\n{exc}", parent=self.root)

    def _open_selected_file(self, _event=None):
        # Duplo clique também significa OUVIR CENA; nunca abrir o reprodutor padrão.
        self.play_selected_audio()

    def start_processing(self):
        if self.running:
            self.cancel_event.set()
            self.status_var.set("Cancelamento solicitado...")
            return
        if not self.files:
            messagebox.showinfo("Processar áudios", "Adicione pelo menos um áudio.", parent=self.root)
            return
        if self.pending_paths:
            self.status_var.set("Aguarde o carregamento dos metadados terminar antes de processar.")
            return
        selected_paths = self.selected_paths(fallback_to_all=True)
        if not selected_paths:
            messagebox.showinfo("Processar áudios", "Selecione pelo menos um áudio.", parent=self.root)
            return
        try:
            silence_db = int(self.silence_db_var.get().strip())
            silence_seconds = float(self.silence_seconds_var.get().strip())
            omni_seconds = float(self.omnivoice_seconds_var.get().strip())
            block_minutes = float(self.block_minutes_var.get().strip())
        except ValueError:
            messagebox.showerror("Parâmetros", "Confira os valores numéricos dos parâmetros.", parent=self.root)
            return
        self.running = True
        self.cancel_event.clear()
        self.process_progress.stop()
        self.process_progress.configure(mode="determinate", value=0)
        self.process_progress_var.set("Processamento: 0% — iniciando")
        self.process_button.configure(text="CANCELAR PROCESSAMENTO")
        selected_label = "selecionado(s)" if self.file_tree.selection() else "da lista"
        self.status_var.set(f"Juntando {len(selected_paths)} áudio(s) {selected_label} e preparando para {self.target_combo.get()}...")
        args = (selected_paths, self.current_target(), self.output_dir_var.get(), self.format_var.get(), self.channels_combo.get(), silence_db, silence_seconds, omni_seconds, block_minutes, self.normalize_var.get() == "1")
        self.worker = threading.Thread(target=self._worker, args=args, daemon=True)
        self.worker.start()

    def _worker(self, paths, target, output_root, output_format, channels_value, silence_db, silence_seconds, omni_seconds, block_minutes, normalize):
        try:
            channels = 2 if channels_value.startswith("2") else 1
            processor = self.make_processor(silence_db=silence_db, silence_seconds=silence_seconds)
            def on_progress(percent, stage):
                self.queue.put(("process_progress", (percent, stage)))
            report = processor.process(paths, target, output_root=Path(output_root), output_format=output_format, channels=channels, normalize=normalize, omnivoice_seconds=omni_seconds, block_minutes=block_minutes, progress_callback=on_progress)
            self.queue.put(("done", report))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def poll_messages(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self.append_log(str(payload))
                elif kind == "download_progress":
                    description, downloaded, total = payload
                    percent = update_download_progress(self.download_progress, description, downloaded, total)
                    if total:
                        self.download_status_var.set(f"Baixando {description}: {percent:.1f}%")
                    else:
                        self.download_status_var.set(f"Baixando {description}: {percent:.1f}% estimado; tamanho final ainda não informado")
                elif kind == "download_complete":
                    update_download_progress(self.download_progress, str(payload), 1, 1)
                elif kind == "load_progress":
                    source_label, index, total = payload
                    percent = min(100.0, index * 100.0 / max(1, total))
                    self.load_progress.stop()
                    self.load_progress.configure(mode="determinate", value=max(float(self.load_progress.cget("value")), percent))
                    self.load_progress_var.set(f"Carregando {total} áudio(s) de {source_label}: {percent:.1f}% ({index}/{total})")
                    self._refresh_file_tree()
                elif kind == "load_ready":
                    paths, probed_infos, errors, source_label = payload
                    self.drop_thread = None
                    for path in paths:
                        self.pending_paths.discard(Path(path).expanduser().resolve())
                    for path, info in probed_infos.items():
                        self.info_by_path[Path(path).expanduser().resolve()] = info
                    self._refresh_file_tree()
                    for error in errors:
                        self.append_log(error)
                    self.load_progress.stop()
                    self.load_progress.configure(mode="determinate", value=100 if not errors or probed_infos else max(float(self.load_progress.cget("value")), 0))
                    self.load_progress_var.set(f"Carregamento de {source_label} concluído: {len(probed_infos)}/{len(paths)} áudio(s) pronto(s).")
                    if errors:
                        self.status_var.set(f"Carregamento concluído com {len(errors)} aviso(s); confira o painel de mensagens.")
                    elif paths:
                        self.status_var.set(f"{len(paths)} áudio(s) carregado(s) e pronto(s) para seleção.")
                elif kind == "process_progress":
                    percent, stage = payload
                    try:
                        current = float(self.process_progress.cget("value"))
                    except Exception:
                        current = 0.0
                    percent = max(current, min(100.0, float(percent)))
                    self.process_progress.stop()
                    self.process_progress.configure(mode="determinate", value=percent)
                    self.process_progress_var.set(f"Processamento: {percent:.1f}% — {stage}")
                elif kind == "dependencies_done":
                    self.dependencies_running = False
                    self.dependencies_button.configure(state="normal")
                    self.download_progress.stop()
                    self.download_progress.configure(mode="determinate", value=max(float(self.download_progress.cget("value")), 100.0) if not self.missing_tools() else 0)
                    self.download_status_var.set(str(payload))
                    self.status_var.set(str(payload))
                    if self.missing_tools():
                        self.start_tool_alert()
                elif kind == "done":
                    report = payload
                    self.running = False
                    self.process_progress.stop()
                    self.process_progress.configure(mode="determinate", value=100)
                    self.process_progress_var.set("Processamento: 100% — concluído")
                    self.process_button.configure(text="PROCESSAR ÁUDIOS")
                    self.status_var.set(f"Concluído: {len(report.outputs)} arquivo(s) salvo(s) em {report.output_dir}.")
                    self.append_log(f"Processamento {report.target} concluído: {len(report.outputs)} saída(s), {format_seconds(report.output_duration)}.")
                    for warning in report.warnings:
                        self.append_log(f"AVISO: {warning}")
                elif kind == "error":
                    self.running = False
                    try:
                        current = float(self.process_progress.cget("value"))
                    except Exception:
                        current = 0.0
                    self.process_progress.stop()
                    self.process_progress.configure(mode="determinate", value=current)
                    self.process_progress_var.set(f"Processamento interrompido em {current:.1f}%")
                    self.process_button.configure(text="PROCESSAR ÁUDIOS")
                    self.status_var.set("Falha no processamento.")
                    self.append_log(f"ERRO: {payload}")
                    messagebox.showerror("Processamento", str(payload), parent=self.root)
        except queue.Empty:
            pass
        try:
            if self.root.winfo_exists():
                self.root.after(150, self.poll_messages)
        except Exception:
            pass

    def _log_central(self, text, tag="normal") -> None:
        callback = getattr(self, "central_log_callback", None)
        if callable(callback):
            try:
                callback("REDIMENSIONAR PARA CLONAR", str(text), tag)
            except Exception:
                pass

    def append_log(self, text: str):
        self._log_central(text, "error" if str(text).startswith("ERRO") else "normal")
        self.log_box.configure(state="normal")
        self.log_box.insert(END, text + "\n")
        self.log_box.see(END)
        self.log_box.configure(state="disabled")

    def missing_tools(self) -> list[str]:
        return [name for name in ("ffmpeg", "ffprobe", "ffplay") if executable_path(name, self.project_root) is None]

    def stop_tool_alert(self):
        after_id = self.tool_alert_after_id
        self.tool_alert_after_id = None
        self.tool_alert_until = 0.0
        self.tool_alert_on = False
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        try:
            apply_button_style(self.dependencies_button, self.theme, "teal")
        except Exception:
            pass

    def start_tool_alert(self):
        missing = self.missing_tools()
        if not missing or self.dependencies_running:
            self.stop_tool_alert()
            return
        if self.tool_alert_after_id is None:
            self.tool_alert_until = time.monotonic() + 2.0
            self.tool_alert_on = False
            self.tool_alert_tick()
        self.status_var.set("Faltam ferramentas: " + ", ".join(missing) + ". Clique em BAIXAR / PREPARAR FERRAMENTAS.")

    def tool_alert_tick(self):
        if time.monotonic() >= self.tool_alert_until or self.dependencies_running:
            self.stop_tool_alert()
            return
        self.tool_alert_on = not self.tool_alert_on
        try:
            apply_button_style(self.dependencies_button, self.theme, "danger" if self.tool_alert_on else "teal")
            self.tool_alert_after_id = self.root.after(220, self.tool_alert_tick)
        except Exception:
            self.tool_alert_after_id = None

    def tool_storage_dir(self) -> Path:
        return self.project_root / TOOLS_DIR_NAME

    def safe_extract_zip(self, archive_path: Path, destination: Path):
        destination.mkdir(parents=True, exist_ok=True)
        base = destination.resolve()
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                target = (destination / info.filename).resolve()
                if target != base and base not in target.parents:
                    raise RuntimeError(f"Arquivo inseguro no pacote baixado: {info.filename}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)

    def download_and_extract(self, url: str, destination: Path, description: str) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="dublaskizon_audio_tools_"))
        archive_path = temp_dir / f"{description}.zip"
        try:
            self.queue.put(("log", f"Baixando {description}..."))
            self.queue.put(("download_progress", (description, 0, 0)))
            request = urllib.request.Request(url, headers={"User-Agent": "Dublaskizon/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as output:
                total_header = response.headers.get("Content-Length")
                total = int(total_header) if total_header and total_header.isdigit() else 0
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    self.queue.put(("download_progress", (description, downloaded, total)))
            extracted = temp_dir / "extraido"
            self.safe_extract_zip(archive_path, extracted)
            self.queue.put(("download_complete", description))
            return extracted
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def copy_executables_from_tree(self, source_root: Path, names: set[str], destination: Path) -> list[Path]:
        destination.mkdir(parents=True, exist_ok=True)
        wanted = {name.casefold() for name in names}
        copied = []
        for candidate in source_root.rglob("*"):
            if candidate.is_file() and candidate.name.casefold() in wanted:
                target = destination / candidate.name
                shutil.copy2(candidate, target)
                copied.append(target)
        return copied

    def copy_sibling_runtime_files(self, source_root: Path, executable_name: str, destination: Path):
        executable = next((path for path in source_root.rglob(executable_name) if path.is_file()), None)
        if executable is None:
            return
        destination.mkdir(parents=True, exist_ok=True)
        for sibling in executable.parent.iterdir():
            if sibling.is_file() and sibling.suffix.casefold() in {".dll", ".exe"}:
                shutil.copy2(sibling, destination / sibling.name)

    def dependency_worker(self):
        try:
            if os.name != "nt":
                self.queue.put(("download_progress", ("ferramentas", 1, 1)))
                self.queue.put(("dependencies_done", "Neste sistema, o aplicativo usa FFmpeg/FFprobe disponíveis no PATH."))
                return
            tools_dir = self.tool_storage_dir()
            tools_dir.mkdir(parents=True, exist_ok=True)
            if all(executable_path(name, self.project_root) is not None for name in ("ffmpeg", "ffprobe", "ffplay")):
                self.queue.put(("log", "FFmpeg, FFprobe e FFplay já estão disponíveis; download ignorado."))
            else:
                extracted = self.download_and_extract(FFMPEG_WINDOWS_URL, tools_dir / "ffmpeg", "ffmpeg")
                copied = self.copy_executables_from_tree(extracted, {"ffmpeg.exe", "ffprobe.exe", "ffplay.exe"}, tools_dir)
                self.copy_sibling_runtime_files(extracted, "ffmpeg.exe", tools_dir)
                copied_names = {path.name.casefold() for path in copied}
                if not copied_names.issuperset({"ffmpeg.exe", "ffprobe.exe", "ffplay.exe"}):
                    raise RuntimeError("O pacote do FFmpeg não continha ffmpeg.exe, ffprobe.exe e ffplay.exe.")
                self.queue.put(("log", "FFmpeg, FFprobe e FFplay foram preparados em ferramentas_audio."))
            self.queue.put(("download_progress", ("ferramentas", 1, 1)))
            self.queue.put(("dependencies_done", "Ferramentas de áudio preparadas."))
        except Exception as exc:
            self.queue.put(("log", f"ERRO ao preparar ferramentas: {exc}"))
            self.queue.put(("download_progress", ("ferramentas", 0, 1)))
            self.queue.put(("dependencies_done", "Não foi possível preparar as ferramentas; confira o painel de processos."))

    def show_tools_help(self):
        messagebox.showinfo("Ferramentas de áudio", TOOLS_HELP_TEXT, parent=self.root)

    def start_dependency_setup(self):
        self.stop_tool_alert()
        if self.dependencies_running or self.running:
            return
        self.dependencies_running = True
        self.dependencies_button.configure(state="disabled")
        self.download_progress.configure(mode="determinate", value=0)
        self.download_status_var.set("Preparando ferramentas...")
        self.status_var.set("Preparando FFmpeg e FFprobe; aguarde...")
        self.dependency_thread = threading.Thread(target=self.dependency_worker, daemon=True)
        self.dependency_thread.start()

    def show_format_help(self):
        messagebox.showinfo("Formatos de saída", FORMAT_HELP_TEXT, parent=self.root)

    def show_help(self):
        messagebox.showinfo(i18n.tr("REDIMENSIONAR ÁUDIO PARA CLONAR"), i18n.tr("AJUDA DA CLONAGEM"), parent=self.root)

    def refresh_for_project(self):
        new_root = Path(getattr(self.root, "project_root", self.project_root)).expanduser().resolve()
        self.project_root = new_root
        self.audio_player.set_project_root(self.project_root)
        if not self.files:
            self.output_dir_var.set(str(self.project_root / CLONE_OUTPUT_FOLDER_NAME))
        self.start_tool_alert()

    def apply_language(self, language: str | None = None):
        code = i18n.set_current_language(language or i18n.CURRENT_LANGUAGE)
        target = self.current_target()
        self.target_combo.configure(values=tuple(i18n.tr(TARGET_LABELS[key], code) for key in TARGET_CHOICES))
        self.target_combo.current(TARGET_CHOICES.index(target))
        channel_index = 1 if self.channels_combo.current() == 1 else 0
        self.channels_combo.configure(values=(i18n.tr("1 — mono", code), i18n.tr("2 — estéreo", code)))
        self.channels_combo.current(channel_index)
        for widget, source in (
            (self.add_button, "ADICIONAR ÁUDIOS"),
            (self.open_folder_button, "ABRIR PASTA"),
            (self.load_format_button, "CARREGAR DA CONVERSÃO DE FORMATOS"),
            (self.select_all_button, "SELECIONAR TODOS"),
            (self.clear_selection_button, "LIMPAR SELEÇÃO"),
            (self.play_scene_button, "▶ OUVIR CENA"),
            (self.stop_audio_button, "PARAR ÁUDIO"),
            (self.clear_button, "LIMPAR LISTA"),
            (self.choose_output_button, "ESCOLHER"),
            (self.process_button, "CANCELAR PROCESSAMENTO" if self.running else "PROCESSAR ÁUDIOS SELECIONADOS"),
            (self.open_output_button, "ABRIR SAÍDA"),
        ):
            widget.configure(text=i18n.tr(source, code))
        for column in ("name", "duration", "size", "format", "rate", "channels", "path"):
            headings = {"name": "Arquivo", "duration": "Duração", "size": "Tamanho", "format": "Formato", "rate": "Amostragem", "channels": "Canais", "path": "Caminho"}
            self.file_tree.heading(column, text=i18n.tr(headings[column], code))
        self.source_hint.configure(text=i18n.tr("Arraste arquivos para a tabela ou use ADICIONAR ÁUDIOS. Use Ctrl/Shift para marcar somente os áudios desejados; sem marcação, todos serão usados.", code))
        self._target_changed()
        self._update_selected_metrics()
        self._refresh_file_tree()
        self.refresh_folder_buttons()

    def apply_theme(self, theme):
        self.theme = {**self.theme, **theme}
        surface = self.theme.get("surface", "#FFFFFF")
        root_bg = self.theme.get("root", "#F5F6FA")
        text = self.theme.get("text", "#1F2937")
        muted = self.theme.get("muted", "#64748B")
        input_bg = self.theme.get("input", surface)
        input_fg = self.theme.get("input_text", text)
        select = self.theme.get("select", "#DBEAFE")
        try:
            self.root.configure(bg=root_bg)
            style = ttk.Style(self.root)
            configure_ttk_button_styles(style, self.theme)
            style.configure("TFrame", background=surface)
            style.configure("TLabel", background=surface, foreground=text)
            style.configure("TCheckbutton", background=surface, foreground=text)
            style.configure("TCombobox", fieldbackground=input_bg, background=input_bg, foreground=input_fg)
            style.configure("VoiceClone.Treeview", background=input_bg, fieldbackground=input_bg, foreground=input_fg, rowheight=25)
            style.map("VoiceClone.Treeview", background=[("selected", select)], foreground=[("selected", input_fg)])
            style.configure("VoiceClone.Size.Horizontal.TProgressbar", troughcolor=self.theme.get("border", "#CBD5E1"), background=self.theme.get("accent", "#7C3AED"))
            style.configure("VoiceClone.Duration.Horizontal.TProgressbar", troughcolor=self.theme.get("border", "#CBD5E1"), background=self.theme.get("success", "#15803D"))
            track_color = self.theme.get("border", "#CBD5E1")
            download_color = self.theme.get("warning", "#F97316")
            style.configure("Download.Horizontal.TProgressbar", troughcolor=track_color, background=download_color, lightcolor=download_color, darkcolor=download_color)
            self.download_progress.configure(style="Download.Horizontal.TProgressbar")
            if hasattr(self, "load_progress"):
                self.load_progress.configure(style="Download.Horizontal.TProgressbar")
            if hasattr(self, "process_progress"):
                self.process_progress.configure(style="Download.Horizontal.TProgressbar")
            self.file_tree.configure(style="VoiceClone.Treeview")
        except Exception:
            pass
        def visit(widget):
            try:
                cls = widget.winfo_class()
                if cls == "Frame":
                    widget.configure(bg=surface if widget is not self.root else root_bg)
                elif cls == "Label":
                    widget.configure(bg=surface, fg=text)
                elif cls == "Entry":
                    widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg)
                elif cls == "Text":
                    widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg)
            except Exception:
                pass
            try:
                for child in widget.winfo_children():
                    visit(child)
            except Exception:
                pass
        visit(self.root)
        apply_button_style_to_tree(self.root, self.theme)
        self.refresh_folder_buttons()
        try:
            self.audio_player.apply_theme(self.theme)
        except Exception:
            pass
