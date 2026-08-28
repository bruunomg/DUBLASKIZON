"""Aba independente para converter somente o formato dos arquivos de áudio."""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

try:
    from .audio_player import AudioPlayerManager, reveal_in_file_manager
    from .ui_theme import apply_button_style, apply_button_style_to_tree, configure_ttk_button_styles, surface_color
    from .duration_converter_tab import (
        DEFAULT_FORMAT,
        FFMPEG_WINDOWS_URL,
        FORMAT_CHOICES,
        HoverTooltip,
        TOOLS_DIR_NAME,
        TOOLS_HELP_TEXT,
        executable_path,
        update_download_progress,
    )
except ImportError:
    from audio_player import AudioPlayerManager, reveal_in_file_manager
    from ui_theme import apply_button_style, apply_button_style_to_tree, configure_ttk_button_styles, surface_color
    from duration_converter_tab import (
        DEFAULT_FORMAT,
        FFMPEG_WINDOWS_URL,
        FORMAT_CHOICES,
        HoverTooltip,
        TOOLS_DIR_NAME,
        TOOLS_HELP_TEXT,
        executable_path,
        update_download_progress,
    )

try:
    from tkinter import END, Menu, StringVar, Text, filedialog, messagebox, ttk
    import tkinter as tk
    from tkinter import Button, Entry, Frame, Label, Listbox, Scrollbar
    TK_AVAILABLE = True
    TK_IMPORT_ERROR = ""
except ModuleNotFoundError as exc:
    TK_AVAILABLE = False
    TK_IMPORT_ERROR = str(exc)
    END = "end"

try:
    from . import i18n
except ImportError:
    import i18n

if TK_AVAILABLE:
    messagebox = i18n.localized_messagebox(messagebox)


AUDIO_EXTENSIONS = {
    ".wav", ".wave", ".mp3", ".ogg", ".flac", ".aiff", ".aif",
    ".m4a", ".aac", ".wma", ".opus",
}
FORMAT_OUTPUT_FOLDER_NAME = "AUDIO FORMATOS CONVERTIDOS"
FORMAT_ARCHIVE_DIR_NAMES = {
    "_backup_omnivoice", "mp3", "ogg", "flac", "aiff", "aif", "m4a", "aac", "wma", "opus", "wave", "wav",
}


def is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS


def _is_internal_project_audio(path: Path, scan_root: Path | None = None) -> bool:
    path = Path(path).expanduser().resolve()
    try:
        relative = path.relative_to(Path(scan_root).expanduser().resolve()) if scan_root is not None else path
    except ValueError:
        relative = path
    parts = relative.parts
    parent_name = relative.parent.name.casefold()
    return (
        "_backup_omnivoice" in {part.casefold() for part in parts[:-1]}
        or parent_name in FORMAT_ARCHIVE_DIR_NAMES
    )


def list_audio_files(folder: Path, exclude_internal: bool = True) -> list[Path]:
    if not folder.is_dir():
        return []
    candidates = (path for path in folder.rglob("*") if is_audio_file(path))
    if exclude_internal:
        candidates = (path for path in candidates if not _is_internal_project_audio(path, folder))
    return sorted(candidates, key=lambda path: (path.name.casefold(), str(path).casefold()))


def project_audio_files(project_root: Path) -> tuple[list[Path], list[Path]]:
    """Retorna originais e dublados recursivamente, sem criar diretórios."""
    root = Path(project_root).expanduser().resolve()
    return list_audio_files(root / "WAV ORIGINAIS"), list_audio_files(root / "dublado")


def parse_drop_paths(raw: str, tk_root=None) -> list[Path]:
    if not raw:
        return []
    try:
        values = list(tk_root.tk.splitlist(raw)) if tk_root is not None else [raw]
    except Exception:
        values = [raw]
    paths: list[Path] = []
    for value in values:
        cleaned = str(value).strip().strip('"')
        if cleaned:
            paths.append(Path(cleaned).expanduser())
    return paths


def hidden_process_kwargs() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
    }


def portable_tool_dir() -> Path:
    module_dir = Path(__file__).resolve().parent
    app_dir = Path(os.environ.get("DUBLASKIZON_APP_DIR", module_dir)).expanduser().resolve()
    target = app_dir / TOOLS_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


