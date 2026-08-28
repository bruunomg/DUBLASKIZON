#!/usr/bin/env python3
"""Ponte simples de revisão: arquivos + botões + Audacity.

Estrutura esperada:

PROJETO_DUBLAGEM/
|-- CLONAR-DUBLAR.bat
|-- CLONAR-DUBLAR.py
|-- WAV ORIGINAIS/
|-- TXT TEXTO PORTUGUES/
|-- dublado/
`-- revisoes/
    |-- REVISAR-DUBLAGEM.bat
    `-- REVISAR-DUBLAGEM.py

A primeira versão usa o OmniVoice diretamente para regenerar a cena. O
Audacity entra como ferramenta de revisão/escuta; não é necessário instalar
um plugin ou configurar API dentro dele.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
try:
    from .audio_player import AudioPlayerManager, reveal_in_file_manager
    from .ui_theme import apply_button_style, apply_button_style_to_tree, surface_color
except ImportError:
    from audio_player import AudioPlayerManager, reveal_in_file_manager
    from ui_theme import apply_button_style, apply_button_style_to_tree, surface_color

try:

    from .batch_tab import find_omnivoice_command, hidden_process_kwargs, relative_scene_key, is_format_archive_dir, is_internal_omnivoice_backup, R_PRONUNCIATION_CHOICES, apply_r_pronunciation
except ImportError:
    from batch_tab import find_omnivoice_command, hidden_process_kwargs, relative_scene_key, is_format_archive_dir, is_internal_omnivoice_backup, R_PRONUNCIATION_CHOICES, apply_r_pronunciation

try:
    from tkinter import END, Button, DoubleVar, Entry, Frame, Label, Listbox, Menu, StringVar, Text, Tk, Toplevel, filedialog, messagebox, simpledialog, ttk
    TK_AVAILABLE = True
    TK_IMPORT_ERROR = ""
except ModuleNotFoundError as exc:
    TK_AVAILABLE = False
    TK_IMPORT_ERROR = str(exc)
    END = "end"
    DoubleVar = None  # type: ignore
    filedialog = None  # type: ignore
    Toplevel = None  # type: ignore

try:
    from . import i18n
except ImportError:
    import i18n

if TK_AVAILABLE:
    messagebox = i18n.localized_messagebox(messagebox)
    simpledialog = i18n.localized_simpledialog(simpledialog)

# O EXE define DUBLASKIZON_PROJECT_ROOT; standalone continua usando a pasta acima de revisoes.
_PROJECT_ROOT = os.environ.get("DUBLASKIZON_PROJECT_ROOT")
ROOT = Path(_PROJECT_ROOT).resolve() if _PROJECT_ROOT else Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "WAV ORIGINAIS"
TEXT_DIR = ROOT / "TXT TEXTO PORTUGUES"
OUTPUT_DIR = ROOT / "dublado"
REVISIONS_DIR = ROOT / "revisoes"
ORIGINAL_TEXT_DIR = ROOT / "TXT TEXTO ORIGINAL"
TRANSCRIBED_TRANSLATED_TEXT_DIR = ROOT / "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO"
OTHER_TRANSLATIONS_DIR = ROOT / "OUTRAS TRADUÇÕES"
STATE_FILE = REVISIONS_DIR / "revisao_estado.json"
CONFIG_FILE = REVISIONS_DIR / "revisao_config.json"

AUDIO_EXTENSIONS = {".wav", ".waw"}
REFERENCE_AUDIO_EXTENSIONS = {".wav", ".wave", ".waw", ".mp3", ".ogg", ".flac", ".m4a", ".aac"}


def configure_project_root(project_root: Path) -> None:
    global ROOT, AUDIO_DIR, TEXT_DIR, OUTPUT_DIR, REVISIONS_DIR, ORIGINAL_TEXT_DIR, TRANSCRIBED_TRANSLATED_TEXT_DIR, OTHER_TRANSLATIONS_DIR, STATE_FILE, CONFIG_FILE
    ROOT = Path(project_root).expanduser().resolve()
    os.environ["DUBLASKIZON_PROJECT_ROOT"] = str(ROOT)
    AUDIO_DIR = ROOT / "WAV ORIGINAIS"
    TEXT_DIR = ROOT / "TXT TEXTO PORTUGUES"
    OUTPUT_DIR = ROOT / "dublado"
    REVISIONS_DIR = ROOT / "revisoes"
    ORIGINAL_TEXT_DIR = ROOT / "TXT TEXTO ORIGINAL"
    TRANSCRIBED_TRANSLATED_TEXT_DIR = ROOT / "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO"
    OTHER_TRANSLATIONS_DIR = ROOT / "OUTRAS TRADUÇÕES"
    STATE_FILE = REVISIONS_DIR / "revisao_estado.json"
    CONFIG_FILE = REVISIONS_DIR / "revisao_config.json"
DEFAULT_CONFIG = {
    "model": "edwixx/omnivoice-brpt-v15",
    "language": "pt",
    "instruct": "portuguese accent",
    "audacity_exe": "",
    "auto_open_after_generate": True,
    "ask_r_pronunciation": True,
    "other_translation_dir": "",
    "other_translation_root_dir": "",
}


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default.copy() if isinstance(default, dict) else default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def find_audacity_exe(configured: str) -> Path | None:
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate

    candidates = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        value = os.environ.get(env_name)
        if value:
            base = Path(value)
            candidates.extend(
                [
                    base / "Audacity" / "Audacity.exe",
                    base / "audacity" / "Audacity.exe",
                ]
            )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def open_audio_file(path: Path, config: dict) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {path}")

    audacity = find_audacity_exe(str(config.get("audacity_exe", "")))
    if audacity:
        subprocess.Popen([str(audacity), str(path)])
        return f"Aberto no Audacity: {path.name}"

    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
    return f"Aberto pelo aplicativo padrão: {path.name}"


def open_audio_pair(original: Path, dubbed: Path, stem: str, config: dict) -> str:
    """Abre original e dublagem como duas faixas no mesmo projeto Audacity."""
    if not original.exists():
        raise FileNotFoundError(f"Original não encontrado: {original}")
    if not dubbed.exists():
        return open_audio_file(original, config) + " (a dublagem ainda não existe)"

    audacity = find_audacity_exe(str(config.get("audacity_exe", "")))
    if audacity:
        REVISIONS_DIR.mkdir(parents=True, exist_ok=True)
        lof_path = _revision_scene_dir(stem) / f".audacity_{_scene_basename(stem)}.lof"
        lof_path.parent.mkdir(parents=True, exist_ok=True)
        lof_text = (
            "# Arquivo temporario criado pela ponte de revisao\n"
            f'file "{original}"\n'
            f'file "{dubbed}"\n'
        )
        lof_path.write_text(lof_text, encoding="utf-8")
        subprocess.Popen([str(audacity), str(lof_path)])
        return f"Aberto no Audacity: ORIGINAL acima / DUBLAGEM abaixo — {stem}"

    # Fallback: sem caminho detectado do Audacity, abre os dois no aplicativo padrão.
    # Nesse modo o Windows pode abrir duas janelas, em vez de duas faixas no mesmo projeto.
    if sys.platform.startswith("win"):
        os.startfile(str(original))  # type: ignore[attr-defined]
        os.startfile(str(dubbed))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(original), str(dubbed)])
    else:
        subprocess.Popen(["xdg-open", str(original)])
        subprocess.Popen(["xdg-open", str(dubbed)])
    return f"Audacity não foi localizado; arquivos abertos pelo aplicativo padrão — {stem}"


def scene_audio_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    if not AUDIO_DIR.is_dir():
        return files
    for path in sorted(AUDIO_DIR.rglob("*"), key=lambda item: str(item).casefold()):
        if (
            is_internal_omnivoice_backup(path)
            or is_format_archive_dir(path.parent)
            or not path.is_file()
            or path.suffix.lower() not in AUDIO_EXTENSIONS
        ):
            continue
        key = relative_scene_key(path, AUDIO_DIR)
        current = files.get(key)
        if current is None or path.suffix.lower() == ".wav":
            files[key] = path
    return files


def scene_text_files() -> dict[str, Path]:
    if not TEXT_DIR.is_dir():
        return {}
    return {
        relative_scene_key(path, TEXT_DIR): path
        for path in sorted(TEXT_DIR.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file() and path.suffix.lower() == ".txt"
    }


def original_text_files() -> dict[str, Path]:
    if not ORIGINAL_TEXT_DIR.is_dir():
        return {}
    return {
        relative_scene_key(path, ORIGINAL_TEXT_DIR): path
        for path in sorted(ORIGINAL_TEXT_DIR.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file() and path.suffix.lower() == ".txt"
    }


def transcribed_translated_text_files() -> dict[str, Path]:
    if not TRANSCRIBED_TRANSLATED_TEXT_DIR.is_dir():
        return {}
    return {
        relative_scene_key(path, TRANSCRIBED_TRANSLATED_TEXT_DIR): path
        for path in sorted(TRANSCRIBED_TRANSLATED_TEXT_DIR.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file() and path.suffix.lower() == ".txt"
    }


def other_translation_text_files(directory: Path | None = None) -> dict[str, Path]:
    directory = directory or OTHER_TRANSLATIONS_DIR
    if not directory.is_dir():
        return {}
    return {
        relative_scene_key(path, directory): path
        for path in sorted(directory.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file() and path.suffix.lower() == ".txt"
    }


def other_translation_folders(directory: Path | None = None) -> list[Path]:
    """Retorna as pastas de idiomas/traduções diretamente dentro da pasta escolhida."""
    directory = directory or OTHER_TRANSLATIONS_DIR
    if not directory.is_dir():
        return []
    return [
        path
        for path in sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        if path.is_dir()
    ]


def _revision_scene_dir(stem: str) -> Path:
    return REVISIONS_DIR / Path(stem).parent


def _scene_basename(stem: str) -> str:
    return Path(stem).name


def next_version(stem: str) -> int:
    highest = 0
    prefix = f"{_scene_basename(stem)}_v"
    directory = _revision_scene_dir(stem)
    if directory.is_dir():
        for path in directory.glob(f"{_scene_basename(stem)}_v*.wav"):
            suffix = path.stem[len(prefix) :]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return highest + 1


def next_text_version(stem: str) -> int:
    highest = 0
    prefix = f"{_scene_basename(stem)}_texto_v"
    directory = _revision_scene_dir(stem)
    if directory.is_dir():
        for path in directory.glob(f"{_scene_basename(stem)}_texto_v*.txt"):
            suffix = path.stem[len(prefix) :]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return highest + 1


class ReviewApp:
    def apply_theme(self, theme):
        root_bg = theme.get("root", "#F5F6FA")
        surface = theme.get("surface", "#FFFFFF")
        text = theme.get("text", "#1F2937")
        muted = theme.get("muted", "#64748B")
        input_bg = theme.get("input", surface)
        input_fg = theme.get("input_text", text)
        self.theme = theme
        neutral_fgs = {"#1F2937", "#334155", "#475569", "#555", "#64748B", "#6B7280"}
        def visit(widget):
            try:
                cls = widget.winfo_class()
                if cls == "TFrame":
                    widget.configure(style="TFrame")
                elif cls == "Frame":
                    widget.configure(bg=surface)
                elif cls == "Label":
                    if str(widget.cget("fg")) in neutral_fgs:
                        widget.configure(fg=text)
                    try:
                        widget.configure(bg=str(widget.master.cget("bg")))
                    except Exception:
                        widget.configure(bg=surface)
                elif cls == "Text":
                    text_background = input_bg
                    if widget is getattr(self, "text_box", None):
                        text_background = surface_color(theme, "portuguese", input_bg)
                    elif widget is getattr(self, "other_translation_box", None):
                        text_background = surface_color(theme, "other_translation", input_bg)
                    elif widget is getattr(self, "original_text_box", None):
                        text_background = surface_color(theme, "original", input_bg)
                    elif widget is getattr(self, "transcribed_text_box", None):
                        text_background = surface_color(theme, "transcribed", input_bg)
                    elif widget is getattr(self, "history_box", None) or widget is getattr(self, "regen_log_box", None):
                        text_background = surface_color(theme, "history", input_bg)
                    widget.configure(bg=text_background, fg=input_fg, insertbackground=input_fg)
                elif cls == "Entry":
                    widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg, readonlybackground=input_bg)
                elif cls == "Listbox":
                    widget.configure(bg=input_bg, fg=input_fg, selectbackground=theme.get("select", "#DBEAFE"), selectforeground=input_fg)
            except Exception:
                pass
            try:
                for child in widget.winfo_children():
                    visit(child)
            except Exception:
                pass
        visit(self.root)
        apply_button_style_to_tree(self.root, theme)
        try:
            style = ttk.Style(self.root)
            if hasattr(self, "scene_sort_combo"):
                style.configure("ReviewSort.TCombobox", fieldbackground=input_bg, background=input_bg, foreground=input_fg, arrowcolor=input_fg)
                style.map("ReviewSort.TCombobox", fieldbackground=[("readonly", input_bg)], foreground=[("readonly", input_fg)], selectbackground=[("readonly", select_bg)], selectforeground=[("readonly", input_fg)])
                self.scene_sort_combo.configure(style="ReviewSort.TCombobox")
            self.root.option_add("*ReviewSort.TCombobox*Listbox.background", input_bg)
            self.root.option_add("*ReviewSort.TCombobox*Listbox.foreground", input_fg)
            self.root.option_add("*ReviewSort.TCombobox*Listbox.selectBackground", select_bg)
            self.root.option_add("*ReviewSort.TCombobox*Listbox.selectForeground", input_fg)
        except Exception:
            pass
        try:
            style = ttk.Style(self.root)
            clone_color = surface_color(theme, "progress_clone", theme.get("select", "#2563EB"))
            dub_color = surface_color(theme, "progress_dub", "#7C3AED")
            track_color = surface_color(theme, "progress_track", theme.get("border", "#CBD5E1"))
            style.configure("RegenClone.Horizontal.TProgressbar", troughcolor=track_color, background=clone_color, lightcolor=clone_color, darkcolor=clone_color)
            style.configure("RegenDub.Horizontal.TProgressbar", troughcolor=track_color, background=dub_color, lightcolor=dub_color, darkcolor=dub_color)
        except Exception:
            pass
        if hasattr(self, "audio_player"):
            self.audio_player.apply_theme(theme)
        self._apply_other_audio_window_theme(theme)

    def __init__(self, root: Tk, embedded=False, batch_callback=None, project_actions=None):
        self.root = root
        self.embedded = embedded
        self.batch_callback = batch_callback
        self.project_actions = project_actions or {}
        self.central_log_callback = self.project_actions.get("central_log")
        if not embedded:
            self.root.title("Revisar dublagens - Audacity + OmniVoice")
            self.root.geometry("1120x760")
            self.root.minsize(760, 560)

        # A pasta revisoes e o arquivo de configuração só são criados por uma ação
        # que realmente grava uma revisão, uma configuração ou uma nova cena.
        self.config = load_json(CONFIG_FILE, DEFAULT_CONFIG)
        merged = DEFAULT_CONFIG.copy()
        merged.update(self.config)
        self.config = merged

        self.state = load_json(STATE_FILE, {})
        self.audio_by_stem = scene_audio_files()
        self.text_by_stem = scene_text_files()
        missing_text = sorted(set(self.audio_by_stem) - set(self.text_by_stem), key=str.casefold)
        if missing_text and messagebox.askyesno(
            "Áudios sem TXT",
            f"Foram encontrados {len(missing_text)} áudio(s) sem TXT acompanhante.\n\nDeseja gerar os TXT em branco agora?",
            parent=self.root,
        ):
            TEXT_DIR.mkdir(parents=True, exist_ok=True)
            for stem in missing_text:
                target = TEXT_DIR / f"{stem}.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch(exist_ok=True)
            self.text_by_stem = scene_text_files()
        self.original_text_by_stem = original_text_files()
        self.transcribed_translated_text_by_stem = transcribed_translated_text_files()
        configured_other_dir = str(self.config.get("other_translation_dir", "")).strip()
        configured_other_root = str(self.config.get("other_translation_root_dir", "")).strip()
        self.other_translation_dir = Path(configured_other_dir).expanduser().resolve() if configured_other_dir else OTHER_TRANSLATIONS_DIR
        self.other_translation_root_dir = Path(configured_other_root).expanduser().resolve() if configured_other_root else (OTHER_TRANSLATIONS_DIR if not configured_other_dir else self.other_translation_dir)
        if not self.other_translation_root_dir.is_dir():
            self.other_translation_root_dir = OTHER_TRANSLATIONS_DIR
        self.other_translation_by_stem = other_translation_text_files(self.other_translation_dir)
        self.other_translation_folder_buttons = []
        self.other_translation_var = StringVar(value=str(self.other_translation_dir) if self.other_translation_dir.is_dir() else "(nenhuma pasta selecionada)")
        self.other_translation_status_var = StringVar(value="Nenhuma tradução alternativa selecionada")
        self.use_other_translation_var = StringVar(value="0")
        self.selected_other_translation_text = ""
        self.selected_other_translation_file = None
        self.other_audio_window = None
        self.other_audio_list = None
        self.other_audio_paths: list[Path] = []
        self.other_audio_path_var = None
        self.other_audio_hint_var = None
        self.other_audio_choose_button = None
        self.other_audio_listen_button = None
        self.other_audio_confirm_button = None
        self.other_audio_cancel_button = None
        self.stems = sorted(set(self.audio_by_stem) & set(self.text_by_stem), key=str.casefold)
        self.default_stems = list(self.stems)
        self.scene_sort_mode = "default"
        self.current_index = 0
        self.busy = False
        self.request_r_var = StringVar(value="1" if bool(self.config.get("ask_r_pronunciation", True)) else "0")
        self.regen_r_override: str | None = None
        self.regen_stem: str | None = None
        self.regen_progress_callback = None
        self.player_refresh_callback = None
        self.process_message_callback = None
        self._last_history_mirror = None
        self.loaded_text = ""
        self.original_unlocked = False
        self.transcribed_unlocked = False
        self.audio_player = AudioPlayerManager(self.root, ROOT, status_callback=lambda text: (self.status_var.set(text), self._log_central(text, "info")))
        self.audio_player.set_scene_text_integration(self.load_scene_text_for_player, self.save_scene_text_from_player)

        self.status_var = StringVar(value="Pronto")
        self.audio_player.set_review_preferences({
            "auto_open_var": self.auto_open_var if hasattr(self, "auto_open_var") else None,
            "request_r_var": self.request_r_var,
            "request_r_command": self.toggle_r_request,
        })
        self.audio_player.set_scene_integration(self._sync_audio_player_selection, {
            "open_audacity": lambda stem: self.run_audio_review_action(stem, "open_audacity"),
            "approve": lambda stem: self.run_audio_review_action(stem, "approve"),
            "reject": lambda stem: self.run_audio_review_action(stem, "reject"),
            "redub": lambda stem: self.run_audio_review_action(stem, "redub"),
            "redub_other": lambda stem: self.run_audio_review_action(stem, "redub_other"),
        })
        self.scene_var = StringVar(value="Nenhuma cena selecionada")
        self.path_var = StringVar(value="")
        self.meta_var = StringVar(value="")
        self.scene_count_var = StringVar(value=f"DUBLADOS ({len(self.stems)} áudios)")
        self.regen_elapsed_var = StringVar(value="Refazer decorrido: 00:00:00")
        self.regen_eta_var = StringVar(value="Restante: 00:00:00")
        self.regen_phase_var = StringVar(value="Pronto para refazer a cena")
        self.regen_clone_progress = DoubleVar(value=0.0)
        self.regen_dub_progress = DoubleVar(value=0.0)
        self.regen_started_at = None
        self.regen_tick_id = None
        self.initial_text_divider_set = False

        self.build_ui()
        self.audio_player.set_review_snapshot_provider(self.player_review_snapshot)
        self.audio_player.set_review_preferences({
            "auto_open_var": self.auto_open_var,
            "auto_open_command": self.toggle_auto_open,
            "request_r_var": self.request_r_var,
            "request_r_command": self.toggle_r_request,
        })
        self.refresh_scene_list()
        if self.stems:
            self.select_scene(0)
        else:
            # A aba Batch pode estar aguardando o preparo do FFmpeg portátil.
            # Não abrir modal durante a construção da janela principal; o status fica
            # visível e a lista é atualizada quando a conversão pós-abertura terminar.
            self.status_var.set("Nenhum par de áudio + TXT disponível no momento.")

    def build_ui(self) -> None:
        header = ttk.Frame(self.root, padding=(12, 5, 12, 3))
        header.pack(fill="x")
        title_area = ttk.Frame(header)
        title_area.pack(side="left", fill="x", expand=True)
        ttk.Label(title_area, text="REVISAR DUBLAGENS", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        project_line = ttk.Frame(title_area)
        project_line.pack(fill="x", pady=(1, 0))
        ttk.Label(project_line, text="Projeto:").pack(side="left")
        self.project_entry = Entry(project_line, font=("Segoe UI", 9), relief="flat", bd=0, readonlybackground="#F5F6FA", fg="#334155", width=110)
        self.project_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.project_entry.insert(0, str(ROOT))
        self.project_entry.configure(state="readonly")
        project_actions = ttk.Frame(header)
        project_actions.pack(side="right", padx=(12, 0))
        Button(project_actions, text="SELECIONAR PROJETO", command=self.project_actions.get("select_project", lambda: None), bg="#2563EB", activebackground="#1D4ED8", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5, cursor="hand2").pack(side="left", padx=(4, 0))
        Button(project_actions, text="USAR PASTA DO EXE", command=self.project_actions.get("use_exe_folder", lambda: None), bg="#475569", activebackground="#334155", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5, cursor="hand2").pack(side="left", padx=(4, 0))
        Button(project_actions, text="TUTORIAL PDF", command=self.project_actions.get("tutorial", lambda: None), bg="#D97706", activebackground="#B45309", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5, cursor="hand2").pack(side="left", padx=(4, 0))

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.main_pane = ttk.PanedWindow(main, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True)

        left = ttk.Frame(self.main_pane, padding=8, width=220)
        self.main_pane.add(left, weight=1)
        right = ttk.Frame(self.main_pane, padding=8)
        self.main_pane.add(right, weight=4)

        scene_list_header = ttk.Frame(left)
        scene_list_header.pack(fill="x")
        ttk.Label(scene_list_header, textvariable=self.scene_count_var, font=("Segoe UI", 10, "bold")).pack(side="left", anchor="w")
        self.scene_sort_var = StringVar(value="Padrão")
        self.scene_sort_combo = ttk.Combobox(
            scene_list_header,
            textvariable=self.scene_sort_var,
            values=("Padrão", "Aprovadas primeiro", "Rejeitadas primeiro", "Aprovadas e rejeitadas primeiro"),
            state="readonly",
            width=25,
        )
        self.scene_sort_combo.pack(side="right", padx=(5, 0))
        self.scene_sort_combo.bind("<<ComboboxSelected>>", self._on_scene_sort_selected)
        ttk.Label(left, text="Organizar DUBLADOS", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(2, 0))
        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.scene_list = Listbox(list_frame, exportselection=False, activestyle="dotbox")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.scene_list.yview)
        self.scene_list.configure(yscrollcommand=scrollbar.set)
        self.scene_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.scene_list.bind("<<ListboxSelect>>", self.on_scene_selected)
        self.scene_list.bind("<Double-Button-1>", self.play_selected_scene)
        self.scene_list.bind("<Button-3>", self.show_scene_context_menu)
        scene_audio_controls = ttk.Frame(left)
        scene_audio_controls.pack(fill="x", pady=(6, 0))
        self.play_scene_button = Button(scene_audio_controls, text="▶ OUVIR CENA", command=self.play_selected_scene, bg="#0F766E", activebackground="#115E59", fg="white", relief="flat", padx=8, pady=4, cursor="hand2")
        self.play_scene_button.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.play_all_button = Button(scene_audio_controls, text="▶ OUVIR TODOS", command=self.play_all_scenes, bg="#7C3AED", activebackground="#6D28D9", fg="white", relief="flat", padx=8, pady=4, cursor="hand2")
        self.play_all_button.pack(side="left", fill="x", expand=True, padx=(3, 0))

        ttk.Label(right, textvariable=self.scene_var, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(right, textvariable=self.meta_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(right, textvariable=self.path_var, foreground="#555").pack(anchor="w", pady=(1, 5))

        # Uma única PanedWindow abriga as duas colunas completas. Assim, a divisória
        # vertical é única e permanece exatamente na mesma posição nas duas linhas.
        self.text_columns = ttk.PanedWindow(right, orient="horizontal")
        self.text_columns.pack(fill="x", expand=False, pady=(0, 12))
        self.text_columns.bind("<Map>", self.schedule_initial_text_divider, add="+")
        left_column = ttk.Frame(self.text_columns)
        right_column = ttk.Frame(self.text_columns)
        self.text_columns.add(left_column, weight=2)
        self.text_columns.add(right_column, weight=1)
        for column in (left_column, right_column):
            column.grid_columnconfigure(0, weight=1)
            column.grid_rowconfigure(0, weight=1)
            column.grid_rowconfigure(1, weight=1)

        portuguese_panel = ttk.Frame(left_column, padding=(0, 0, 6, 0))
        portuguese_panel.grid(row=0, column=0, sticky="nsew")
        text_header = ttk.Frame(portuguese_panel)
        text_header.pack(fill="x")
        ttk.Label(text_header, text="Texto em português — editável").pack(side="left", anchor="w")
        self.save_text_button = Button(text_header, text="Salvar alteração", command=self.save_text_changes, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.save_text_button, getattr(self, "theme", {}), "primary")
        self.save_text_button.pack(side="right")
        text_frame = ttk.Frame(portuguese_panel)
        text_frame.pack(fill="both", expand=True, pady=(5, 0))
        self.text_box = Text(text_frame, height=8, wrap="word", state="normal", font=("Segoe UI", 11), background="#E8F5E9", undo=True)
        text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_box.yview)
        self.text_box.configure(yscrollcommand=text_scrollbar.set)
        self.text_box.pack(side="left", fill="both", expand=True)
        text_scrollbar.pack(side="right", fill="y")

        other_panel = ttk.Frame(right_column, padding=(6, 0, 0, 0))
        other_panel.grid(row=0, column=0, sticky="nsew")
        other_header = ttk.Frame(other_panel)
        other_header.pack(fill="x")
        ttk.Label(other_header, text="OUTRAS TRADUÇÕES").pack(side="left", anchor="w")
        self.other_translation_folders_bar = ttk.Frame(other_header)
        self.other_translation_folders_bar.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.refresh_other_translation_folder_buttons()
        other_meta = ttk.Frame(other_header)
        other_meta.pack(side="right", padx=(6, 0))
        self.other_translation_check = ttk.Checkbutton(other_meta, text="Usar na REFAZER CENA", variable=self.use_other_translation_var, onvalue="1", offvalue="0", command=self.on_other_translation_toggle)
        self.other_translation_check.pack(side="right")
        self.other_translation_status_label = ttk.Label(other_meta, textvariable=self.other_translation_status_var, foreground="#64748B", anchor="e")
        self.other_translation_status_label.pack(side="right", padx=(0, 8))
        self.other_translation_box = Text(other_panel, height=8, wrap="word", state="disabled", font=("Segoe UI", 11), background="#F0FDFA")
        other_text_scrollbar = ttk.Scrollbar(other_panel, orient="vertical", command=self.other_translation_box.yview)
        self.other_translation_box.configure(yscrollcommand=other_text_scrollbar.set)
        self.other_translation_box.pack(side="left", fill="both", expand=True, pady=(5, 0))
        other_text_scrollbar.pack(side="right", fill="y", pady=(5, 0))

        original_panel = ttk.Frame(left_column, padding=(0, 5, 6, 0))
        original_panel.grid(row=1, column=0, sticky="nsew")
        original_header = ttk.Frame(original_panel)
        original_header.pack(fill="x")
        ttk.Label(original_header, text="TEXTO ORIGINAL — editável").pack(side="left", anchor="w")
        self.original_save_button = Button(original_header, text="SALVAR", command=self.save_original_text, bg="#2563EB", activebackground="#1D4ED8", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.original_save_button.pack(side="right", padx=(4, 0))
        self.original_lock_button = Button(original_header, text="DESTRAVAR", command=lambda: self.toggle_reference_edit("original"), bg="#64748B", activebackground="#475569", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.original_lock_button.pack(side="right", padx=(4, 0))
        original_text_frame = ttk.Frame(original_panel)
        original_text_frame.pack(fill="both", expand=True, pady=(5, 0))
        self.original_text_box = Text(original_text_frame, height=8, wrap="word", state="disabled", font=("Segoe UI", 10), background="#F2F2F2")
        original_text_scrollbar = ttk.Scrollbar(original_text_frame, orient="vertical", command=self.original_text_box.yview)
        self.original_text_box.configure(yscrollcommand=original_text_scrollbar.set)
        self.original_text_box.pack(side="left", fill="both", expand=True)
        original_text_scrollbar.pack(side="right", fill="y")
        self.original_text_box.bind("<Control-c>", self.copy_selected_text)

        transcribed_panel = ttk.Frame(right_column, padding=(6, 5, 0, 0))
        transcribed_panel.grid(row=1, column=0, sticky="nsew")
        transcribed_header = ttk.Frame(transcribed_panel)
        transcribed_header.pack(fill="x")
        ttk.Label(transcribed_header, text="TEXTO do WAV TRANSCRITO e TRADUZIDO — editável").pack(side="left", anchor="w")
        self.transcribed_save_button = Button(transcribed_header, text="SALVAR", command=self.save_transcribed_text, bg="#0F766E", activebackground="#115E59", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.transcribed_save_button.pack(side="right", padx=(4, 0))
        self.transcribed_lock_button = Button(transcribed_header, text="DESTRAVAR", command=lambda: self.toggle_reference_edit("transcribed"), bg="#64748B", activebackground="#475569", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.transcribed_lock_button.pack(side="right", padx=(4, 0))
        transcribed_text_frame = ttk.Frame(transcribed_panel)
        transcribed_text_frame.pack(fill="both", expand=True, pady=(5, 0))
        self.transcribed_text_box = Text(transcribed_text_frame, height=8, wrap="word", state="disabled", font=("Segoe UI", 10), background="#EEF6F5")
        transcribed_text_scrollbar = ttk.Scrollbar(transcribed_text_frame, orient="vertical", command=self.transcribed_text_box.yview)
        self.transcribed_text_box.configure(yscrollcommand=transcribed_text_scrollbar.set)
        self.transcribed_text_box.pack(side="left", fill="both", expand=True)
        transcribed_text_scrollbar.pack(side="right", fill="y")
        self.transcribed_text_box.bind("<Control-c>", self.copy_selected_text)

        navigation = ttk.Frame(right)
        navigation.pack(fill="x", pady=(0, 8))
        self.previous_button = Button(navigation, text="<< Anterior", command=self.previous_scene, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.previous_button, getattr(self, "theme", {}), "secondary")
        self.previous_button.pack(side="left")
        self.next_button = Button(navigation, text="Próxima >>", command=self.next_scene, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.next_button, getattr(self, "theme", {}), "primary")
        self.next_button.pack(side="left", padx=(6, 0))
        self.open_project_button = Button(navigation, text="Abrir pasta do projeto", command=self.open_project_folder, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.open_project_button, getattr(self, "theme", {}), "teal")
        self.open_project_button.pack(side="right")

        actions = ttk.LabelFrame(right, text="Revisão", padding=10)
        actions.pack(fill="x", pady=(0, 8))
        self.auto_open_var = StringVar(value="1" if bool(self.config.get("auto_open_after_generate", True)) else "0")
        self.auto_open_check = ttk.Checkbutton(actions, text="Abrir Audacity após redublar", variable=self.auto_open_var, onvalue="1", offvalue="0", command=self.toggle_auto_open)
        self.auto_open_check.grid(row=0, column=3, pady=(0, 4), padx=6, sticky="w")
        self.request_r_check = ttk.Checkbutton(actions, text="Pedido de alterar pronúncia do R", variable=self.request_r_var, onvalue="1", offvalue="0", command=self.toggle_r_request)
        self.request_r_check.grid(row=0, column=4, pady=(0, 4), padx=(6, 0), sticky="w")
        self.open_button = Button(actions, text="Abrir ORIGINAL + DUBLAGEM no Audacity", command=self.open_current_pair, bg="#F2C94C", activebackground="#D4A72C", fg="#3B2F00", activeforeground="#3B2F00", relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=6, cursor="hand2")
        self.open_button.grid(row=1, column=0, padx=(0, 6), pady=4, sticky="ew")
        self.approve_button = Button(actions, text="Aprovar", command=self.approve_scene, bg="#2563EB", activebackground="#1D4ED8", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=6, cursor="hand2")
        self.approve_button.grid(row=1, column=1, padx=6, pady=4, sticky="ew")
        self.reject_button = Button(actions, text="Rejeitar", command=self.reject_scene, bg="#DC2626", activebackground="#B91C1C", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=6, cursor="hand2")
        self.reject_button.grid(row=1, column=2, padx=6, pady=4, sticky="ew")
        self.regenerate_button = Button(actions, text="REDUBLAR", command=self._redub_with_r_request, bg="#16A34A", activebackground="#15803D", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=6, cursor="hand2")
        self.regenerate_button.grid(row=1, column=3, padx=6, pady=4, sticky="ew")
        self.regenerate_other_audio_button = Button(actions, text="REDUBLAR COM OUTRO ÁUDIO", command=self._redub_other_with_r_request, bg="#7C3AED", activebackground="#6D28D9", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=6, cursor="hand2")
        self.regenerate_other_audio_button.grid(row=1, column=4, padx=(6, 0), pady=4, sticky="ew")
        for column in range(5):
            actions.columnconfigure(column, weight=1, uniform="review_actions")

        history = ttk.LabelFrame(right, text="Histórico da cena", padding=8)
        history.pack(fill="x", expand=False)
        self.history_pane = ttk.PanedWindow(history, orient="horizontal")
        self.history_pane.pack(fill="x", expand=False)
        history_left = ttk.Frame(self.history_pane, padding=(0, 0, 6, 0))
        history_right = ttk.Frame(self.history_pane, padding=(6, 0, 0, 0))
        self.history_pane.add(history_left, weight=1)
        self.history_pane.add(history_right, weight=1)
        ttk.Label(history_left, text="HISTÓRICO DA CENA", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.history_box = Text(history_left, height=6, wrap="word", state="disabled", font=("Consolas", 9))
        self.history_box.pack(fill="both", expand=True, pady=(4, 0))
        ttk.Label(history_right, text="REFAZENDO A CENA", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        regen_style = ttk.Style(self.root)
        regen_style.configure("RegenClone.Horizontal.TProgressbar", troughcolor="#E2E8F0", background="#2F75B5", lightcolor="#2F75B5", darkcolor="#2F75B5")
        regen_style.configure("RegenDub.Horizontal.TProgressbar", troughcolor="#E2E8F0", background="#9B7BC5", lightcolor="#9B7BC5", darkcolor="#9B7BC5")
        regen_bars = ttk.Frame(history_right)
        regen_bars.pack(fill="x", pady=(4, 2))
        clone_column = ttk.Frame(regen_bars)
        clone_column.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Label(clone_column, text="CLONANDO REFERÊNCIA", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.regen_clone_bar = ttk.Progressbar(clone_column, orient="horizontal", mode="determinate", style="RegenClone.Horizontal.TProgressbar", maximum=100, variable=self.regen_clone_progress)
        self.regen_clone_bar.pack(fill="x", pady=(2, 0))
        dub_column = ttk.Frame(regen_bars)
        dub_column.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ttk.Label(dub_column, text="DUBLANDO CENA", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.regen_dub_bar = ttk.Progressbar(dub_column, orient="horizontal", mode="determinate", style="RegenDub.Horizontal.TProgressbar", maximum=100, variable=self.regen_dub_progress)
        self.regen_dub_bar.pack(fill="x", pady=(2, 0))
        ttk.Label(history_right, textvariable=self.regen_phase_var, foreground="#475569", font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 2))
        self.regen_log_box = Text(history_right, height=4, wrap="word", state="disabled", font=("Consolas", 8), background="#F8FAFC")
        regen_log_scroll = ttk.Scrollbar(history_right, orient="vertical", command=self.regen_log_box.yview)
        self.regen_log_box.configure(yscrollcommand=regen_log_scroll.set)
        self.regen_log_box.pack(side="left", fill="both", expand=True)
        regen_log_scroll.pack(side="right", fill="y")

        folder_bar = ttk.Frame(self.root, padding=(12, 0, 12, 6))
        folder_bar.pack(fill="x")
        self.make_folder_button(folder_bar, "WAV ORIGINAL", AUDIO_DIR, "#2F75B5").pack(side="left", padx=(0, 3))
        self.make_folder_button(folder_bar, "WAV DUBLADO", OUTPUT_DIR, "#9B7BC5").pack(side="left", padx=3)
        self.make_folder_button(folder_bar, "REVISÕES", REVISIONS_DIR, "#3A7D44").pack(side="left", padx=3)
        self.make_folder_button(folder_bar, "TXT PT", TEXT_DIR, "#D97706").pack(side="left", padx=3)
        self.make_folder_button(folder_bar, "TXT ORIGINAL", ORIGINAL_TEXT_DIR, "#475569").pack(side="left", padx=3)
        self.make_folder_button(folder_bar, "TXT TRANSCRITO", TRANSCRIBED_TRANSLATED_TEXT_DIR, "#0F766E").pack(side="left", padx=3)
        self.other_folder_button = Button(folder_bar, text="OUTRAS TRADUÇÕES", command=lambda: self.open_folder(self.other_translation_root_dir, "OUTRAS TRADUÇÕES"), bg="#7C3AED", fg="white", activebackground="#7C3AED", activeforeground="white", relief="flat", padx=9, pady=4, cursor="hand2")
        self.other_folder_button.pack(side="left", padx=3)
        regen_clock_box = ttk.Frame(folder_bar)
        regen_clock_box.pack(side="left", padx=(7, 0))
        ttk.Label(regen_clock_box, textvariable=self.regen_elapsed_var, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 7))
        ttk.Label(regen_clock_box, textvariable=self.regen_eta_var, font=("Segoe UI", 8)).pack(side="left")
        ttk.Label(folder_bar, text="A regeneração cria versões em revisoes\\ e preserva a cena atual.", justify="right", anchor="e", font=("Segoe UI", 8)).pack(side="right", padx=(8, 0))

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")

    def schedule_initial_text_divider(self, _event=None) -> None:
        """Centraliza depois que a aba e a escala terminarem de calcular a largura."""
        if not self.initial_text_divider_set:
            for delay, final_attempt in ((0, False), (100, False), (300, False), (700, True)):
                self.root.after(delay, lambda final=final_attempt: self.set_initial_text_divider(final))

    def set_initial_text_divider(self, final_attempt: bool = False) -> None:
        """Inicia a divisão central como no layout desejado, sem travar o arraste."""
        if self.initial_text_divider_set:
            return
        try:
            self.text_columns.update_idletasks()
            width = self.text_columns.winfo_width()
            if width < 500:
                if final_attempt:
                    self.root.after(250, lambda: self.set_initial_text_divider(True))
                return
            self.text_columns.sashpos(0, int(width * 0.50))
            if final_attempt:
                self.initial_text_divider_set = True
        except Exception:
            if final_attempt:
                self.root.after(250, lambda: self.set_initial_text_divider(True))

    def _log_central(self, text, tag="normal") -> None:
        callback = getattr(self, "central_log_callback", None)
        if callable(callback):
            try:
                callback("REVISÃO", str(text), tag)
            except Exception:
                pass

    def append_regen_log(self, text: str) -> None:
        tag = "error" if str(text).startswith("ERRO") else "normal"
        self._log_central(text, tag)
        callback = getattr(self, "process_message_callback", None)
        if callable(callback):
            try:
                current_stem = getattr(self, "current_stem", lambda: None)()
                callback(getattr(self, "regen_stem", None) or current_stem, text, tag, "REFAZENDO A CENA")
            except Exception:
                pass
        self.regen_log_box.configure(state="normal")
        self.regen_log_box.insert(END, i18n.tr(str(text)).rstrip() + "\n")
        self.regen_log_box.see(END)
        self.regen_log_box.configure(state="disabled")

    def update_regen_clock(self) -> None:
        if not self.busy or self.regen_started_at is None:
            return
        elapsed = max(0.0, time.monotonic() - self.regen_started_at)
        if elapsed < 2.0:
            clone = min(95.0, elapsed / 2.0 * 95.0)
            dub = 0.0
            self.regen_phase_var.set("CLONANDO REFERÊNCIA...")
        else:
            clone = 100.0
            dub = min(95.0, 5.0 + (elapsed - 2.0) * 8.0)
            self.regen_phase_var.set("DUBLANDO CENA...")
        self.regen_clone_progress.set(clone)
        self.regen_dub_progress.set(dub)
        total_progress = (clone + dub) / 2.0
        if total_progress > 1.0:
            remaining = max(0.0, elapsed * (100.0 - total_progress) / total_progress)
            self.regen_eta_var.set(f"Restante: {format_duration(remaining)}")
        else:
            self.regen_eta_var.set("Restante: calculando...")
        self.regen_elapsed_var.set(f"Refazer decorrido: {format_duration(elapsed)}")
        self._notify_regen_progress(clone, dub, self.regen_phase_var.get())
        self.regen_tick_id = self.root.after(250, self.update_regen_clock)

    def finish_regen_clock(self, success: bool) -> None:
        if self.regen_tick_id is not None:
            try:
                self.root.after_cancel(self.regen_tick_id)
            except Exception:
                pass
            self.regen_tick_id = None
        elapsed = max(0.0, time.monotonic() - self.regen_started_at) if self.regen_started_at else 0.0
        self.regen_elapsed_var.set(f"Refazer decorrido: {format_duration(elapsed)}")
        self.regen_eta_var.set("Restante: 00:00:00")
        self.regen_clone_progress.set(100.0 if success else self.regen_clone_progress.get())
        self.regen_dub_progress.set(100.0 if success else self.regen_dub_progress.get())
        self.regen_phase_var.set("REFAZER CENA concluído." if success else "REFAZER CENA com erro.")
        self._notify_regen_progress(self.regen_clone_progress.get(), self.regen_dub_progress.get(), self.regen_phase_var.get(), done=True, success=success)

    def copy_selected_text(self, event=None):
        widget = getattr(event, "widget", None)
        if widget is None:
            return "break"
        try:
            selected = widget.get("sel.first", "sel.last")
        except Exception:
            return "break"
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
            self.status_var.set("Texto selecionado copiado para a área de transferência.")
        except Exception:
            pass
        return "break"

    def set_reference_edit_state(self, kind: str, unlocked: bool) -> None:
        if kind == "original":
            box = self.original_text_box
            lock_button = self.original_lock_button
            save_button = self.original_save_button
            self.original_unlocked = unlocked
        else:
            box = self.transcribed_text_box
            lock_button = self.transcribed_lock_button
            save_button = self.transcribed_save_button
            self.transcribed_unlocked = unlocked
        box.configure(state="normal" if unlocked else "disabled")
        lock_button.configure(text="TRAVAR" if unlocked else "DESTRAVAR")
        save_button.configure(state="normal" if unlocked and not self.busy else "disabled")

    def toggle_reference_edit(self, kind: str) -> None:
        if self.busy:
            return
        unlocked = not (self.original_unlocked if kind == "original" else self.transcribed_unlocked)
        self.set_reference_edit_state(kind, unlocked)
        label = "destravado para edição" if unlocked else "travado para leitura"
        self.status_var.set(f"Painel {kind} {label}.")

    def save_original_text(self) -> bool:
        if not self.original_unlocked:
            return False
        stem = self.current_stem()
        if not stem:
            return False
        text = self.original_text_box.get("1.0", "end-1c").strip()
        try:
            ORIGINAL_TEXT_DIR.mkdir(parents=True, exist_ok=True)
            path = ORIGINAL_TEXT_DIR / f"{stem}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n", encoding="utf-8")
            self.original_text_by_stem[stem] = path
            self.set_reference_edit_state("original", False)
            self.status_var.set(f"Texto original salvo: {path.name}")
            self._log_central(f"Texto original salvo: {path}", "ok")
            return True
        except OSError as exc:
            messagebox.showerror("Texto original", f"Não foi possível salvar o texto original:\n{exc}", parent=self.root)
            return False

    def save_transcribed_text(self) -> bool:
        if not self.transcribed_unlocked:
            return False
        stem = self.current_stem()
        if not stem:
            return False
        text = self.transcribed_text_box.get("1.0", "end-1c").strip()
        try:
            TRANSCRIBED_TRANSLATED_TEXT_DIR.mkdir(parents=True, exist_ok=True)
            path = TRANSCRIBED_TRANSLATED_TEXT_DIR / f"{stem}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n", encoding="utf-8")
            self.transcribed_translated_text_by_stem[stem] = path
            self.set_reference_edit_state("transcribed", False)
            self.status_var.set(f"Texto transcrito/traduzido salvo: {path.name}")
            self._log_central(f"Texto transcrito/traduzido salvo: {path}", "ok")
            return True
        except OSError as exc:
            messagebox.showerror("Texto transcrito/traduzido", f"Não foi possível salvar o texto:\n{exc}", parent=self.root)
            return False

    def refresh_other_translation_folder_buttons(self) -> None:
        """Mostra as subpastas disponíveis acima do painel de texto alternativo."""
        bar = getattr(self, "other_translation_folders_bar", None)
        if bar is None:
            return
        for button in getattr(self, "other_translation_folder_buttons", []):
            try:
                button.destroy()
            except tk.TclError:
                pass
        self.other_translation_folder_buttons = []
        try:
            for child in bar.winfo_children():
                child.destroy()
        except tk.TclError:
            return

        root_dir = self.other_translation_root_dir
        folders = other_translation_folders(root_dir)
        # Também oferece a pasta principal como botão quando ela contém TXT diretamente.
        if root_dir.is_dir() and any(
            path.is_file() and path.suffix.lower() == ".txt"
            for path in root_dir.iterdir()
        ):
            folders.insert(0, root_dir)

        if not folders:
            ttk.Label(
                bar,
                text="Nenhuma subpasta encontrada. Crie subpastas de idiomas dentro de OUTRAS TRADUÇÕES.",
                foreground="#64748B",
            ).pack(side="left", anchor="w")
            return

        active_dir = self.other_translation_dir.resolve()
        for folder in folders:
            is_active = folder.resolve() == active_dir
            label = "PASTA PRINCIPAL" if folder.resolve() == root_dir.resolve() else folder.name
            button = Button(
                bar,
                text=label,
                command=lambda path=folder: self.select_other_translation_subfolder(path),
                relief="flat",
                font=("Segoe UI", 8, "bold"),
                padx=7,
                pady=3,
                cursor="hand2",
            )
            apply_button_style(button, getattr(self, "theme", {}), "accent" if is_active else "secondary")
            button.pack(side="left", padx=(0, 4))
            self.other_translation_folder_buttons.append(button)

    def select_other_translation_subfolder(self, folder: Path) -> None:
        selected = Path(folder).expanduser().resolve()
        if not selected.is_dir():
            return
        self.other_translation_dir = selected
        self.config["other_translation_dir"] = str(selected)
        self.config["other_translation_root_dir"] = str(self.other_translation_root_dir)
        save_json(CONFIG_FILE, self.config)
        self.other_translation_by_stem = other_translation_text_files(selected)
        self.other_translation_var.set(str(selected))
        self.use_other_translation_var.set("0")
        self.refresh_other_translation_folder_buttons()
        self.refresh_other_translation_text(self.current_stem())
        self.status_var.set(f"Pasta de tradução ativa: {selected.name}")
        self.set_action_state()

    def select_other_translation_folder(self) -> None:
        if filedialog is None:
            return
        selected = filedialog.askdirectory(parent=self.root, title="Escolher pasta OUTRAS TRADUÇÕES", initialdir=str(self.other_translation_root_dir) if self.other_translation_root_dir.is_dir() else str(ROOT))
        if not selected:
            return
        self.other_translation_root_dir = Path(selected).expanduser().resolve()
        self.other_translation_dir = self.other_translation_root_dir
        self.config["other_translation_dir"] = str(self.other_translation_dir)
        self.config["other_translation_root_dir"] = str(self.other_translation_root_dir)
        save_json(CONFIG_FILE, self.config)
        self.other_translation_by_stem = other_translation_text_files(self.other_translation_dir)
        self.other_translation_var.set(str(self.other_translation_dir))
        self.use_other_translation_var.set("0")
        self.refresh_other_translation_folder_buttons()
        self.refresh_other_translation_text(self.current_stem())
        self.status_var.set(f"Pasta de outras traduções selecionada: {self.other_translation_dir}")
        self.set_action_state()

    def read_optional_text(self, path: Path | None, missing_message: str) -> str:
        if path is None:
            return missing_message
        try:
            return path.read_text(encoding="utf-8-sig").strip()
        except UnicodeDecodeError:
            return "[TXT não está em UTF-8]"
        except OSError as exc:
            return f"[Não foi possível ler o TXT: {exc}]"

    def refresh_other_translation_text(self, stem: str | None) -> None:
        self.selected_other_translation_file = self.other_translation_by_stem.get(stem) if stem else None
        if self.selected_other_translation_file:
            self.selected_other_translation_text = self.read_optional_text(self.selected_other_translation_file, "")
            self.other_translation_status_var.set(f"Arquivo carregado: {self.selected_other_translation_file.name}")
        else:
            self.selected_other_translation_text = ""
            self.other_translation_status_var.set("Nenhum TXT correspondente a esta cena na pasta selecionada")
        if not hasattr(self, "other_translation_box"):
            return
        self.other_translation_box.configure(state="normal")
        self.other_translation_box.delete("1.0", END)
        if self.selected_other_translation_file:
            self.other_translation_box.insert("1.0", self.selected_other_translation_text)
        else:
            self.other_translation_box.insert("1.0", "[Nenhum TXT correspondente encontrado]")
        self.other_translation_box.configure(state="disabled")
        self.other_translation_check.configure(state="normal" if self.selected_other_translation_file else "disabled")
        if not self.selected_other_translation_file:
            self.use_other_translation_var.set("0")

    def on_other_translation_toggle(self) -> None:
        if self.use_other_translation_var.get() == "1" and not self.selected_other_translation_file:
            self.use_other_translation_var.set("0")
            messagebox.showwarning("Outras traduções", "Nenhum TXT correspondente à cena atual foi encontrado.", parent=self.root)
            return
        if self.use_other_translation_var.get() == "1":
            self.status_var.set(f"REFAZER CENA usará: {self.selected_other_translation_file.name}")
        else:
            self.status_var.set("REFAZER CENA usará o Texto em português")

    def open_batch(self):
        if self.batch_callback is not None:
            self.batch_callback()
            self.status_var.set("Aba de clonagem + dublagem selecionada.")

    def current_scene_playback_path(self, stem: str) -> Path | None:
        return self.review_audio(stem) or self.audio_by_stem.get(stem)

    def _scene_stem_from_context_event(self, event):
        """Seleciona a cena sob o botão direito e retorna sua chave relativa."""
        if not self.stems or not hasattr(self, "scene_list"):
            return None
        try:
            index = int(self.scene_list.nearest(event.y))
            bounds = self.scene_list.bbox(index)
        except (AttributeError, tk.TclError, TypeError, ValueError):
            return None
        if not bounds or not (bounds[1] <= event.y < bounds[1] + bounds[3]) or index >= len(self.stems):
            return None
        self.scene_list.selection_clear(0, END)
        self.scene_list.selection_set(index)
        self.scene_list.see(index)
        return self.stems[index]

    def _context_audio_paths(self, stem: str):
        original = self.audio_by_stem.get(stem)
        dubbed = self.current_output(stem)
        return original if original is not None and original.is_file() else None, dubbed if dubbed.is_file() else None

    def open_scene_audio_folder(self, stem: str | None = None, kind: str = "dubbed") -> None:
        if stem is None:
            selection = self.scene_list.curselection()
            stem = self.stems[int(selection[0])] if selection else None
        if not stem:
            self.status_var.set("Selecione um áudio para acessar o local.")
            return
        original, dubbed = self._context_audio_paths(stem)
        path = dubbed if kind == "dubbed" else original
        label = "dublado" if kind == "dubbed" else "original"
        if path is None:
            self.status_var.set(f"Áudio {label} não encontrado para: {Path(stem).name}")
            return
        if reveal_in_file_manager(path):
            self.status_var.set(f"Pasta do áudio {label} aberta: {path.parent}")
        else:
            self.status_var.set(f"Não foi possível abrir a pasta do áudio {label}: {path.parent}")

    def _copy_context_value(self, value: str, success_message: str) -> None:
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.root.update()
            self.status_var.set(success_message)
        except tk.TclError as exc:
            self.status_var.set(f"Não foi possível copiar: {exc}")

    def copy_scene_audio_name(self, stem: str | None = None) -> None:
        if stem is None:
            selection = self.scene_list.curselection()
            stem = self.stems[int(selection[0])] if selection else None
        if not stem:
            self.status_var.set("Selecione um áudio para copiar o nome.")
            return
        original, dubbed = self._context_audio_paths(stem)
        path = dubbed or original
        name = path.name if path is not None else f"{Path(stem).name}.wav"
        self._copy_context_value(name, f"Nome copiado: {name}")

    def copy_scene_audio_folder(self, stem: str | None, kind: str) -> None:
        if not stem:
            self.status_var.set("Selecione uma cena para copiar o local do áudio.")
            return
        original, dubbed = self._context_audio_paths(stem)
        path = dubbed if kind == "dubbed" else original
        label = "dublado" if kind == "dubbed" else "original"
        if path is None:
            self.status_var.set(f"Áudio {label} não encontrado para: {Path(stem).name}")
            return
        self._copy_context_value(str(path.parent), f"Local da pasta {label} copiado: {path.parent}")

    def show_scene_context_menu(self, event):
        stem = self._scene_stem_from_context_event(event)
        if not stem:
            return "break"
        theme = getattr(self, "theme", {})
        menu = Menu(
            self.root,
            tearoff=0,
            bg=theme.get("input", "#FFFFFF"),
            fg=theme.get("input_text", "#1F2937"),
            activebackground=theme.get("select", "#DBEAFE"),
            activeforeground=theme.get("input_text", "#1F2937"),
        )
        menu.add_command(label=i18n.tr("ABRIR LOCAL DO ÁUDIO DUBLADO"), command=lambda: self.open_scene_audio_folder(stem, "dubbed"))
        menu.add_command(label=i18n.tr("ABRIR LOCAL DO ÁUDIO ORIGINAL"), command=lambda: self.open_scene_audio_folder(stem, "original"))
        menu.add_separator()
        menu.add_command(label=i18n.tr("COPIAR NOME DO ÁUDIO"), command=lambda: self.copy_scene_audio_name(stem))
        menu.add_command(label=i18n.tr("COPIAR LOCAL DO ÁUDIO DUBLADO"), command=lambda: self.copy_scene_audio_folder(stem, "dubbed"))
        menu.add_command(label=i18n.tr("COPIAR LOCAL DO ÁUDIO ORIGINAL"), command=lambda: self.copy_scene_audio_folder(stem, "original"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _sync_audio_player_selection(self, scene_key: str | None, index: int) -> None:
        if not self.stems:
            return
        target = self.stems.index(scene_key) if scene_key in self.stems else index
        if target < 0 or target >= len(self.stems):
            return
        self.select_scene(target)

    def run_audio_review_action(self, stem: str | None, action: str) -> None:
        """Executa uma ação da Revisão na cena mostrada em OUVIR CENA."""
        if stem in self.stems:
            self.select_scene(self.stems.index(stem))
        elif not self.current_stem():
            return
        audio_window = getattr(self.audio_player, "window", None)
        callbacks = {
            "open_audacity": self.open_current_pair,
            "approve": self.approve_scene,
            "reject": lambda: self.reject_scene(dialog_parent=audio_window),
            "redub": lambda: self._redub_with_r_request(dialog_parent=audio_window),
            "redub_other": lambda: self._redub_other_with_r_request(dialog_parent=audio_window),
        }
        callback = callbacks.get(action)
        if callback is not None:
            callback()
        audio_window = getattr(self.audio_player, "window", None)
        if audio_window is not None:
            try:
                audio_window.lift()
                audio_window.focus_force()
            except Exception:
                pass

    def play_selected_scene(self, _event=None):
        selection = self.scene_list.curselection()
        if not selection or not self.stems:
            return
        index = int(selection[0])
        if index >= len(self.stems):
            return
        stem = self.stems[index]
        path = self.current_scene_playback_path(stem)
        if path is None:
            return
        # Só a cena escolhida é validada agora. Os vizinhos usam o caminho de
        # dublado esperado e são resolvidos quando ANTERIOR/PRÓXIMO for acionado.
        playlist = [OUTPUT_DIR / f"{scene_stem}.wav" for scene_stem in self.stems]
        playlist[index] = path
        self.audio_player.play_one(path, f"OUVIR CENA — {stem}", playlist=playlist, index=index, scene_key=stem, scene_keys=self.stems)

    def play_all_scenes(self):
        pairs = [(stem, self.current_scene_playback_path(stem)) for stem in self.stems]
        pairs = [(stem, path) for stem, path in pairs if path is not None]
        self.audio_player.play_all([path for _stem, path in pairs], "OUVIR TODOS — CENAS", scene_keys=[stem for stem, _path in pairs])

    def scene_display_name(self, stem: str) -> str:
        path = self.audio_by_stem.get(stem)
        return path.name if path is not None else f"{Path(stem).name}.wav"

    def _ordered_scene_stems(self) -> list[str]:
        """Retorna a lista na ordem solicitada, sem perder o conjunto original."""
        base = list(getattr(self, "default_stems", self.stems))
        mode = getattr(self, "scene_sort_mode", "default")
        if mode == "approved_first":
            rank = {"aprovada": 0, "pendente": 1, "rejeitada": 2}
        elif mode == "rejected_first":
            rank = {"rejeitada": 0, "pendente": 1, "aprovada": 2}
        elif mode == "decided_first":
            rank = {"aprovada": 0, "rejeitada": 1, "pendente": 2}
        else:
            return sorted(base, key=str.casefold)
        return sorted(base, key=lambda stem: (rank.get(self.state.get(stem, {}).get("status", "pendente"), 2), str(stem).casefold()))

    def _on_scene_sort_selected(self, _event=None) -> None:
        selected_label = self.scene_sort_var.get()
        self.scene_sort_mode = {
            "Aprovadas primeiro": "approved_first",
            "Rejeitadas primeiro": "rejected_first",
            "Aprovadas e rejeitadas primeiro": "decided_first",
        }.get(selected_label, "default")
        selected_stem = self.current_stem()
        self.refresh_scene_list(selected_stem)
        if selected_stem in self.stems:
            self.select_scene(self.stems.index(selected_stem))
        self.status_var.set(f"Organização aplicada: {selected_label}.")

    def refresh_scene_list(self, preserve_stem: str | None = None) -> None:
        if preserve_stem is None and getattr(self, "stems", None) and 0 <= getattr(self, "current_index", -1) < len(self.stems):
            preserve_stem = self.stems[self.current_index]
        self.stems = self._ordered_scene_stems()
        self.scene_count_var.set(f"DUBLADOS ({len(self.stems)} áudios)")
        self.scene_list.delete(0, END)
        dark = getattr(self, "theme", {}).get("root") != "#F5F6FA"
        for index, stem in enumerate(self.stems):
            status = self.state.get(stem, {}).get("status", "pendente")
            marker = {"aprovada": "[OK]", "rejeitada": "[REFAZER]"}.get(status, "[ ]")
            color = {"aprovada": "#60A5FA" if dark else "#0057B8", "rejeitada": "#F87171" if dark else "#C00000"}.get(status, "#F8FAFC" if dark else "#333333")
            self.scene_list.insert(END, f"{marker} {self.scene_display_name(stem)}")
            self.scene_list.itemconfig(index, foreground=color)
        if self.stems:
            if preserve_stem in self.stems:
                self.current_index = self.stems.index(preserve_stem)
            else:
                self.current_index = max(0, min(self.current_index, len(self.stems) - 1))
            self.scene_list.selection_set(self.current_index)
            self.scene_list.see(self.current_index)

    def show_error(self, text: str) -> None:
        self.status_var.set(text)
        if self.root.winfo_viewable():
            messagebox.showwarning("Revisão de dublagem", text)

    def on_scene_selected(self, _event=None) -> None:
        selection = self.scene_list.curselection()
        if selection:
            self.select_scene(selection[0])

    def select_scene(self, index: int) -> None:
        if not self.stems:
            return
        self.current_index = max(0, min(index, len(self.stems) - 1))
        self.scene_list.selection_clear(0, END)
        self.scene_list.selection_set(self.current_index)
        self.scene_list.see(self.current_index)
        self.update_details()

    def current_stem(self) -> str | None:
        if not self.stems:
            return None
        return self.stems[self.current_index]

    def current_output(self, stem: str) -> Path:
        return OUTPUT_DIR / f"{stem}.wav"

    def review_audio(self, stem: str) -> Path:
        output = self.current_output(stem)
        return output if output.exists() else self.audio_by_stem[stem]

    def update_details(self) -> None:
        stem = self.current_stem()
        if not stem:
            return
        text_file = self.text_by_stem[stem]
        try:
            text = text_file.read_text(encoding="utf-8-sig").strip()
        except UnicodeDecodeError:
            text = "[TXT não está em UTF-8]"

        original_file = self.original_text_by_stem.get(stem)
        if original_file:
            try:
                original_text = original_file.read_text(encoding="utf-8-sig").strip()
            except UnicodeDecodeError:
                original_text = "[TXT original não está em UTF-8]"
        else:
            original_text = f"[Texto original não encontrado em:\n{ORIGINAL_TEXT_DIR}]"
        transcribed_file = self.transcribed_translated_text_by_stem.get(stem)
        if transcribed_file:
            try:
                transcribed_text = transcribed_file.read_text(encoding="utf-8-sig").strip()
            except UnicodeDecodeError:
                transcribed_text = "[TXT transcrito/traduzido não está em UTF-8]"
        else:
            transcribed_text = f"[TXT transcrito e traduzido não encontrado em:\n{TRANSCRIBED_TRANSLATED_TEXT_DIR}]"
        record = self.state.get(stem, {})
        status = record.get("status", "pendente")
        self.scene_var.set(f"Cena: {stem}")
        self.meta_var.set(f"Status: {status} | Referência: {self.audio_by_stem[stem].name}")
        self.path_var.set(f"Inglês: {self.audio_by_stem[stem]} | Português: {self.current_output(stem)}")
        self.text_box.delete("1.0", END)
        self.text_box.insert("1.0", text)
        self.loaded_text = text
        self.original_text_box.configure(state="normal")
        self.original_text_box.delete("1.0", END)
        self.original_text_box.insert("1.0", original_text)
        self.set_reference_edit_state("original", False)
        self.transcribed_text_box.configure(state="normal")
        self.transcribed_text_box.delete("1.0", END)
        self.transcribed_text_box.insert("1.0", transcribed_text)
        self.set_reference_edit_state("transcribed", False)
        self.refresh_other_translation_text(stem)
        self.update_history(stem)
        self.previous_button.configure(state="normal" if self.current_index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.current_index < len(self.stems) - 1 else "disabled")
        self.set_action_state()

    def update_history(self, stem: str) -> None:
        record = self.state.get(stem, {})
        lines = [
            f"Cena: {stem}",
            f"Status: {record.get('status', 'pendente')}",
            f"Última ação: {record.get('updated_at', '-')}",
            f"Observação: {record.get('reason', '-')}",
            "",
            "Versões salvas:",
        ]
        versions = sorted((_revision_scene_dir(stem).glob(f"{_scene_basename(stem)}_v*.wav")) if _revision_scene_dir(stem).is_dir() else [])
        if versions:
            lines.extend(f"- {path.name}" for path in versions)
        else:
            lines.append("- nenhuma versão arquivada ainda")
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", END)
        self.history_box.tag_configure("observation_red", foreground="#C00000")
        self.history_box.insert(END, i18n.tr(f"Cena: {stem}\n"))
        self.history_box.insert(END, i18n.tr(f"Status: {record.get('status', 'pendente')}\n"))
        self.history_box.insert(END, i18n.tr(f"Última ação: {record.get('updated_at', '-')}\n"))
        self.history_box.insert(END, i18n.tr("Observação: "))
        self.history_box.insert(END, record.get("reason", "-") or "-", "observation_red")
        self.history_box.insert(END, i18n.tr("\n\nVersões salvas:\n"))
        if versions:
            self.history_box.insert(END, "\n".join(f"- {path.name}" for path in versions))
        else:
            self.history_box.insert(END, i18n.tr("- nenhuma versão arquivada ainda"))
        self.history_box.configure(state="disabled")
        history_mirror = "\n".join(lines)
        mirror_key = (stem, history_mirror)
        if mirror_key != getattr(self, "_last_history_mirror", None):
            self._last_history_mirror = mirror_key
            callback = getattr(self, "process_message_callback", None)
            if callable(callback):
                try:
                    callback(stem, history_mirror, "info", "HISTÓRICO DA CENA")
                except Exception:
                    pass

    def set_action_state(self) -> None:
        state = "disabled" if self.busy else "normal"
        for button in (self.open_button, self.save_text_button, self.approve_button, self.reject_button, self.regenerate_button, self.regenerate_other_audio_button, self.other_folder_button):
            button.configure(state=state)
        for button in getattr(self, "other_translation_folder_buttons", []):
            button.configure(state=state)
        self.other_translation_check.configure(state="disabled" if self.busy or not self.selected_other_translation_file else "normal")
        self.original_lock_button.configure(state=state)
        self.transcribed_lock_button.configure(state=state)
        self.original_save_button.configure(state="normal" if not self.busy and self.original_unlocked else "disabled")
        self.transcribed_save_button.configure(state="normal" if not self.busy and self.transcribed_unlocked else "disabled")

    def toggle_auto_open(self) -> None:
        enabled = self.auto_open_var.get() == "1"
        self.config["auto_open_after_generate"] = enabled
        save_json(CONFIG_FILE, self.config)
        self.status_var.set("Audacity será aberto após a redublagem." if enabled else "Abertura automática do Audacity desativada.")

    def toggle_r_request(self) -> None:
        enabled = self.request_r_var.get() == "1"
        self.config["ask_r_pronunciation"] = enabled
        save_json(CONFIG_FILE, self.config)
        self.status_var.set("Será perguntado o ajuste do R em cada redublagem." if enabled else "Pedido de alteração do R desativado.")

    def set_regeneration_progress_callback(self, callback=None) -> None:
        self.regen_progress_callback = callback

    def set_player_refresh_callback(self, callback=None) -> None:
        """Notifica players externos quando um WAV de redublagem foi substituído."""
        self.player_refresh_callback = callback

    def set_process_message_callback(self, callback=None) -> None:
        """Encaminha histórico e mensagens da Revisão ao painel Processos e Mensagens do Batch."""
        self.process_message_callback = callback

    def player_review_snapshot(self, stem: str | None = None) -> dict:
        """Retorna apenas os dados necessários para a área lateral do player."""
        current = stem or getattr(self, "current_stem", lambda: None)()
        snapshot = {
            "history": "",
            "regen": "",
            "clone_progress": 0.0,
            "dub_progress": 0.0,
            "phase": "Pronto para refazer a cena",
        }
        if current:
            try:
                snapshot["history"] = self.history_box.get("1.0", "end-1c")
            except Exception:
                pass
        try:
            snapshot["regen"] = self.regen_log_box.get("1.0", "end-1c")
        except Exception:
            pass
        for key, variable in (("clone_progress", getattr(self, "regen_clone_progress", None)), ("dub_progress", getattr(self, "regen_dub_progress", None))):
            try:
                snapshot[key] = float(variable.get()) if variable is not None else 0.0
            except (AttributeError, TypeError, ValueError):
                snapshot[key] = 0.0
        try:
            snapshot["phase"] = str(self.regen_phase_var.get())
        except Exception:
            pass
        return snapshot

    def set_fixed_r_pronunciation_provider(self, provider=None) -> None:
        self.fixed_r_pronunciation_provider = provider

    def _fixed_r_pronunciation(self) -> str:
        provider = getattr(self, "fixed_r_pronunciation_provider", None)
        if callable(provider):
            try:
                value = str(provider() or "unchanged").casefold()
                if value in {mode_id for _label, mode_id in R_PRONUNCIATION_CHOICES}:
                    return value
            except Exception:
                pass
        return "unchanged"

    def _notify_regen_progress(self, clone: float, dub: float, phase: str, done: bool = False, success: bool = False) -> None:
        callback = getattr(self, "regen_progress_callback", None)
        if not callable(callback):
            return
        try:
            callback(self.regen_stem, float(clone), float(dub), str(phase), bool(done), bool(success))
        except Exception:
            pass

    def _r_mode_label(self, mode_id: str) -> str:
        return next((label for label, candidate in R_PRONUNCIATION_CHOICES if candidate == mode_id), R_PRONUNCIATION_CHOICES[0][0])

    def _choose_r_override(self, dialog_parent=None) -> str | None:
        parent = dialog_parent if dialog_parent is not None else self.root
        try:
            if parent is None or not parent.winfo_exists():
                parent = self.root
        except Exception:
            parent = self.root
        if self.request_r_var.get() != "1":
            return None
        if not messagebox.askyesno(
            i18n.tr("Alterar pronúncia do R"),
            i18n.tr("Deseja alterar a pronúncia do R nesta redublagem?"),
            parent=parent,
        ):
            return None
        selected = {"value": None}
        window = Toplevel(parent)
        window.title(i18n.tr("Escolha a pronúncia do R para esta redublagem"))
        window.transient(parent)
        window.resizable(False, False)
        window.grab_set()
        theme = getattr(self, "theme", {}) or {}
        surface = theme.get("surface", "#FFFFFF")
        text_color = theme.get("text", "#1F2937")
        input_bg = theme.get("input", surface)
        input_fg = theme.get("input_text", text_color)
        select_bg = theme.get("select", "#DBEAFE")
        window.option_add("*TCombobox*Listbox.background", input_bg)
        window.option_add("*TCombobox*Listbox.foreground", input_fg)
        window.option_add("*TCombobox*Listbox.selectBackground", select_bg)
        window.option_add("*TCombobox*Listbox.selectForeground", input_fg)
        window.configure(bg=surface)
        Label(window, text=i18n.tr("Escolha a pronúncia do R para esta redublagem"), bg=surface, fg=text_color, font=("Segoe UI", 10, "bold"), padx=14, pady=12).pack(anchor="w")
        style = ttk.Style(window)
        style.configure("PronunciationR.TCombobox", fieldbackground=input_bg, background=input_bg, foreground=input_fg)
        style.map("PronunciationR.TCombobox", fieldbackground=[("readonly", input_bg)], foreground=[("readonly", input_fg)])
        combo = ttk.Combobox(window, state="readonly", values=[i18n.tr(label) for label, _mode_id in R_PRONUNCIATION_CHOICES], width=28, style="PronunciationR.TCombobox")
        combo.pack(fill="x", padx=14, pady=(0, 12))
        combo.current(0)
        buttons = Frame(window, bg=surface)
        buttons.pack(fill="x", padx=14, pady=(0, 12))
        def confirm():
            rendered = combo.get()
            source = i18n.source_text(rendered)
            selected["value"] = next((mode_id for label, mode_id in R_PRONUNCIATION_CHOICES if label == source), "unchanged")
            window.destroy()
        def cancel():
            window.destroy()
        confirm_button = Button(buttons, text="OK", command=confirm, relief="flat", padx=12, pady=4, cursor="hand2")
        apply_button_style(confirm_button, theme, "primary")
        confirm_button.pack(side="left")
        cancel_button = Button(buttons, text="CANCELAR", command=cancel, relief="flat", padx=12, pady=4, cursor="hand2")
        apply_button_style(cancel_button, theme, "secondary")
        cancel_button.pack(side="right")
        window.protocol("WM_DELETE_WINDOW", cancel)
        try:
            window.update_idletasks()
            screen_width = int(window.winfo_screenwidth())
            screen_height = int(window.winfo_screenheight())
            dialog_width = int(window.winfo_reqwidth())
            dialog_height = int(window.winfo_reqheight())
            position_x = max(0, (screen_width - dialog_width) // 2)
            position_y = max(0, (screen_height - dialog_height) // 2)
            window.geometry(f"+{position_x}+{position_y}")
            window.lift()
            window.focus_force()
        except Exception:
            pass
        window.wait_window()
        try:
            parent.lift()
            parent.focus_force()
        except Exception:
            pass
        return selected["value"]

    def _redub_with_r_request(self, dialog_parent=None) -> None:
        if self.busy:
            return
        self.regen_r_override = self._choose_r_override(dialog_parent)
        self.regenerate_scene()

    def _redub_other_with_r_request(self, dialog_parent=None) -> None:
        if self.busy:
            return
        self.regen_r_override = self._choose_r_override(dialog_parent)
        self.regenerate_with_other_audio()

    def _original_reference_audio_files(self) -> list[Path]:
        """Retorna somente os WAVs atuais, respeitando suas subpastas relativas."""
        return sorted({path.resolve() for path in scene_audio_files().values()}, key=lambda path: str(path).casefold())

    def _other_audio_display_name(self, path: Path) -> str:
        try:
            return str(path.relative_to(AUDIO_DIR))
        except ValueError:
            return path.name

    def _other_audio_index(self) -> int | None:
        if self.other_audio_list is None:
            return None
        selection = self.other_audio_list.curselection()
        if not selection:
            return None
        index = int(selection[0])
        return index if 0 <= index < len(self.other_audio_paths) else None

    def _update_other_audio_selection(self, _event=None) -> None:
        index = self._other_audio_index()
        if index is None:
            return
        path = self.other_audio_paths[index]
        if self.other_audio_path_var is not None:
            self.other_audio_path_var.set(str(path))
        if self.other_audio_hint_var is not None:
            self.other_audio_hint_var.set(i18n.tr(f"Selecionado: {path.name}. Clique em OUVIR CENA para escutar ou em REDUBLAR COM ESSE ÁUDIO para confirmar."))

    def _play_selected_other_audio(self, _event=None) -> None:
        index = self._other_audio_index()
        if index is None:
            messagebox.showinfo("Áudio de referência", "Selecione um áudio na lista primeiro.", parent=self.other_audio_window or self.root)
            return
        path = self.other_audio_paths[index]
        if not path.is_file():
            messagebox.showwarning("Áudio de referência", f"O arquivo não existe mais:\n{path}", parent=self.other_audio_window or self.root)
            return
        self.audio_player.play_one(path, f"OUVIR CENA — {path.stem}", playlist=self.other_audio_paths, index=index)

    def _choose_external_other_audio(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.other_audio_window or self.root,
            title=i18n.tr("Escolher áudio neste computador"),
            initialdir=str(AUDIO_DIR if AUDIO_DIR.is_dir() else ROOT),
            filetypes=[("Áudios", "*.wav *.wave *.waw *.mp3 *.ogg *.flac *.m4a *.aac"), ("Todos os arquivos", "*.*")],
        )
        if not selected:
            return
        path = Path(selected).expanduser().resolve()
        if not path.is_file():
            return
        if path not in self.other_audio_paths:
            self.other_audio_paths.append(path)
            self.other_audio_paths.sort(key=lambda item: str(item).casefold())
            self.other_audio_list.delete(0, END)
            for candidate in self.other_audio_paths:
                self.other_audio_list.insert(END, self._other_audio_display_name(candidate))
        index = self.other_audio_paths.index(path)
        self.other_audio_list.selection_clear(0, END)
        self.other_audio_list.selection_set(index)
        self.other_audio_list.see(index)
        self._update_other_audio_selection()

    def _confirm_other_audio(self) -> None:
        index = self._other_audio_index()
        if index is None:
            messagebox.showinfo("Áudio de referência", "Selecione um áudio na lista ou use ESCOLHER NESTE COMPUTADOR.", parent=self.other_audio_window or self.root)
            return
        path = self.other_audio_paths[index]
        if not path.is_file():
            messagebox.showwarning("Áudio de referência", f"O arquivo selecionado não existe mais:\n{path}", parent=self.other_audio_window or self.root)
            return
        self.alternate_reference_audio = path
        self._close_other_audio_window(clear_r_override=False)
        self.regenerate_scene()

    def _close_other_audio_window(self, clear_r_override: bool = True) -> None:
        if clear_r_override:
            self.regen_r_override = None
        window = self.other_audio_window
        self.other_audio_window = None
        self.other_audio_list = None
        self.other_audio_path_var = None
        self.other_audio_hint_var = None
        self.other_audio_choose_button = None
        self.other_audio_listen_button = None
        self.other_audio_confirm_button = None
        self.other_audio_cancel_button = None
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass

    def _apply_other_audio_window_theme(self, theme) -> None:
        window = self.other_audio_window
        if window is None:
            return
        try:
            if not window.winfo_exists():
                return
            surface = theme.get("surface", "#FFFFFF")
            input_bg = theme.get("input", surface)
            text = theme.get("text", "#1F2937")
            input_fg = theme.get("input_text", text)
            window.configure(bg=surface)
            for child in window.winfo_children():
                if child.winfo_class() in {"Label", "Frame"}:
                    try:
                        child.configure(bg=surface)
                    except Exception:
                        pass
            if self.other_audio_list is not None:
                self.other_audio_list.configure(bg=input_bg, fg=input_fg, selectbackground=theme.get("select", "#DBEAFE"), selectforeground=input_fg)
            if self.other_audio_path_var is not None:
                for child in window.winfo_children():
                    if child.winfo_class() == "Entry":
                        child.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg, readonlybackground=input_bg)
            for widget, role in (
                (self.other_audio_choose_button, "secondary"),
                (self.other_audio_listen_button, "teal"),
                (self.other_audio_confirm_button, "success"),
                (self.other_audio_cancel_button, "danger"),
            ):
                if widget is not None:
                    apply_button_style(widget, theme, role)
        except Exception:
            pass

    def _open_other_audio_window(self) -> None:
        if self.other_audio_window is not None:
            try:
                if self.other_audio_window.winfo_exists():
                    self.other_audio_window.deiconify()
                    self.other_audio_window.lift()
                    self.other_audio_window.focus_force()
                    return
            except Exception:
                pass
        if not self.other_audio_paths:
            messagebox.showinfo("Áudio de referência", "Nenhum áudio foi encontrado na pasta WAV ORIGINAIS. Use ESCOLHER NESTE COMPUTADOR para selecionar um arquivo externo.", parent=self.root)
        window = Toplevel(self.root)
        self.other_audio_window = window
        window.title(i18n.tr("Escolher áudio para REDUBLAR COM OUTRO ÁUDIO"))
        window.geometry("760x560")
        window.minsize(600, 460)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self._close_other_audio_window)
        theme = getattr(self, "theme", {})
        surface = theme.get("surface", "#FFFFFF")
        input_bg = theme.get("input", surface)
        text = theme.get("text", "#1F2937")
        input_fg = theme.get("input_text", text)
        muted = theme.get("muted", "#64748B")
        window.configure(bg=surface)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(2, weight=1)
        Label(window, text=i18n.tr("ÁUDIOS ORIGINAIS — WAV ORIGINAIS"), bg=surface, fg=text, font=("Segoe UI", 12, "bold"), anchor="w").grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 3))
        Label(window, text=i18n.tr("Clique em um áudio para selecioná-lo. Use OUVIR CENA para escutar e confirme somente depois."), bg=surface, fg=muted, justify="left", anchor="w", wraplength=720).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 9))
        list_frame = Frame(window, bg=surface)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.other_audio_list = Listbox(list_frame, exportselection=False, activestyle="none", bg=input_bg, fg=input_fg, selectbackground=theme.get("select", "#DBEAFE"), selectforeground=input_fg, font=("Segoe UI", 10), borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.other_audio_list.yview)
        self.other_audio_list.configure(yscrollcommand=scrollbar.set)
        self.other_audio_list.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        if self.other_audio_paths:
            for path in self.other_audio_paths:
                self.other_audio_list.insert(END, self._other_audio_display_name(path))
        else:
            self.other_audio_list.insert(END, i18n.tr("Nenhum WAV original encontrado — use ESCOLHER NESTE COMPUTADOR."))
        self.other_audio_list.bind("<<ListboxSelect>>", self._update_other_audio_selection)
        self.other_audio_list.bind("<Double-Button-1>", self._play_selected_other_audio)
        self.other_audio_list.bind("<MouseWheel>", lambda event: self.other_audio_list.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units"))
        self.other_audio_list.bind("<Button-4>", lambda _event: self.other_audio_list.yview_scroll(-1, "units"))
        self.other_audio_list.bind("<Button-5>", lambda _event: self.other_audio_list.yview_scroll(1, "units"))
        self.other_audio_path_var = StringVar(value=i18n.tr("Nenhum áudio selecionado"))
        Entry(window, textvariable=self.other_audio_path_var, state="readonly", readonlybackground=input_bg, fg=input_fg, relief="flat", font=("Segoe UI", 8)).grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 3))
        self.other_audio_hint_var = StringVar(value=i18n.tr("Selecione um áudio da lista ou escolha um arquivo neste computador."))
        Label(window, textvariable=self.other_audio_hint_var, bg=surface, fg=muted, justify="left", anchor="w", wraplength=720).grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 8))
        actions = Frame(window, bg=surface)
        actions.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 14))
        self.other_audio_choose_button = Button(actions, text=i18n.tr("ESCOLHER NESTE COMPUTADOR"), command=self._choose_external_other_audio, relief="flat", padx=9, pady=5, cursor="hand2")
        apply_button_style(self.other_audio_choose_button, theme, "secondary")
        self.other_audio_choose_button.pack(side="left")
        self.other_audio_listen_button = Button(actions, text=i18n.tr("OUVIR CENA"), command=self._play_selected_other_audio, relief="flat", padx=10, pady=5, cursor="hand2")
        apply_button_style(self.other_audio_listen_button, theme, "teal")
        self.other_audio_listen_button.pack(side="left", padx=(7, 0))
        self.other_audio_confirm_button = Button(actions, text=i18n.tr("REDUBLAR COM ESSE ÁUDIO"), command=self._confirm_other_audio, relief="flat", padx=10, pady=5, cursor="hand2")
        apply_button_style(self.other_audio_confirm_button, theme, "success")
        self.other_audio_confirm_button.pack(side="left", padx=(7, 0))
        self.other_audio_cancel_button = Button(actions, text=i18n.tr("CANCELAR"), command=self._close_other_audio_window, relief="flat", padx=10, pady=5, cursor="hand2")
        apply_button_style(self.other_audio_cancel_button, theme, "danger")
        self.other_audio_cancel_button.pack(side="right")
        if self.other_audio_paths:
            self.other_audio_list.selection_set(0)
            self.other_audio_list.see(0)
            self._update_other_audio_selection()

    def regenerate_with_other_audio(self) -> None:
        if self.busy:
            return
        self.other_audio_paths = self._original_reference_audio_files()
        self._open_other_audio_window()

    def load_scene_text_for_player(self, stem):
        key = str(stem or "")
        text_file = self.text_by_stem.get(key) if key else None
        if text_file is None and key:
            candidate = TEXT_DIR / f"{key}.txt"
            text_file = candidate if candidate.is_file() else None
        audio = self.audio_by_stem.get(key) if key else None
        title = f"Áudio: {audio.name if audio is not None else (Path(key).name if key else 'não selecionado')}"
        if text_file is None:
            return {"text": "", "path": None, "title": title}
        try:
            text = text_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            text = ""
        return {"text": text, "path": text_file, "title": title}

    def save_scene_text_from_player(self, stem, text):
        key = str(stem or "")
        new_text = str(text or "").strip()
        if not key:
            return False, "Nenhuma cena selecionada."
        if not new_text:
            return False, "Digite algum texto antes de salvar a alteração."
        text_file = self.text_by_stem.get(key) or (TEXT_DIR / f"{key}.txt")
        try:
            old_text = text_file.read_text(encoding="utf-8-sig") if text_file.is_file() else ""
            if old_text.strip() != new_text and old_text:
                text_version = next_text_version(key)
                backup = _revision_scene_dir(key) / f"{_scene_basename(key)}_texto_v{text_version:02d}.txt"
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_text(old_text, encoding="utf-8")
            text_file.parent.mkdir(parents=True, exist_ok=True)
            text_file.write_text(new_text + "\n", encoding="utf-8")
            self.text_by_stem[key] = text_file
            current = getattr(self, "current_stem", lambda: None)()
            if key == current and hasattr(self, "text_box"):
                self.text_box.delete("1.0", "end")
                self.text_box.insert("1.0", new_text)
                self.loaded_text = new_text
            self._log_central(f"Texto em português salvo pela janela OUVIR CENA: {text_file}", "ok")
            self.update_history(key)
            return True, f"Texto salvo em {text_file.name}."
        except Exception as exc:
            self._log_central(f"ERRO ao salvar texto pela janela OUVIR CENA: {exc}", "error")
            return False, f"Não foi possível atualizar o TXT: {exc}"

    def save_text_changes(self) -> bool:
        stem = self.current_stem()
        if not stem:
            return False
        new_text = self.text_box.get("1.0", "end-1c").strip()
        if not new_text:
            messagebox.showwarning("Texto vazio", "Digite algum texto antes de salvar a alteração.", parent=self.root)
            return False
        success, message = self.save_scene_text_from_player(stem, new_text)
        if not success:
            messagebox.showerror("Salvar alteração", message, parent=self.root)
            return False
        text_file = self.text_by_stem[stem]
        self.loaded_text = new_text
        self.status_var.set(f"Texto salvo em {text_file.name}")
        return True

    def text_has_unsaved_changes(self) -> bool:
        return self.text_box.get("1.0", "end-1c").strip() != self.loaded_text.strip()

    def update_record(self, stem: str, status: str, reason: str = "") -> None:
        record = self.state.setdefault(stem, {})
        record.update({"status": status, "reason": reason, "updated_at": now_text()})
        save_json(STATE_FILE, self.state)
        self.refresh_scene_list()
        self.select_scene(self.current_index)

    def open_current_pair(self) -> None:
        stem = self.current_stem()
        if not stem:
            return
        try:
            message = open_audio_pair(
                self.audio_by_stem[stem],
                self.current_output(stem),
                stem,
                self.config,
            )
            self.status_var.set(message)
            self._log_central(f"Audacity aberto para a cena {stem}: {message}", "ok")
        except Exception as exc:
            self._log_central(f"Falha ao abrir Audacity para {stem}: {exc}", "error")
            messagebox.showerror("Audacity", str(exc))
            self.status_var.set("Falha ao abrir o par de áudios")

    def make_folder_button(self, parent, text: str, path: Path, color: str):
        button = Button(parent, text=text, command=lambda: self.open_folder(path, text), bg=color, fg="white", activebackground=color, activeforeground="white", relief="flat", padx=9, pady=4, cursor="hand2")
        apply_button_style(button, getattr(self, "theme", {}))
        return button

    def open_folder(self, path: Path, label: str) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            self.status_var.set(f"Pasta aberta: {label}")
        except Exception as exc:
            messagebox.showerror("Abrir pasta", f"Não foi possível abrir {label}:\n{exc}", parent=self.root)

    def open_project_folder(self) -> None:
        self.open_folder(ROOT, "PROJETO")

    def approve_scene(self) -> None:
        stem = self.current_stem()
        if stem:
            self.update_record(stem, "aprovada")
            self.status_var.set(f"Aprovada: {stem}")
            self._log_central(f"Cena aprovada: {stem}", "ok")

    def reject_scene(self, dialog_parent=None) -> None:
        stem = self.current_stem()
        if not stem:
            return
        parent = dialog_parent if dialog_parent is not None and dialog_parent.winfo_exists() else self.root
        reason = simpledialog.askstring(i18n.tr("Rejeitar cena"), i18n.tr("Motivo opcional:"), parent=parent) or ""
        self.update_record(stem, "rejeitada", reason)
        self.status_var.set(f"Marcada para refazer: {stem}")
        self._log_central(f"Cena rejeitada: {stem}" + (f" — Motivo: {reason}" if reason else ""), "info")
        if dialog_parent is not None:
            try:
                dialog_parent.lift()
                dialog_parent.focus_force()
            except Exception:
                pass

    def previous_scene(self) -> None:
        self.select_scene(self.current_index - 1)

    def next_scene(self) -> None:
        self.select_scene(self.current_index + 1)

    def regenerate_scene(self) -> None:
        if self.busy:
            return
        stem = self.current_stem()
        if not stem:
            return
        pending_r_mode = self.regen_r_override
        self.regen_r_override = None
        valid_r_modes = {mode_id for _label, mode_id in R_PRONUNCIATION_CHOICES}
        r_mode = pending_r_mode if pending_r_mode in valid_r_modes else self._fixed_r_pronunciation()
        use_other = self.use_other_translation_var.get() == "1" and bool(self.selected_other_translation_file)
        reference_audio = getattr(self, "alternate_reference_audio", None) or self.audio_by_stem[stem]
        self.alternate_reference_audio = None
        if not use_other and self.text_has_unsaved_changes():
            answer = messagebox.askyesno(
                "Texto não salvo",
                "O texto foi alterado, mas ainda não foi salvo no TXT.\n\nSalvar agora e continuar com a regeneração?",
                parent=self.root,
            )
            if not answer or not self.save_text_changes():
                return

        source_label = self.selected_other_translation_file.name if use_other else f"{stem}.txt em TXT TEXTO PORTUGUES"
        current = self.current_output(stem)
        destination_note = "A versão atual será preservada em revisoes antes da substituição." if current.exists() else "A nova versão será criada em dublado; não há dublado anterior para arquivar."
        r_label = i18n.tr(self._r_mode_label(r_mode))
        if not messagebox.askyesno(
            "Refazer cena",
            f"Regenerar {stem} usando a referência:\n{reference_audio.name}\n\ne o texto:\n{source_label}\n\n{i18n.tr('A pronúncia do R desta vez será: ')}{r_label}\n\n{destination_note}",
            parent=self.root,
        ):
            return

        try:
            if use_other:
                text = self.selected_other_translation_text.strip()
            else:
                text = self.text_by_stem[stem].read_text(encoding="utf-8-sig").strip()
        except Exception as exc:
            messagebox.showerror("TXT", f"Não foi possível ler o texto:\n{exc}")
            return
        if not text:
            messagebox.showwarning("TXT vazio", f"O arquivo {stem}.txt está vazio.")
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        target = current
        self.busy = True
        self.regen_started_at = time.monotonic()
        self.regen_stem = stem
        self.regen_clone_progress.set(0.0)
        self.regen_dub_progress.set(0.0)
        self.regen_elapsed_var.set("Refazer decorrido: 00:00:00")
        self.regen_eta_var.set("Restante: calculando...")
        self.regen_phase_var.set("CLONANDO REFERÊNCIA...")
        self.regen_log_box.configure(state="normal")
        self.regen_log_box.delete("1.0", END)
        self.regen_log_box.configure(state="disabled")
        self.append_regen_log(f"[1/2] Referência: {reference_audio.name}")
        self.append_regen_log(f"[2/2] Texto: {source_label}")
        self.append_regen_log(f"Pronúncia do R nesta execução: {r_label}")
        self.append_regen_log("Iniciando CLONANDO REFERÊNCIA e DUBLANDO CENA...")
        self.set_action_state()
        self.status_var.set(f"Regenerando {stem}...")
        self.update_regen_clock()
        thread = threading.Thread(target=self._run_generation, args=(stem, text, target, current, reference_audio, r_mode), daemon=True)
        thread.start()

    def _run_generation(self, stem: str, text: str, target: Path, current: Path, reference_audio: Path, r_mode: str = "unchanged") -> None:
        infer_prefix = find_omnivoice_command()
        if not infer_prefix:
            self.root.after(0, lambda: self._generation_failed(stem, "Não encontrei o OmniVoice. Instale o pacote ou defina OMNIVOICE_INFER."))
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_target = target.with_name(f".{target.stem}.__dublaskizon_tmp_{os.getpid()}_{threading.get_ident()}.wav")
        backup_path = None
        command = [
            *infer_prefix,
            "--model",
            str(self.config["model"]),
            "--text",
            apply_r_pronunciation(text, r_mode),
            "--language",
            str(self.config["language"]),
            "--instruct",
            str(self.config["instruct"]),
            "--ref_audio",
            str(reference_audio),
            "--output",
            str(temporary_target),
        ]
        try:
            result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **hidden_process_kwargs())
            if result.returncode != 0 or not temporary_target.exists():
                details = (result.stdout or "").strip()
                suffix = f"\n\n{details[-2000:]}" if details else ""
                raise RuntimeError(f"OmniVoice terminou com código {result.returncode}.{suffix}")
            if current.exists():
                revision_dir = _revision_scene_dir(stem)
                revision_dir.mkdir(parents=True, exist_ok=True)
                backup_path = revision_dir / f"{_scene_basename(stem)}_v{next_version(stem):02d}.wav"
                shutil.copy2(current, backup_path)
            os.replace(temporary_target, target)
            self.root.after(0, lambda: self._generation_done(stem, target, backup_path))
        except Exception as exc:
            try:
                temporary_target.unlink(missing_ok=True)
            except OSError:
                pass
            if backup_path is not None:
                try:
                    backup_path.unlink(missing_ok=True)
                except OSError:
                    pass
            self.root.after(0, lambda: self._generation_failed(stem, str(exc)))

    def _generation_done(self, stem: str, target: Path, backup_path: Path | None = None) -> None:
        self.busy = False
        self.append_regen_log(f"CONCLUÍDO: novo áudio salvo em dublado/{target.relative_to(OUTPUT_DIR) if target.is_relative_to(OUTPUT_DIR) else target.name}")
        if backup_path is not None:
            self.append_regen_log(f"VERSÃO ANTERIOR PRESERVADA: {backup_path.relative_to(REVISIONS_DIR) if backup_path.is_relative_to(REVISIONS_DIR) else backup_path.name}")
        self.finish_regen_clock(True)
        record_text = f"Novo dublado salvo em {target.name}; arquivo atual substituído."
        if backup_path is not None:
            record_text += f" Versão anterior preservada em {backup_path.name}."
        self.update_record(stem, "pendente", record_text)
        self.status_var.set(f"Novo áudio salvo em dublado: {target.name}")
        try:
            self.audio_player.refresh_current_scene(stem)
        except Exception:
            pass
        callback = getattr(self, "player_refresh_callback", None)
        if callable(callback):
            try:
                callback(stem)
            except Exception:
                pass
        self.set_action_state()
        self.update_details()
        if bool(self.config.get("auto_open_after_generate", True)):
            try:
                open_audio_pair(self.audio_by_stem[stem], self.current_output(stem), stem, self.config)
            except Exception as exc:
                self.status_var.set(f"Gerada, mas não abriu no Audacity: {exc}")

    def _generation_failed(self, stem: str, error: str) -> None:
        self.busy = False
        self.append_regen_log(f"ERRO: {error}")
        self.finish_regen_clock(False)
        self.set_action_state()
        self.status_var.set(f"Falha ao regenerar {stem}")
        messagebox.showerror("Regeneração", f"Não foi possível regenerar a cena.\n\n{error}", parent=self.root)


def main() -> int:
    if not TK_AVAILABLE:
        print("ERRO: Tkinter nao esta disponivel neste Python.")
        print(f"Detalhes: {TK_IMPORT_ERROR}")
        print("Instale uma distribuicao completa do Python para Windows e tente novamente.")
        return 2
    if not AUDIO_DIR.is_dir() or not TEXT_DIR.is_dir():
        print("Crie as subpastas WAV ORIGINAIS e TXT TEXTO PORTUGUES na raiz do projeto, um nivel acima de revisoes.")
        return 2
    root = Tk()
    try:
        ttk.Style(root).theme_use("clam")
    except Exception:
        pass
    ReviewApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