class FormatConverterApp:
    TITLE = "CONVERTER FORMATOS DE ÁUDIO"

    def __init__(self, root, embedded=True, project_root: Path | None = None, project_actions=None):
        if not TK_AVAILABLE:
            raise RuntimeError(f"Tkinter indisponível: {TK_IMPORT_ERROR}")
        self.root = root
        self.embedded = embedded
        self.project_root = Path(project_root or Path.cwd()).expanduser().resolve()
        self.project_actions = project_actions or {}
        self.central_log_callback = self.project_actions.get("central_log")
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.files: list[Path] = []
        self.file_source_by_path: dict[str, str] = {}
        self.running = False
        self.dependencies_running = False
        self.tool_alert_after_id = None
        self.tool_alert_until = 0.0
        self.tool_alert_on = False
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.dependency_thread: threading.Thread | None = None
        self.process = None
        self.theme = {
            "root": "#F5F6FA", "surface": "#FFFFFF", "text": "#1F2937",
            "muted": "#64748B", "input": "#FFFFFF", "input_text": "#1F2937",
            "select": "#DBEAFE", "border": "#CBD5E1",
        }
        self.format_var = StringVar(value=DEFAULT_FORMAT)
        self.input_dir_var = StringVar(value="Nenhum arquivo carregado")
        self.output_dir_var = StringVar(value=str(self.project_root / FORMAT_OUTPUT_FOLDER_NAME))
        self.status_var = StringVar(value="Adicione os áudios e escolha o formato de saída.")
        self.count_var = StringVar(value="Áudios: 0")
        self.progress_var = StringVar(value="Conversão de formato: aguardando")
        self.download_status_var = StringVar(value="Ferramentas: não verificadas")
        self.panel_title_var = StringVar(value="ÁUDIOS PARA CONVERTER (0)")
        self.audio_player = AudioPlayerManager(self.root, self.project_root, status_callback=lambda text: (self.status_var.set(text), self._log_central(text, "info")))
        self.build_ui()
        self.refresh_for_project()
        self.root.after(100, self.poll_messages)

    def apply_theme(self, theme):
        self.theme = {**self.theme, **theme}
        surface = self.theme.get("surface", "#FFFFFF")
        text = self.theme.get("text", "#1F2937")
        input_bg = self.theme.get("input", surface)
        input_fg = self.theme.get("input_text", text)
        select = self.theme.get("select", "#DBEAFE")
        try:
            style = ttk.Style(self.root)
            style.configure("TFrame", background=surface)
            style.configure("TLabel", background=surface, foreground=text)
            configure_ttk_button_styles(style, self.theme)
            style.configure("TCombobox", fieldbackground=input_bg, background=input_bg, foreground=input_fg)
            style.map("TCombobox", fieldbackground=[("readonly", input_bg)], foreground=[("readonly", input_fg)], selectbackground=[("readonly", select)], selectforeground=[("readonly", input_fg)])
            self.root.option_add("*TCombobox*Listbox.background", input_bg)
            self.root.option_add("*TCombobox*Listbox.foreground", input_fg)
            self.root.option_add("*TCombobox*Listbox.selectBackground", select)
            track_color = surface_color(self.theme, "progress_track", self.theme.get("border", "#CBD5E1"))
            conversion_color = surface_color(self.theme, "progress_conversion", "#DC2626")
            download_color = surface_color(self.theme, "progress_download", "#F97316")
            style.configure("Format.Horizontal.TProgressbar", troughcolor=track_color, background=conversion_color, lightcolor=conversion_color, darkcolor=conversion_color)
            style.configure("FormatDownload.Horizontal.TProgressbar", troughcolor=track_color, background=download_color, lightcolor=download_color, darkcolor=download_color)
            self.progress_bar.configure(style="Format.Horizontal.TProgressbar")
            self.download_progress.configure(style="FormatDownload.Horizontal.TProgressbar")
        except Exception:
            pass

        def visit(widget):
            try:
                cls = widget.winfo_class()
                if cls == "Frame":
                    widget.configure(bg=surface)
                elif cls == "Label":
                    widget.configure(bg=surface, fg=text)
                elif cls == "Entry":
                    widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg, readonlybackground=input_bg)
                elif cls == "Listbox":
                    widget.configure(bg=input_bg, fg=input_fg, selectbackground=select, selectforeground=input_fg)
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
        if hasattr(self, "audio_player"):
            self.audio_player.apply_theme(self.theme)

    def build_ui(self):
        header = Frame(self.root, bg="#F5F6FA")
        header.pack(fill="x", padx=16, pady=(8, 3))
        Label(header, text=self.TITLE, bg="#F5F6FA", fg="#1F2937", font=("Segoe UI", 14, "bold")).pack(side="left")
        Label(header, text="  Apenas troca o formato; não altera a duração", bg="#F5F6FA", fg="#64748B", font=("Segoe UI", 9)).pack(side="left")
        Label(self.root, textvariable=self.status_var, bg="#F5F6FA", fg="#64748B", anchor="w").pack(fill="x", padx=16, pady=(0, 6))

        panel = Frame(self.root, bg="#FFFFFF", bd=1, relief="solid")
        panel.pack(fill="both", expand=True, padx=16, pady=(0, 7))
        Label(panel, textvariable=self.panel_title_var, bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        Entry(panel, textvariable=self.input_dir_var, state="readonly", readonlybackground="#FFFFFF", fg="#64748B", relief="flat", font=("Segoe UI", 8)).pack(fill="x", padx=10, pady=(0, 5))
        list_frame = Frame(panel, bg="#FFFFFF")
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.listbox = Listbox(list_frame, selectmode="extended", activestyle="none", height=12, font=("Segoe UI", 10), bg="#FFFFFF", fg="#1F2937", selectbackground="#DBEAFE", selectforeground="#1F2937")
        scrollbar = Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.listbox.bind("<Double-Button-1>", self.play_selected)
        self.listbox.bind("<Button-3>", self.show_context_menu, add="+")
        self.enable_drag_drop()
        file_buttons = Frame(panel, bg="#FFFFFF")
        file_buttons.pack(fill="x", padx=10, pady=(0, 5))
        Button(file_buttons, text="ABRIR PASTA", command=self.choose_input_folder, bg="#2563EB", activebackground="#1D4ED8", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2").pack(side="left", padx=(0, 4))
        Button(file_buttons, text="ADICIONAR ÁUDIOS", command=self.add_files, bg="#64748B", activebackground="#475569", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2").pack(side="left", padx=4)
        Button(file_buttons, text="LIMPAR", command=self.clear_files, bg="#CBD5E1", activebackground="#94A3B8", fg="#1F2937", relief="flat", padx=9, pady=4, cursor="hand2").pack(side="right")
        audio_buttons = Frame(panel, bg="#FFFFFF")
        audio_buttons.pack(fill="x", padx=10, pady=(0, 5))
        Button(audio_buttons, text="▶ OUVIR", command=self.play_selected, bg="#0F766E", activebackground="#115E59", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=3, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 3))
        Button(audio_buttons, text="▶ OUVIR TODOS", command=self.play_all, bg="#7C3AED", activebackground="#6D28D9", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=3, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(3, 0))
        Label(panel, text="Arraste arquivos ou uma pasta para a lista. A conversão usa os caminhos reais carregados.", bg="#FFFFFF", fg="#94A3B8", font=("Segoe UI", 8)).pack(fill="x", padx=10, pady=(0, 8))

        options = Frame(self.root, bg="#FFFFFF", bd=1, relief="solid")
        options.pack(fill="x", padx=16, pady=(0, 7))
        Label(options, text="Formato de saída", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(8, 2))
        self.format_combo = ttk.Combobox(options, textvariable=self.format_var, values=list(FORMAT_CHOICES), state="readonly", width=52)
        self.format_combo.grid(row=1, column=0, sticky="ew", padx=(10, 6), pady=(0, 8))
        self.format_combo.bind("<MouseWheel>", lambda _event: "break")
        Label(options, text="Pasta de saída", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=6, pady=(8, 2))
        self.output_entry = ttk.Entry(options, textvariable=self.output_dir_var, width=45)
        self.output_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 8))
        output_buttons = Frame(options, bg="#FFFFFF")
        output_buttons.grid(row=1, column=2, padx=(0, 10), pady=(0, 8))
        Button(output_buttons, text="ESCOLHER", command=self.choose_output_folder, bg="#64748B", activebackground="#475569", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2").pack(side="left", padx=(0, 3))
        Button(output_buttons, text="ABRIR PASTA", command=self.open_output_folder, bg="#0F766E", activebackground="#115E59", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2").pack(side="left")
        options.grid_columnconfigure(0, weight=1)
        options.grid_columnconfigure(1, weight=1)

        actions = Frame(self.root, bg="#F5F6FA")
        actions.pack(fill="x", padx=16, pady=(0, 6))
        self.load_review_button = Button(actions, text="CARREGAR DA ABA REVISÃO", command=self.load_from_review, bg="#D97706", activebackground="#B45309", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2")
        self.load_review_button.pack(side="left", padx=(0, 5))
        self.load_batch_button = Button(actions, text="CARREGAR DA CLONAGEM + DUBLAGEM", command=self.load_from_batch, bg="#D97706", activebackground="#B45309", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2")
        self.load_batch_button.pack(side="left", padx=5)
        self.dependencies_button = Button(actions, text="BAIXAR / PREPARAR FERRAMENTAS", command=self.start_dependency_setup, bg="#0F766E", activebackground="#115E59", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2")
        self.dependencies_button.pack(side="left", padx=(0, 5))
        self.tools_help_button = Button(actions, text="?", command=self.show_tools_help, bg="#64748B", activebackground="#475569", fg="white", relief="flat", font=("Segoe UI", 9, "bold"), width=2, padx=0, pady=5, cursor="hand2")
        self.tools_help_button.pack(side="left")
        HoverTooltip(self.tools_help_button, TOOLS_HELP_TEXT)
        self.convert_button = Button(actions, text="CONVERTER FORMATOS", command=self.start_conversion, bg="#DC2626", activebackground="#B91C1C", fg="white", relief="flat", font=("Segoe UI", 10, "bold"), padx=18, pady=7, cursor="hand2")
        self.convert_button.pack(side="right")
        Label(self.root, textvariable=self.count_var, bg="#F5F6FA", fg="#475569", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=16)
        Label(self.root, textvariable=self.progress_var, bg="#F5F6FA", fg="#64748B", anchor="w").pack(fill="x", padx=16, pady=(2, 2))
        self.progress_bar = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100, value=0, style="Format.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 3))
        Label(self.root, textvariable=self.download_status_var, bg="#F5F6FA", fg="#64748B", font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=16, pady=(0, 2))
        self.download_progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100, value=0, style="FormatDownload.Horizontal.TProgressbar")
        self.download_progress.pack(fill="x", padx=16, pady=(0, 7))
        self.log_box = Text(self.root, height=6, wrap="word", state="disabled", font=("Consolas", 9), background="#111827", foreground="#E5E7EB")
        self.log_box.pack(fill="x", padx=16, pady=(0, 7))

        self.folder_bar = Frame(self.root, bg="#F5F6FA")
        self.folder_bar.pack(fill="x", padx=16, pady=(0, 10))
        self.refresh_folder_buttons()

    def folder_button_definitions(self):
        return (
            ("WAV ORIGINAL", self.project_root / "WAV ORIGINAIS", "primary"),
            ("WAV DUBLADO", self.project_root / "dublado", "accent"),
            ("REVISÕES", self.project_root / "revisoes", "success"),
            ("TXT PT", self.project_root / "TXT TEXTO PORTUGUES", "warning"),
            ("TXT ORIGINAL", self.project_root / "TXT TEXTO ORIGINAL", "secondary"),
            ("TXT TRANSCRITO", self.project_root / "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO", "teal"),
            ("OUTRAS TRADUÇÕES", self.project_root / "OUTRAS TRADUÇÕES", "accent"),
            (FORMAT_OUTPUT_FOLDER_NAME, self.project_root / FORMAT_OUTPUT_FOLDER_NAME, "highlight"),
        )

    def refresh_folder_buttons(self):
        if not hasattr(self, "folder_bar"):
            return
        for child in self.folder_bar.winfo_children():
            child.destroy()
        for label, path, role in self.folder_button_definitions():
            button = Button(self.folder_bar, text=label, command=lambda target=path, name=label: self.open_folder(target, name), relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=4, cursor="hand2")
            apply_button_style(button, getattr(self, "theme", {}), role)
            button.pack(side="left", padx=3)

    def open_folder(self, path: Path, label: str):
        folder = Path(path).expanduser().resolve()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._log_central(f"Pasta aberta: {folder}", "info")
        except Exception as exc:
            self._log_central(f"Falha ao abrir pasta {folder}: {exc}", "error")
            messagebox.showerror("Pasta", f"Não foi possível abrir {label}:\n{folder}\n\n{exc}", parent=self.root)

    def enable_drag_drop(self):
        try:
            self.listbox.drop_target_register("DND_Files")
            self.listbox.dnd_bind("<<Drop>>", lambda event: self.handle_drop(event.data))
        except Exception:
            pass

    def handle_drop(self, raw: str):
        found: list[Path] = []
        for path in parse_drop_paths(raw, self.root):
            if path.is_dir():
                found.extend(list_audio_files(path))
            elif is_audio_file(path):
                found.append(path)
        self.set_files(self.files + found, "Arquivos arrastados")

    def choose_input_folder(self):
        selected = filedialog.askdirectory(parent=self.root, title="Escolher pasta de áudios para converter")
        if selected:
            folder = Path(selected)
            self.set_files(list_audio_files(folder), str(folder))

    def add_files(self):
        selected = filedialog.askopenfilenames(parent=self.root, title="Selecionar áudios para converter", filetypes=[("Áudios", "*.wav *.wave *.mp3 *.ogg *.flac *.aiff *.aif *.m4a *.aac *.wma *.opus"), ("Todos os arquivos", "*.*")])
        if selected:
            self.set_files(self.files + [Path(path) for path in selected], "Arquivos selecionados")

    def choose_output_folder(self):
        selected = filedialog.askdirectory(parent=self.root, title="Pasta dos áudios convertidos")
        if selected:
            self.output_dir_var.set(selected)

    def open_output_folder(self):
        folder = Path(self.output_dir_var.get().strip() or self.project_root / FORMAT_OUTPUT_FOLDER_NAME).expanduser().resolve()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            messagebox.showerror("Pasta de saída", f"Não foi possível abrir a pasta:\n{folder}\n\n{exc}", parent=self.root)

    def clear_files(self):
        self.set_files([], "Nenhum arquivo carregado")

    def _display_path(self, path: Path) -> str:
        path = Path(path).expanduser().resolve()
        for folder_name in ("WAV ORIGINAIS", "dublado"):
            try:
                return path.relative_to(self.project_root / folder_name).as_posix()
            except ValueError:
                continue
        return path.name

    def set_files(self, files: list[Path], label: str, source_labels: dict[str, str] | None = None):
        unique: list[Path] = []
        seen: set[str] = set()
        supplied_sources = source_labels or {}
        normalized_sources = {os.path.normcase(str(Path(key).expanduser().resolve())): value for key, value in supplied_sources.items()}
        next_sources: dict[str, str] = {}
        for raw in files:
            path = Path(raw).expanduser().resolve()
            key = os.path.normcase(str(path))
            if is_audio_file(path) and key not in seen:
                seen.add(key)
                unique.append(path)
                next_sources[key] = normalized_sources.get(key, "")
        self.files = sorted(unique, key=lambda path: (path.name.casefold(), str(path).casefold()))
        self.file_source_by_path = next_sources
        self.input_dir_var.set(label)
        self.panel_title_var.set(f"ÁUDIOS PARA CONVERTER ({len(self.files)})")
        self.count_var.set(f"Áudios: {len(self.files)}")
        self.listbox.delete(0, END)
        name_counts: dict[str, int] = {}
        for path in self.files:
            name_counts[path.name.casefold()] = name_counts.get(path.name.casefold(), 0) + 1
        for path in self.files:
            source = self.file_source_by_path.get(os.path.normcase(str(path)), "")
            marker = f" [{i18n.tr(source)}]" if source else ""
            shown_name = self._display_path(path) if name_counts.get(path.name.casefold(), 0) > 1 else path.name
            self.listbox.insert(END, f"{shown_name}{marker}")

    def _format_audio_kind(self, path: Path) -> str:
        key = os.path.normcase(str(Path(path).expanduser().resolve()))
        source = str(self.file_source_by_path.get(key, "")).casefold()
        if source in {"original", "dublado"}:
            return source
        resolved = Path(path).expanduser().resolve()
        for kind, base_name in (("original", "WAV ORIGINAIS"), ("dublado", "dublado")):
            try:
                resolved.relative_to((self.project_root / base_name).resolve())
                return kind
            except ValueError:
                continue
        return ""

    def _format_audio_key(self, path: Path, kind: str) -> str:
        base_name = "WAV ORIGINAIS" if kind == "original" else "dublado"
        try:
            relative = Path(path).expanduser().resolve().relative_to((self.project_root / base_name).resolve()).with_suffix("")
            return relative.as_posix().casefold()
        except ValueError:
            return Path(path).stem.casefold()

    def _context_audio_paths(self, index: int):
        if index < 0 or index >= len(self.files):
            return None, None
        selected = self.files[index]
        selected_kind = self._format_audio_kind(selected)
        original = selected if selected_kind == "original" else None
        dubbed = selected if selected_kind == "dublado" else None
        selected_key = self._format_audio_key(selected, selected_kind) if selected_kind else ""
        if selected_key:
            for candidate in self.files:
                candidate_kind = self._format_audio_kind(candidate)
                if not candidate_kind or candidate_kind == selected_kind:
                    continue
                if self._format_audio_key(candidate, candidate_kind) == selected_key:
                    if candidate_kind == "original":
                        original = candidate
                    else:
                        dubbed = candidate
                    break
        return original, dubbed

    def _copy_context_value(self, value: str, success_message: str):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.root.update()
            self.status_var.set(success_message)
        except tk.TclError as exc:
            self.status_var.set(f"Não foi possível copiar: {exc}")

    def _context_action(self, index: int, action: str):
        original, dubbed = self._context_audio_paths(index)
        if action in {"open_original", "copy_original"}:
            path = original
            label = "original"
        elif action in {"open_dubbed", "copy_dubbed"}:
            path = dubbed
            label = "dublado"
        else:
            path = dubbed or original or (self.files[index] if 0 <= index < len(self.files) else None)
            label = "áudio"
        if path is None or not path.is_file():
            self.status_var.set(f"Áudio {label} não encontrado para o item selecionado.")
            return
        if action.startswith("open_"):
            if reveal_in_file_manager(path):
                self.status_var.set(f"Pasta do áudio {label} aberta: {path.parent}")
            else:
                self.status_var.set(f"Não foi possível abrir a pasta do áudio {label}: {path.parent}")
        elif action == "copy_name":
            self._copy_context_value(path.name, f"Nome copiado: {path.name}")
        else:
            self._copy_context_value(str(path.parent), f"Local da pasta copiado: {path.parent}")

    def show_context_menu(self, event):
        index = int(self.listbox.nearest(event.y))
        box = self.listbox.bbox(index) if index < self.listbox.size() else None
        if box is None or not (box[1] <= event.y <= box[1] + box[3]):
            return "break"
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(index)
        self.listbox.activate(index)
        menu = Menu(self.listbox, tearoff=0)
        menu.add_command(label=i18n.tr("ABRIR LOCAL DO ÁUDIO DUBLADO"), command=lambda: self._context_action(index, "open_dubbed"))
        menu.add_command(label=i18n.tr("ABRIR LOCAL DO ÁUDIO ORIGINAL"), command=lambda: self._context_action(index, "open_original"))
        menu.add_separator()
        menu.add_command(label=i18n.tr("COPIAR NOME DO ÁUDIO"), command=lambda: self._context_action(index, "copy_name"))
        menu.add_command(label=i18n.tr("COPIAR LOCAL DO ÁUDIO DUBLADO"), command=lambda: self._context_action(index, "copy_dubbed"))
        menu.add_command(label=i18n.tr("COPIAR LOCAL DO ÁUDIO ORIGINAL"), command=lambda: self._context_action(index, "copy_original"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def play_selected(self, _event=None):
        selection = self.listbox.curselection()
        if not selection or int(selection[0]) >= len(self.files):
            return
        index = int(selection[0])
        path = self.files[index]
        self.audio_player.play_one(path, f"OUVIR — {path.name}", playlist=self.files, index=index)

    def play_all(self):
        self.audio_player.play_all(self.files, "OUVIR TODOS — FORMATOS")

    def load_project_defaults(self, source_label: str):
        """Carrega os áudios atuais do projeto em uma única lista, sem criar pastas."""
        self.project_root = Path(getattr(self.root, "project_root", self.project_root)).expanduser().resolve()
        self.audio_player.set_project_root(self.project_root)
        original_files, dubbed_files = project_audio_files(self.project_root)
        files = original_files + dubbed_files
        source_labels = {str(path): "ORIGINAL" for path in original_files}
        source_labels.update({str(path): "DUBLADO" for path in dubbed_files})
        label = f"Carregado da aba {source_label}: {len(original_files)} originais + {len(dubbed_files)} dublados"
        self.set_files(files, label, source_labels=source_labels)
        self.status_var.set(f"Carregado da aba {source_label}: confira os arquivos antes de converter.")
        self.append_log(f"Carregamento da aba {source_label}: {len(files)} arquivo(s) carregado(s).")

    def load_from_review(self):
        self.load_project_defaults("REVISÃO")

    def load_from_batch(self):
        self.load_project_defaults("CLONAGEM + DUBLAGEM")

    def refresh_for_project(self):
        self.project_root = Path(getattr(self.root, "project_root", self.project_root)).expanduser().resolve()
        self.output_dir_var.set(str(self.project_root / FORMAT_OUTPUT_FOLDER_NAME))
        self.audio_player.set_project_root(self.project_root)
        self.refresh_folder_buttons()
        self.start_tool_alert()

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

    def _log_central(self, text, tag="normal") -> None:
        callback = getattr(self, "central_log_callback", None)
        if callable(callback):
            try:
                callback("CONVERTER FORMATOS", str(text), tag)
            except Exception:
                pass

    def append_log(self, text: str):
        self._log_central(text)
        self.queue.put(("log", text))

    def poll_messages(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", i18n.tr(str(payload)) + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "progress":
                    index, total = payload
                    percent = min(100.0, index * 100.0 / max(1, total))
                    self.progress_bar.configure(value=percent)
                    self.progress_var.set(f"Conversão de formato: {index}/{total} ({percent:.1f}%)")
                elif kind == "done":
                    self.running = False
                    self.convert_button.configure(state="normal")
                    self.status_var.set(str(payload))
                    self.progress_var.set("Conversão de formato: concluída")
                    self.progress_bar.configure(value=100)
                elif kind == "download_progress":
                    description, downloaded, total = payload
                    if total:
                        percent = update_download_progress(self.download_progress, description, downloaded, total)
                        self.download_status_var.set(f"Baixando {description}: {percent:.1f}% ({downloaded / 1048576:.1f} / {total / 1048576:.1f} MB)")
                    else:
                        percent = update_download_progress(self.download_progress, description, downloaded, total)
                        self.download_status_var.set(f"Baixando {description}: {percent:.1f}% estimado; tamanho final ainda não informado")
                elif kind == "dependencies_done":
                    self.dependencies_running = False
                    self.dependencies_button.configure(state="normal")
                    self.stop_tool_alert()
                    self.download_progress.stop()
                    self.download_progress.configure(mode="determinate", value=max(float(self.download_progress.cget("value")), 100.0) if not self.missing_tools() else 0)
                    self.download_status_var.set(str(payload))
                    self.status_var.set(str(payload))
        except queue.Empty:
            pass
        try:
            self.root.after(100, self.poll_messages)
        except Exception:
            pass

    def run_ffmpeg(self, source: Path, target: Path, format_name: str):
        ffmpeg = executable_path("ffmpeg", self.project_root)
        if not ffmpeg:
            raise RuntimeError("FFmpeg não foi encontrado. Clique em BAIXAR / PREPARAR FFmpeg + FFplay.")
        spec = FORMAT_CHOICES[format_name]
        command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vn", "-c:a", spec["codec"]]
        if spec.get("rate"):
            command.extend(["-ar", spec["rate"]])
        if spec.get("channels"):
            command.extend(["-ac", spec["channels"]])
        if spec.get("bitrate"):
            command.extend(["-b:a", spec["bitrate"]])
        if spec.get("quality"):
            command.extend(["-q:a", spec["quality"]])
        command.append(str(target))
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", **hidden_process_kwargs())
        self.process = process
        stdout, stderr = process.communicate()
        if self.process is process:
            self.process = None
        if self.cancel_event.is_set():
            raise RuntimeError("cancelamento solicitado")
        if process.returncode != 0:
            raise RuntimeError(stderr.strip()[-1200:] or f"FFmpeg retornou código {process.returncode}.")

    def _output_relative_path(self, source: Path) -> Path:
        """Preserva a subpasta de arquivos importados das pastas do projeto."""
        source = Path(source).expanduser().resolve()
        project_root = Path(getattr(self, "project_root", Path.cwd())).expanduser().resolve()
        for folder_name in ("WAV ORIGINAIS", "dublado"):
            folder = project_root / folder_name
            try:
                return source.relative_to(folder)
            except ValueError:
                continue
        return Path(source.name)

    def output_target(self, source: Path, output_root: Path, format_name: str) -> Path:
        extension = FORMAT_CHOICES[format_name]["extension"]
        relative = self._output_relative_path(source)
        target = output_root / relative.with_suffix(extension)
        try:
            same_as_source = target.resolve() == source.resolve()
        except OSError:
            same_as_source = False
        if same_as_source or target.exists():
            target = target.with_name(f"{target.stem}_convertido{extension}")
        counter = 2
        while target.exists() and target.resolve() != source.resolve():
            target = target.with_name(f"{target.stem.split('_convertido')[0]}_convertido_{counter}{extension}")
            counter += 1
        return target

    def start_conversion(self):
        missing = self.missing_tools()
        if missing:
            self.start_tool_alert()
            messagebox.showwarning(
                "Ferramentas necessárias",
                "A conversão não foi iniciada. Faltam: " + ", ".join(missing) + ".\n\nClique em BAIXAR / PREPARAR FERRAMENTAS e aguarde a conclusão.",
                parent=self.root,
            )
            return
        self.stop_tool_alert()
        if self.running or self.dependencies_running:
            return
        if not self.files:
            messagebox.showwarning("Conversão de formatos", "Nenhum áudio foi carregado.", parent=self.root)
            return
        format_name = i18n.source_text(self.format_var.get())
        if format_name not in FORMAT_CHOICES:
            messagebox.showwarning("Formato", "Escolha um formato de saída válido.", parent=self.root)
            return
        output_root = Path(self.output_dir_var.get().strip() or self.project_root / FORMAT_OUTPUT_FOLDER_NAME).expanduser().resolve()
        self.running = True
        self.cancel_event.clear()
        self.convert_button.configure(state="disabled")
        self.progress_bar.configure(value=0)
        self.status_var.set(f"Convertendo {len(self.files)} áudio(s) para {format_name}...")
        self._log_central(f"Iniciada conversão de {len(self.files)} áudio(s) para {format_name}; saída: {output_root}", "info")
        self.worker = threading.Thread(target=self.conversion_worker, args=(list(self.files), format_name, output_root), daemon=True)
        self.worker.start()

    def conversion_worker(self, files: list[Path], format_name: str, output_root: Path):
        converted = 0
        failures = 0
        try:
            output_root.mkdir(parents=True, exist_ok=True)
            for index, source in enumerate(files, start=1):
                if self.cancel_event.is_set():
                    summary = f"Conversão cancelada: {converted} concluído(s), {failures} falha(s)."
                    self._log_central(summary, "info")
                    self.queue.put(("done", summary))
                    return
                target = self.output_target(source, output_root, format_name)
                target.parent.mkdir(parents=True, exist_ok=True)
                self.queue.put(("status", f"Convertendo {index}/{len(files)}: {source.name}"))
                self.append_log(f"[{index}/{len(files)}] {source} -> {target}")
                try:
                    self.run_ffmpeg(source, target, format_name)
                    converted += 1
                    self.append_log(f"OK: {target.name}")
                except Exception as exc:
                    failures += 1
                    self.append_log(f"FALHA: {source.name}: {exc}")
                    if self.cancel_event.is_set():
                        summary = f"Conversão cancelada: {converted} concluído(s), {failures} falha(s)."
                        self._log_central(summary, "info")
                        self.queue.put(("done", summary))
                        return
                self.queue.put(("progress", (index, len(files))))
            summary = f"Conversão finalizada: {converted} convertido(s), {failures} falha(s). Saída: {output_root}"
            self._log_central(summary, "ok" if failures == 0 else "info")
            self.queue.put(("done", summary))
        except Exception as exc:
            summary = f"Conversão interrompida: {exc}"
            self._log_central(summary, "error")
            self.queue.put(("done", summary))

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

    def show_tools_help(self):
        messagebox.showinfo(i18n.tr("Ferramentas de áudio"), i18n.tr(TOOLS_HELP_TEXT), parent=self.root)

    def start_dependency_setup(self):
        self.stop_tool_alert()
        if self.running or self.dependencies_running:
            return
        self.dependencies_running = True
        self.dependencies_button.configure(state="disabled")
        self.download_progress.stop()
        self.download_progress.configure(mode="determinate", value=0)
        self.status_var.set("Preparando FFmpeg e FFplay...")
        self.dependency_thread = threading.Thread(target=self.dependency_worker, daemon=True)
        self.dependency_thread.start()

    def dependency_worker(self):
        try:
            if os.name != "nt":
                self.queue.put(("dependencies_done", "No Windows, use este botão para preparar FFmpeg/FFplay; neste sistema o PATH deve fornecê-los."))
                return
            if executable_path("ffmpeg", self.project_root) and executable_path("ffplay", self.project_root):
                self.queue.put(("dependencies_done", "FFmpeg e FFplay já estão disponíveis; download ignorado."))
                return
            tools_dir = portable_tool_dir()
            temp_dir = Path(tempfile.mkdtemp(prefix="dublagenskizon_formats_"))
            archive_path = temp_dir / "ffmpeg.zip"
            try:
                self.append_log("Baixando FFmpeg com FFplay...")
                request = urllib.request.Request(FFMPEG_WINDOWS_URL, headers={"User-Agent": "Dublaskizon/1.0"})
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
                        self.queue.put(("download_progress", ("FFmpeg", downloaded, total)))
                extract_dir = temp_dir / "extraido"
                self.safe_extract_zip(archive_path, extract_dir)
                copied: set[str] = set()
                for candidate in extract_dir.rglob("*"):
                    if not candidate.is_file():
                        continue
                    if candidate.name.casefold() in {"ffmpeg.exe", "ffprobe.exe", "ffplay.exe"} or candidate.suffix.casefold() == ".dll":
                        shutil.copy2(candidate, tools_dir / candidate.name)
                        copied.add(candidate.name.casefold())
                if not {"ffmpeg.exe", "ffprobe.exe", "ffplay.exe"}.issubset(copied):
                    raise RuntimeError("O pacote do FFmpeg não continha ffmpeg.exe, ffprobe.exe e ffplay.exe.")
                self.queue.put(("dependencies_done", "FFmpeg, FFprobe e FFplay foram preparados em ferramentas_audio."))
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as exc:
            self.append_log(f"ERRO ao preparar FFmpeg/FFplay: {exc}")
            self.queue.put(("dependencies_done", "Não foi possível preparar FFmpeg/FFplay; confira o painel de processos."))

    def cancel_run(self):
        if not self.running:
            return
        self.cancel_event.set()
        process = self.process
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self.status_var.set("Cancelamento solicitado; finalizando o arquivo atual...")

    def close(self):
        self.cancel_run()
        try:
            self.audio_player.close_window()
        except Exception:
            pass


if __name__ == "__main__":
    print("Use Dublaskizon.py para abrir a aba de conversão de formatos.")
