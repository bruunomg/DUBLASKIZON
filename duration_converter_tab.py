"""Aba para igualar a duração dos áudios dublados à duração dos originais.

O módulo é autocontido e usa FFmpeg/FFprobe. Quando SoX está disponível, a
rama de arquivos maiores usa o mesmo efeito ``tempo`` do ajustador v10; caso
contrário, há fallback para o filtro ``atempo`` do FFmpeg.
"""

from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
import wave
from pathlib import Path
try:
    from .audio_player import AudioPlayerManager, reveal_in_file_manager
    from .ui_theme import apply_button_style, apply_button_style_to_tree, configure_ttk_button_styles, surface_color
except ImportError:
    from audio_player import AudioPlayerManager, reveal_in_file_manager
    from ui_theme import apply_button_style, apply_button_style_to_tree, configure_ttk_button_styles, surface_color

try:
    from tkinter import END, Menu, StringVar, Text, Toplevel, filedialog, messagebox, ttk
    import tkinter as tk
    from tkinter import Button, Canvas, Entry, Frame, Label, Listbox, Scrollbar
    TK_AVAILABLE = True
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


AUDIO_EXTENSIONS = {".wav", ".wave"}
INTERNAL_AUDIO_DIR_NAMES = {"_backup_omnivoice"}
DURATION_EQUAL_TOLERANCE = 0.02
TOOLS_DIR_NAME = "ferramentas_audio"
DEFAULT_OUTPUT_FOLDER_NAME = "AUDIOS com DURAÇAO CONVERTIDAS"
FFMPEG_WINDOWS_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
SOX_WINDOWS_URL = "https://sourceforge.net/projects/sox/files/sox/14.4.2/sox-14.4.2-win32.zip/download"
DEFAULT_THRESHOLD_DB = -27
DEFAULT_MIN_SILENCE_SECONDS = 0.01

FORMAT_CHOICES = {
    "WAV PCM 16-bit — 48 kHz — manter mono/estéreo do original (recomendado)": {"extension": ".wav", "codec": "pcm_s16le", "rate": "48000", "channels": None},
    "WAV PCM 16-bit — 48 kHz — mono (Unreal)": {"extension": ".wav", "codec": "pcm_s16le", "rate": "48000", "channels": "1"},
    "WAV PCM 16-bit — 48 kHz — estéreo (Unreal)": {"extension": ".wav", "codec": "pcm_s16le", "rate": "48000", "channels": "2"},
    "WAV PCM 24-bit — 48 kHz — mono": {"extension": ".wav", "codec": "pcm_s24le", "rate": "48000", "channels": "1"},
    "WAV PCM 32-bit — 48 kHz — estéreo": {"extension": ".wav", "codec": "pcm_s32le", "rate": "48000", "channels": "2"},
    "WAV PCM 16-bit — manter frequência/canais": {"extension": ".wav", "codec": "pcm_s16le", "rate": None, "channels": None},
    "AIFF PCM 16-bit — 48 kHz — estéreo": {"extension": ".aiff", "codec": "pcm_s16be", "rate": "48000", "channels": "2"},
    "FLAC — 48 kHz — estéreo": {"extension": ".flac", "codec": "flac", "rate": "48000", "channels": "2"},
    "MP3 — 320 kbps — 48 kHz — estéreo": {"extension": ".mp3", "codec": "libmp3lame", "rate": "48000", "channels": "2", "bitrate": "320k"},
    "MP3 — 192 kbps — 48 kHz — estéreo": {"extension": ".mp3", "codec": "libmp3lame", "rate": "48000", "channels": "2", "bitrate": "192k"},
    "OGG Vorbis — qualidade alta": {"extension": ".ogg", "codec": "libvorbis", "rate": "48000", "channels": "2", "quality": "6"},
}
DEFAULT_FORMAT = next(iter(FORMAT_CHOICES))
OUTPUT_MODE_CHOICES = ("Separar por duração", "Salvar tudo na mesma pasta")
SILENCE_HELP_TEXT = (
    "Ao ativar esta opção, os silêncios do início e do final dos áudios serão cortados "
    "antes do ajuste de duração. Atenção: essa ferramenta também pode remover uma pequena "
    "parte da fala no começo e no fim. Confira os áudios após a conversão."
)
TOOLS_HELP_TEXT = (
    "FFmpeg: converte e processa áudio e vídeo; é usado para gerar o formato de saída.\n\n"
    "FFprobe: consulta informações do arquivo, como duração, frequência e canais.\n\n"
    "FFplay: reproduz os áudios dentro do Dublaskizon.\n\n"
    "SoX: realiza operações de áudio, incluindo o ajuste de tempo usado em alguns áudios maiores."
)
DURATION_FOLDERS_HELP_TEXT = (
    "IGUAL: a pasta 'AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO' recebe os áudios cuja duração já era igual à do original; nenhum ajuste de duração foi necessário.\n\n"
    "MAIOR: a pasta 'AUDIO CONVERTIDO ..MAIOR.. DURAÇÃO' recebe os áudios dublados mais longos que o original; eles são comprimidos para ficar com a duração do original.\n\n"
    "MENOR: a pasta 'AUDIO CONVERTIDO ..MENOR.. DURAÇÃO' recebe os áudios dublados mais curtos que o original; apenas silêncio é acrescentado no final para completar o tempo faltante."
)


def update_download_progress(widget, description: str, downloaded: int, total: int) -> float:
    """Atualiza a barra sempre em modo determinístico e nunca reduz o valor."""
    try:
        current = float(widget.cget("value"))
    except Exception:
        current = 0.0
    label = str(description).casefold()
    # O FFmpeg costuma ser baixado primeiro; SoX, quando necessário, ocupa a
    # faixa final. Assim, a troca de arquivo também continua sempre crescente.
    if "sox" in label:
        base, span = 70.0, 29.0
    elif "ffmpeg" in label:
        base, span = 0.0, 70.0
    else:
        base, span = 0.0, 99.0
    if total and total > 0:
        candidate = base + span * min(1.0, max(0.0, downloaded / total))
    else:
        # Sem Content-Length, usa os bytes já recebidos para crescer devagar e
        # para em 99%; ao concluir, o evento download_complete leva a 100%.
        candidate = base + min(span - 0.5, max(0.0, downloaded / 1048576.0 * 0.5))
    value = min(99.0, max(current, candidate))
    try:
        widget.stop()
        widget.configure(mode="determinate", value=value)
    except Exception:
        pass
    return value


class HoverTooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, event=None):
        if self.window is not None:
            return
        try:
            self.window = Toplevel(self.widget)
            self.window.wm_overrideredirect(True)
            self.window.attributes("-topmost", True)
            mouse_x = int(getattr(event, "x_root", self.widget.winfo_rootx()))
            mouse_y = int(getattr(event, "y_root", self.widget.winfo_rooty()))
            Label(self.window, text=i18n.tr(self.text), justify="left", wraplength=430, bg="#FFFDE7", fg="#3F3F46", relief="solid", bd=1, padx=8, pady=6, font=("Segoe UI", 9)).pack()
            self.window.update_idletasks()
            tooltip_height = self.window.winfo_reqheight()
            x = max(4, mouse_x - 455)
            y = mouse_y - tooltip_height - 10
            if y < 4:
                y = mouse_y + 16
            self.window.geometry(f"+{x}+{y}")
        except Exception:
            self.window = None

    def hide(self, _event=None):
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None


def configure_project_root(project_root: Path) -> None:
    global PROJECT_ROOT
    PROJECT_ROOT = Path(project_root).expanduser().resolve()


PROJECT_ROOT = Path(os.environ.get("DUBLASKIZON_PROJECT_ROOT", Path(__file__).resolve().parent))


def is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def normalized_stem(path_or_name: str | Path) -> str:
    stem = Path(path_or_name).stem.casefold()
    stem = re.sub(r"(?:[_ .-]*(?:convertidos?|converted))+$", "", stem)
    stem = re.sub(r"(?:[_ .-]+(?:audio|dub|dublado))+$", "", stem)
    return stem.strip(" _.-")


def list_audio_files(folder: Path, converted_only: bool = False, exclude_converted: bool = False) -> list[Path]:
    if not folder.is_dir():
        return []
    folder_root = folder.expanduser().resolve()
    files = []
    for path in folder.rglob("*"):
        if not is_audio_file(path):
            continue
        try:
            relative = path.resolve().relative_to(folder_root)
        except ValueError:
            relative = path
        if any(part.casefold() in INTERNAL_AUDIO_DIR_NAMES for part in relative.parts[:-1]):
            continue
        files.append(path)
    marked = [path for path in files if "convert" in path.stem.casefold()]
    if converted_only:
        files = marked
    elif exclude_converted:
        files = [path for path in files if path not in marked]
    return sorted(files, key=lambda path: (path.name.casefold(), str(path).casefold()))


def relative_audio_key(path: Path, root_dir: Path | None = None) -> str:
    """Chave de pareamento com subpasta, normalizando apenas o nome do arquivo."""
    path = Path(path).expanduser().resolve()
    if root_dir is not None:
        try:
            relative = path.relative_to(Path(root_dir).expanduser().resolve()).with_suffix("")
            normalized_name = normalized_stem(relative.name)
            relative = relative.with_name(normalized_name)
            return relative.as_posix()
        except ValueError:
            pass
    return normalized_stem(path)



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


def portable_tool_roots(project_root: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    module_dir = Path(__file__).resolve().parent
    app_dir = Path(os.environ.get("DUBLASKIZON_APP_DIR", module_dir)).expanduser()
    if project_root is not None:
        project_root = Path(project_root).expanduser()
        roots.extend([project_root, project_root / TOOLS_DIR_NAME, project_root / "tools", project_root / "sox"])
    roots.extend([app_dir, app_dir / TOOLS_DIR_NAME, app_dir / "tools", app_dir / "sox", module_dir, module_dir / TOOLS_DIR_NAME, module_dir / "tools", module_dir / "sox"])
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = os.path.normcase(os.path.abspath(str(root)))
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def executable_path(name: str, project_root: Path | None = None) -> str | None:
    found = shutil.which(name) or shutil.which(f"{name}.exe")
    if found:
        return found
    executable_names = {name, f"{name}.exe"}
    for root in portable_tool_roots(project_root):
        for executable_name in executable_names:
            candidate = root / executable_name
            if candidate.is_file():
                return str(candidate)
        try:
            for candidate in root.rglob("*"):
                if candidate.is_file() and candidate.name.casefold() in {value.casefold() for value in executable_names}:
                    return str(candidate)
        except (OSError, PermissionError):
            continue
    return None


class DurationConverterApp:
    TITLE = "CONVERTER DURAÇÃO DOS ÁUDIOS DUBLADOS AO ORIGINAL"

    def __init__(self, root, embedded=True, project_root: Path | None = None, project_actions=None):
        if not TK_AVAILABLE:
            raise RuntimeError(f"Tkinter indisponível: {TK_IMPORT_ERROR}")
        self.root = root
        self.embedded = embedded
        self.project_actions = project_actions or {}
        self.central_log_callback = self.project_actions.get("central_log")
        self.project_root = Path(project_root or PROJECT_ROOT).expanduser().resolve()
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.dependency_thread: threading.Thread | None = None
        self.dependencies_running = False
        self.tool_alert_after_id = None
        self.tool_alert_until = 0.0
        self.tool_alert_on = False
        self.running = False
        self.cancel_event = threading.Event()
        self.original_files: list[Path] = []
        self.dubbed_files: list[Path] = []
        self.original_base_dir = self.project_root / "WAV ORIGINAIS"
        self.dubbed_base_dir = self.project_root / "dublado"
        self.panel_title_vars: dict[str, StringVar] = {}
        self.original_by_stem: dict[str, Path] = {}
        self.dubbed_by_stem: dict[str, Path] = {}
        self.theme = {"root": "#F5F6FA", "surface": "#FFFFFF", "text": "#1F2937", "muted": "#64748B", "input": "#FFFFFF", "input_text": "#1F2937", "select": "#DBEAFE"}
        self.original_dir_var = StringVar(value="Nenhuma pasta selecionada")
        self.dubbed_dir_var = StringVar(value="Nenhuma pasta selecionada")
        self.output_dir_var = StringVar(value=str(self.project_root / DEFAULT_OUTPUT_FOLDER_NAME))
        self.format_var = StringVar(value=DEFAULT_FORMAT)
        self.output_mode_var = StringVar(value=OUTPUT_MODE_CHOICES[0])
        self.silence_var = StringVar(value="0")
        self.preserve_channels_var = StringVar(value="1")
        self.forced_channels: int | None = None
        self.current_output_channels: int | None = None
        self.status_var = StringVar(value="Selecione as duas pastas e clique em CONVERTER AUDIOS.")
        self.audio_player = AudioPlayerManager(self.root, self.project_root, status_callback=lambda text: (self.status_var.set(text), self._log_central(text, "info")))
        self.count_var = StringVar(value="Originais: 0    Dublados: 0    Pares: 0")
        self.progress_var = StringVar(value="")
        self.download_status_var = StringVar(value="Ferramentas: não verificadas")
        self.conversion_progress_var = StringVar(value="Conversão: aguardando")
        self.build_ui()
        self.refresh_for_project()
        self.root.after(100, self.poll_messages)

    def apply_theme(self, theme):
        self.theme = theme
        root_bg = theme.get("root", "#F5F6FA")
        surface = theme.get("surface", "#FFFFFF")
        text = theme.get("text", "#1F2937")
        input_bg = theme.get("input", surface)
        input_fg = theme.get("input_text", text)
        select = theme.get("select", "#DBEAFE")
        try:
            style = ttk.Style(self.root)
            style.configure("TFrame", background=surface)
            style.configure("TLabel", background=surface, foreground=text)
            style.configure("TCheckbutton", background=surface, foreground=text)
            configure_ttk_button_styles(style, self.theme)
            style.configure("TCombobox", fieldbackground=input_bg, background=input_bg, foreground=input_fg)
            style.map("TCombobox", fieldbackground=[("readonly", input_bg)], foreground=[("readonly", input_fg)], selectbackground=[("readonly", select)], selectforeground=[("readonly", input_fg)])
            self.root.option_add("*TCombobox*Listbox.background", input_bg)
            self.root.option_add("*TCombobox*Listbox.foreground", input_fg)
            self.root.option_add("*TCombobox*Listbox.selectBackground", select)
            track_color = surface_color(self.theme, "progress_track", theme.get("border", "#CBD5E1"))
            download_color = surface_color(self.theme, "progress_download", "#F97316")
            conversion_color = surface_color(self.theme, "progress_conversion", "#DC2626")
            style.configure("Download.Horizontal.TProgressbar", troughcolor=track_color, background=download_color, lightcolor=download_color, darkcolor=download_color)
            style.configure("Conversion.Horizontal.TProgressbar", troughcolor=track_color, background=conversion_color, lightcolor=conversion_color, darkcolor=conversion_color)
            if hasattr(self, "download_progress"):
                self.download_progress.configure(style="Download.Horizontal.TProgressbar")
            if hasattr(self, "conversion_progress"):
                self.conversion_progress.configure(style="Conversion.Horizontal.TProgressbar")
        except Exception:
            pass

        def visit(widget):
            try:
                cls = widget.winfo_class()
                if cls in {"Frame", "TFrame"}:
                    if cls == "Frame":
                        widget.configure(bg=surface)
                elif cls in {"Label", "TLabel"}:
                    if cls == "Label":
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
        apply_button_style_to_tree(self.root, theme)
        if hasattr(self, "audio_player"):
            self.audio_player.apply_theme(theme)

    def build_ui(self):
        header = Frame(self.root, bg="#F5F6FA")
        header.pack(fill="x", padx=16, pady=(8, 3))
        Label(header, text=self.TITLE, bg="#F5F6FA", fg="#1F2937", font=("Segoe UI", 13, "bold")).pack(side="left")
        Label(header, text="  Ajuste para cutscenes com tempo exato", bg="#F5F6FA", fg="#64748B", font=("Segoe UI", 9)).pack(side="left")
        Label(self.root, textvariable=self.status_var, bg="#F5F6FA", fg="#64748B", anchor="w").pack(fill="x", padx=16, pady=(0, 6))

        folders = Frame(self.root, bg="#F5F6FA")
        folders.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        folders.grid_columnconfigure(0, weight=1)
        folders.grid_columnconfigure(1, weight=1)
        folders.grid_rowconfigure(0, weight=1)
        self.original_panel = self.make_audio_panel(folders, "ÁUDIOS ORIGINAIS", "original")
        self.original_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.dubbed_panel = self.make_audio_panel(folders, "ÁUDIOS DUBLADOS", "dubbed")
        self.dubbed_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        options = Frame(self.root, bg="#FFFFFF", bd=1, relief="solid")
        options.pack(fill="x", padx=16, pady=(0, 6))
        Label(options, text="Formato de saída", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(8, 2))
        self.format_combo = ttk.Combobox(options, textvariable=self.format_var, values=list(FORMAT_CHOICES), state="readonly", width=54)
        self.format_combo.grid(row=1, column=0, sticky="ew", padx=(10, 6), pady=(0, 8))
        self.format_combo.bind("<MouseWheel>", lambda _event: "break")
        Label(options, text="Saída dos resultados", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=6, pady=(8, 2))
        self.output_entry = ttk.Entry(options, textvariable=self.output_dir_var, width=48)
        self.output_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 8))
        output_buttons = Frame(options, bg="#FFFFFF")
        output_buttons.grid(row=1, column=2, padx=(0, 10), pady=(0, 8))
        Button(output_buttons, text="ESCOLHER", command=self.choose_output_folder, bg="#64748B", activebackground="#475569", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2").pack(side="left", padx=(0, 3))
        Button(output_buttons, text="ABRIR PASTA DE SAÍDA", command=self.open_output_folder, bg="#0F766E", activebackground="#115E59", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2").pack(side="left")
        Label(options, text="Organização da saída", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", padx=(10, 6), pady=(0, 8))
        self.output_mode_combo = ttk.Combobox(options, textvariable=self.output_mode_var, values=list(OUTPUT_MODE_CHOICES), state="readonly", width=38)
        self.output_mode_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=6, pady=(0, 8))
        self.output_mode_combo.bind("<MouseWheel>", lambda _event: "break")
        options.grid_columnconfigure(0, weight=1)
        options.grid_columnconfigure(1, weight=1)
        options.grid_columnconfigure(2, weight=0)

        actions = Frame(self.root, bg="#F5F6FA")
        actions.pack(fill="x", padx=16, pady=(0, 6))
        Button(actions, text="CARREGAR DA ABA REVISÃO", command=lambda: self.project_actions.get("load_converter_from_review", self.load_from_review)(), bg="#D97706", activebackground="#B45309", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2").pack(side="left", padx=(0, 6))
        Button(actions, text="CARREGAR DA CLONAGEM + DUBLAGEM", command=lambda: self.project_actions.get("load_converter_from_batch", self.load_from_batch)(), bg="#D97706", activebackground="#B45309", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2").pack(side="left", padx=6)
        self.dependencies_button = Button(actions, text="BAIXAR / PREPARAR FERRAMENTAS", command=self.start_dependency_setup, bg="#0F766E", activebackground="#115E59", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=6, cursor="hand2")
        self.dependencies_button.pack(side="left", padx=6)
        self.tools_help_button = Button(actions, text="?", command=self.show_tools_help, bg="#64748B", activebackground="#475569", fg="white", relief="flat", font=("Segoe UI", 9, "bold"), width=2, padx=0, pady=5, cursor="hand2")
        self.tools_help_button.pack(side="left", padx=(0, 6))
        HoverTooltip(self.tools_help_button, TOOLS_HELP_TEXT)
        self.convert_button = Button(actions, text="CONVERTER AUDIOS", command=self.start_conversion, bg="#DC2626", activebackground="#B91C1C", fg="white", relief="flat", font=("Segoe UI", 10, "bold"), padx=18, pady=7, cursor="hand2")
        self.convert_button.pack(side="right")
        self.duration_help_button = Button(actions, text="?", command=lambda: None, bg="#64748B", activebackground="#475569", fg="white", relief="flat", font=("Segoe UI", 9, "bold"), width=2, padx=0, pady=5, cursor="hand2")
        self.duration_help_button.pack(side="right", padx=(0, 6))
        self.duration_help_tooltip = HoverTooltip(self.duration_help_button, DURATION_FOLDERS_HELP_TEXT)
        self.preserve_channels_check = ttk.Checkbutton(actions, text="Manter mono/estéreo conforme cada áudio original (recomendado)", variable=self.preserve_channels_var, onvalue="1", offvalue="0")
        self.preserve_channels_check.pack(side="right", padx=(8, 10))
        # Aproximadamente 1 cm entre a opção de silêncio e o botão principal.
        silence_controls = Frame(actions, bg="#F5F6FA")
        silence_controls.pack(side="right", padx=(0, 38))
        self.silence_check = ttk.Checkbutton(silence_controls, text="Remover silêncio inicial/final", variable=self.silence_var, onvalue="1", offvalue="0")
        self.silence_check.pack(side="left", padx=(0, 6))
        self.silence_help_button = Button(silence_controls, text="?", command=lambda: None, bg="#64748B", activebackground="#475569", fg="white", relief="flat", font=("Segoe UI", 9, "bold"), width=2, padx=0, pady=5, cursor="hand2")
        self.silence_help_button.pack(side="left")
        HoverTooltip(self.silence_help_button, SILENCE_HELP_TEXT)

        Label(self.root, textvariable=self.count_var, bg="#F5F6FA", fg="#475569", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=16)
        Label(self.root, textvariable=self.progress_var, bg="#F5F6FA", fg="#64748B", anchor="w").pack(fill="x", padx=16, pady=(2, 2))
        Label(self.root, textvariable=self.conversion_progress_var, bg="#F5F6FA", fg="#64748B", anchor="w", font=("Segoe UI", 8, "bold")).pack(fill="x", padx=16, pady=(0, 2))
        self.conversion_progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100, value=0, style="Conversion.Horizontal.TProgressbar")
        self.conversion_progress.pack(fill="x", padx=16, pady=(0, 3))
        Label(self.root, textvariable=self.download_status_var, bg="#F5F6FA", fg="#64748B", anchor="w", font=("Segoe UI", 8, "bold")).pack(fill="x", padx=16, pady=(0, 2))
        self.download_progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100, value=0, style="Download.Horizontal.TProgressbar")
        self.download_progress.pack(fill="x", padx=16, pady=(0, 7))
        self.log_box = Text(self.root, height=7, wrap="word", state="disabled", font=("Consolas", 9), background="#111827", foreground="#E5E7EB")
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
            (DEFAULT_OUTPUT_FOLDER_NAME, self.project_root / DEFAULT_OUTPUT_FOLDER_NAME, "highlight"),
        )

    def refresh_folder_buttons(self):
        if not hasattr(self, "folder_bar"):
            return
        for child in self.folder_bar.winfo_children():
            child.destroy()
        for label, path, role in self.folder_button_definitions():
            self.make_folder_button(self.folder_bar, label, path, role).pack(side="left", padx=3)

    def make_folder_button(self, parent, text: str, path: Path, role: str):
        button = Button(parent, text=text, command=lambda target=path, name=text: self.open_folder(target, name), relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=4, cursor="hand2")
        apply_button_style(button, getattr(self, "theme", {}), role)
        return button

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

    def make_audio_panel(self, parent, title: str, kind: str):
        panel = Frame(parent, bg="#FFFFFF", bd=1, relief="solid")
        title_var = StringVar(value=f"{title} (0)")
        self.panel_title_vars[kind] = title_var
        Label(panel, textvariable=title_var, bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=8, pady=(7, 2))
        directory_var = self.original_dir_var if kind == "original" else self.dubbed_dir_var
        Entry(panel, textvariable=directory_var, state="readonly", readonlybackground="#FFFFFF", fg="#64748B", relief="flat", font=("Segoe UI", 8)).pack(fill="x", padx=8, pady=(0, 4))
        list_frame = Frame(panel, bg="#FFFFFF")
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 5))
        listbox = Listbox(list_frame, selectmode="extended", activestyle="none", height=10, font=("Segoe UI", 9), bg="#FFFFFF", fg="#1F2937", selectbackground="#DBEAFE", selectforeground="#1F2937")
        scrollbar = Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        setattr(self, f"{kind}_listbox", listbox)
        Button(panel, text="ABRIR PASTA", command=lambda: self.choose_audio_folder(kind), bg="#2563EB", activebackground="#1D4ED8", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=4, cursor="hand2").pack(side="left", padx=(8, 4), pady=(0, 8))
        Button(panel, text="ADICIONAR ÁUDIOS", command=lambda: self.add_audio_files(kind), bg="#64748B", activebackground="#475569", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=4, cursor="hand2").pack(side="left", padx=4, pady=(0, 8))
        Button(panel, text="LIMPAR", command=lambda: self.clear_audio_files(kind), bg="#CBD5E1", activebackground="#94A3B8", fg="#1F2937", relief="flat", padx=8, pady=4, cursor="hand2").pack(side="right", padx=(4, 8), pady=(0, 8))
        listbox.bind("<Double-Button-1>", lambda _event: self.play_selected_kind(kind))
        listbox.bind("<Button-3>", lambda event, panel_kind=kind: self.show_audio_context_menu(event, panel_kind), add="+")
        audio_buttons = Frame(panel, bg="#FFFFFF")
        audio_buttons.pack(fill="x", padx=8, pady=(0, 5))
        Button(audio_buttons, text="▶ OUVIR", command=lambda: self.play_selected_kind(kind), bg="#0F766E", activebackground="#115E59", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=3, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 3))
        Button(audio_buttons, text="▶ OUVIR TODOS", command=lambda: self.play_all_kind(kind), bg="#7C3AED", activebackground="#6D28D9", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=3, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(3, 0))
        drop_label = Label(panel, text="Arraste os áudios para a lista ou use ADICIONAR ÁUDIOS", bg="#FFFFFF", fg="#94A3B8", font=("Segoe UI", 8))
        drop_label.pack(fill="x", padx=8, pady=(0, 6))
        self.enable_drag_drop(listbox, kind)
        return panel

    def _context_audio_paths(self, kind: str, index: int):
        files = self.original_files if kind == "original" else self.dubbed_files
        if index < 0 or index >= len(files):
            return None, None
        selected = files[index]
        base_dir = self.original_base_dir if kind == "original" else self.dubbed_base_dir
        key = relative_audio_key(selected, base_dir)
        if kind == "original":
            counterpart = self.dubbed_by_stem.get(key)
            return selected, counterpart if counterpart is not None and counterpart.is_file() else None
        counterpart = self.original_by_stem.get(key)
        return selected, counterpart if counterpart is not None and counterpart.is_file() else None

    def _copy_context_value(self, value: str, success_message: str):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.root.update()
            self.status_var.set(success_message)
        except tk.TclError as exc:
            self.status_var.set(f"Não foi possível copiar: {exc}")

    def _context_action(self, kind: str, index: int, action: str):
        selected, counterpart = self._context_audio_paths(kind, index)
        original = selected if kind == "original" else counterpart
        dubbed = selected if kind == "dubbed" else counterpart
        if action == "open_original" or action == "copy_original":
            path = original
            label = "original"
        elif action == "open_dubbed" or action == "copy_dubbed":
            path = dubbed
            label = "dublado"
        else:
            path = selected
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

    def show_audio_context_menu(self, event, kind: str):
        listbox = self.original_listbox if kind == "original" else self.dubbed_listbox
        index = int(listbox.nearest(event.y))
        box = listbox.bbox(index) if index < listbox.size() else None
        if box is None or not (box[1] <= event.y <= box[1] + box[3]):
            return "break"
        listbox.selection_clear(0, END)
        listbox.selection_set(index)
        listbox.activate(index)
        menu = Menu(listbox, tearoff=0)
        menu.add_command(label=i18n.tr("ABRIR LOCAL DO ÁUDIO DUBLADO"), command=lambda: self._context_action(kind, index, "open_dubbed"))
        menu.add_command(label=i18n.tr("ABRIR LOCAL DO ÁUDIO ORIGINAL"), command=lambda: self._context_action(kind, index, "open_original"))
        menu.add_separator()
        menu.add_command(label=i18n.tr("COPIAR NOME DO ÁUDIO"), command=lambda: self._context_action(kind, index, "copy_name"))
        menu.add_command(label=i18n.tr("COPIAR LOCAL DO ÁUDIO DUBLADO"), command=lambda: self._context_action(kind, index, "copy_dubbed"))
        menu.add_command(label=i18n.tr("COPIAR LOCAL DO ÁUDIO ORIGINAL"), command=lambda: self._context_action(kind, index, "copy_original"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def play_selected_kind(self, kind: str):
        files = self.original_files if kind == "original" else self.dubbed_files
        listbox = self.original_listbox if kind == "original" else self.dubbed_listbox
        selection = listbox.curselection()
        if not selection or int(selection[0]) >= len(files):
            return
        index = int(selection[0])
        path = files[index]
        collection = "ÁUDIOS ORIGINAIS" if kind == "original" else "ÁUDIOS DUBLADOS"
        self.audio_player.play_one(path, f"{collection} ({len(files)})", playlist=files, index=index)

    def play_all_kind(self, kind: str):
        files = self.original_files if kind == "original" else self.dubbed_files
        label = "ÁUDIOS ORIGINAIS" if kind == "original" else "ÁUDIOS DUBLADOS"
        self.audio_player.play_all(files, f"{label} ({len(files)})")

    def enable_drag_drop(self, widget, kind: str):
        try:
            widget.drop_target_register("DND_Files")
            widget.dnd_bind("<<Drop>>", lambda event: self.handle_drop(event.data, kind))
        except Exception:
            # Tkinter padrão não traz DnD nativo; os botões continuam sendo o fallback.
            pass

    def handle_drop(self, raw: str, kind: str):
        paths = parse_drop_paths(raw, self.root)
        files = []
        for path in paths:
            if path.is_dir():
                folder_files = list_audio_files(path, converted_only=(kind == "dubbed"))
                if kind == "dubbed" and not folder_files:
                    folder_files = list_audio_files(path, converted_only=False)
                files.extend(folder_files)
            elif is_audio_file(path):
                files.append(path)
        self.set_audio_files(kind, files, directory_label="Arquivos arrastados")

    def choose_audio_folder(self, kind: str):
        selected = filedialog.askdirectory(parent=self.root, title="Escolher pasta de áudios")
        if selected:
            folder = Path(selected)
            files = list_audio_files(folder, converted_only=(kind == "dubbed"))
            if kind == "dubbed" and not files:
                files = list_audio_files(folder, converted_only=False)
            self.set_audio_files(kind, files, directory_label=str(folder), base_dir=folder)

    def add_audio_files(self, kind: str):
        selected = filedialog.askopenfilenames(parent=self.root, title="Selecionar áudios WAV", filetypes=[("Áudios WAV", "*.wav *.wave"), ("Todos os arquivos", "*.*")])
        if selected:
            current = self.original_files if kind == "original" else self.dubbed_files
            files = list(dict.fromkeys(current + [Path(path) for path in selected if is_audio_file(Path(path))]))
            self.set_audio_files(kind, files, directory_label="Arquivos selecionados")

    def choose_output_folder(self):
        selected = filedialog.askdirectory(parent=self.root, title="Pasta de saída dos áudios convertidos")
        if selected:
            self.output_dir_var.set(selected)

    def open_output_folder(self):
        folder = Path(self.output_dir_var.get().strip() or self.project_root).expanduser().resolve()
        self.open_folder(folder, "a pasta de saída")

    def clear_audio_files(self, kind: str):
        self.set_audio_files(kind, [], directory_label="Nenhuma pasta selecionada")

    def set_audio_files(self, kind: str, files: list[Path], directory_label: str, base_dir: Path | None = None):
        unique = list(dict.fromkeys(path.resolve() for path in files if is_audio_file(path)))
        if base_dir is not None:
            if kind == "original":
                self.original_base_dir = Path(base_dir).expanduser().resolve()
            else:
                self.dubbed_base_dir = Path(base_dir).expanduser().resolve()
        if kind == "original":
            self.original_files = sorted(unique, key=lambda path: path.name.casefold())
            self.original_dir_var.set(directory_label)
            self.panel_title_vars["original"].set(f"ÁUDIOS ORIGINAIS ({len(self.original_files)})")
            listbox = self.original_listbox
        else:
            self.dubbed_files = sorted(unique, key=lambda path: path.name.casefold())
            self.dubbed_dir_var.set(directory_label)
            self.panel_title_vars["dubbed"].set(f"ÁUDIOS DUBLADOS ({len(self.dubbed_files)})")
            listbox = self.dubbed_listbox
        listbox.delete(0, END)
        base_dir = self.original_base_dir if kind == "original" else self.dubbed_base_dir
        for path in (self.original_files if kind == "original" else self.dubbed_files):
            channels = self.detect_channels_quick(path)
            identifier = "mono" if channels == 1 else "estéreo" if channels == 2 else "canais ?"
            try:
                shown_name = path.relative_to(base_dir).as_posix()
            except ValueError:
                shown_name = path.name
            listbox.insert(END, f"{shown_name}   [{identifier}]")
        self.rebuild_maps()

    def detect_channels_quick(self, path: Path) -> int | None:
        try:
            with wave.open(str(path), "rb") as audio:
                return int(audio.getnchannels())
        except Exception:
            return None

    def rebuild_maps(self):
        self.original_by_stem = {}
        self.dubbed_by_stem = {}
        for path in self.original_files:
            self.original_by_stem.setdefault(relative_audio_key(path, self.original_base_dir), path)
        for path in self.dubbed_files:
            self.dubbed_by_stem.setdefault(relative_audio_key(path, self.dubbed_base_dir), path)
        pairs = len(set(self.original_by_stem) & set(self.dubbed_by_stem))
        self.count_var.set(f"Originais: {len(self.original_files)}    Dublados: {len(self.dubbed_files)}    Pares: {pairs}")

    def refresh_for_project(self):
        self.project_root = Path(getattr(self.root, "project_root", self.project_root)).resolve()
        try:
            self.audio_player.set_project_root(self.project_root)
        except Exception:
            pass
        default_output = self.project_root / DEFAULT_OUTPUT_FOLDER_NAME
        self.output_dir_var.set(str(default_output))
        self.refresh_folder_buttons()
        # A pasta de saída só é criada quando o usuário abre a pasta ou inicia a conversão.
        self.start_tool_alert()

    def missing_tools(self) -> list[str]:
        return [name for name in ("ffmpeg", "ffprobe", "ffplay", "sox") if executable_path(name, self.project_root) is None]

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

    def load_project_defaults(self, source_label: str):
        configure_project_root(self.project_root)
        original_dir = self.project_root / "WAV ORIGINAIS"
        dubbed_dir = self.project_root / "dublado"
        original_files = list_audio_files(original_dir, converted_only=False, exclude_converted=True)

        dubbed_files = list_audio_files(dubbed_dir, converted_only=True)
        if not dubbed_files:
            dubbed_files = list_audio_files(dubbed_dir, converted_only=False)
        self.set_audio_files("original", original_files, str(original_dir), base_dir=original_dir)
        self.set_audio_files("dubbed", dubbed_files, str(dubbed_dir), base_dir=dubbed_dir)
        self.status_var.set(f"Carregado da aba {source_label}: confira os pares antes de converter.")
        self.append_log(f"Carregamento da aba {source_label}: {len(original_files)} originais e {len(dubbed_files)} dublados.")

    def load_from_review(self):
        self.load_project_defaults("REVISÃO")

    def load_from_batch(self):
        self.load_project_defaults("CLONAGEM + DUBLAGEM")

    def _log_central(self, message, tag="normal") -> None:
        callback = getattr(self, "central_log_callback", None)
        if callable(callback):
            try:
                callback("CONVERTER DURAÇÃO", str(message), tag)
            except Exception:
                pass

    def append_log(self, message: str):
        self._log_central(message)
        self.queue.put(("log", message))

    def poll_messages(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", i18n.tr(str(payload)) + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif kind == "progress":
                    self.progress_var.set(str(payload))
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "download_progress":
                    description, downloaded, total = payload
                    if total and total > 0:
                        percent = update_download_progress(self.download_progress, description, downloaded, total)
                        self.download_status_var.set(f"Baixando {description}: {percent:.1f}% ({downloaded / 1048576:.1f} / {total / 1048576:.1f} MB)")
                    else:
                        update_download_progress(self.download_progress, description, downloaded, total)
                        self.download_status_var.set(f"Baixando {description}: {downloaded / 1048576:.1f} MB recebidos; tamanho final ainda não informado")
                elif kind == "download_complete":
                    percent = update_download_progress(self.download_progress, str(payload), 1, 1)
                    self.download_status_var.set(f"Download de {payload} concluído; preparando arquivos... ({percent:.1f}%)")
                elif kind == "conversion_progress":
                    index, total = payload
                    percent = min(100.0, index * 100.0 / max(1, total))
                    self.conversion_progress.configure(value=percent)
                    self.conversion_progress_var.set(f"Conversão: {index}/{total} áudios ({percent:.1f}%)")
                elif kind == "done":
                    self.running = False
                    self.convert_button.configure(state="normal")
                    self.status_var.set(str(payload))
                    self.progress_var.set("")
                    try:
                        conversion_value = float(self.conversion_progress.cget("value"))
                    except (TypeError, ValueError):
                        conversion_value = 0.0
                    if conversion_value < 100 and "Conversão finalizada" in str(payload):
                        self.conversion_progress.configure(value=100)
                    if "Conversão finalizada" in str(payload):
                        self.conversion_progress_var.set("Conversão: concluída")
                elif kind == "dependencies_done":
                    self.dependencies_running = False
                    self.dependencies_button.configure(state="normal")
                    self.stop_tool_alert()
                    try:
                        current_download = float(self.download_progress.cget("value"))
                    except Exception:
                        current_download = 0.0
                    if not self.missing_tools():
                        current_download = max(current_download, 100.0)
                    self.download_progress.stop()
                    self.download_progress.configure(mode="determinate", value=current_download)
                    self.status_var.set(str(payload))
        except queue.Empty:
            pass
        try:
            self.root.after(100, self.poll_messages)
        except Exception:
            pass

    def command_output(self, command: list[str]) -> tuple[int, str, str]:
        kwargs = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        process = subprocess.run(command, **kwargs)
        return process.returncode, process.stdout or "", process.stderr or ""

    def get_duration(self, path: Path) -> float:
        ffprobe = executable_path("ffprobe", self.project_root)
        if not ffprobe:
            raise RuntimeError("FFprobe não foi encontrado. Instale o FFmpeg e coloque ffprobe no PATH.")
        code, stdout, stderr = self.command_output([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
        if code != 0:
            raise RuntimeError(f"FFprobe não conseguiu ler {path.name}: {stderr.strip() or 'erro desconhecido'}")
        try:
            duration = float(stdout.strip())
        except ValueError as exc:
            raise RuntimeError(f"Duração inválida em {path.name}.") from exc
        if duration <= 0:
            raise RuntimeError(f"Duração zerada em {path.name}.")
        return duration

    def output_format_args(self, format_name: str | None = None) -> list[str]:
        spec = FORMAT_CHOICES[i18n.source_text(format_name or self.format_var.get())]
        args = ["-c:a", spec["codec"]]
        if spec.get("rate"):
            args.extend(["-ar", spec["rate"]])
        channels = self.current_output_channels
        if channels is None and spec.get("channels"):
            channels = int(spec["channels"])
        if channels:
            args.extend(["-ac", str(channels)])
        if spec.get("bitrate"):
            args.extend(["-b:a", spec["bitrate"]])
        if spec.get("quality"):
            args.extend(["-q:a", spec["quality"]])
        return args

    def output_extension(self, format_name: str) -> str:
        return FORMAT_CHOICES[format_name]["extension"]

    def run_ffmpeg(self, args: list[str]):
        ffmpeg = executable_path("ffmpeg", self.project_root)
        if not ffmpeg:
            raise RuntimeError("FFmpeg não foi encontrado. Instale o FFmpeg e coloque ffmpeg no PATH.")
        code, _stdout, stderr = self.command_output([ffmpeg, *args])
        if code != 0:
            raise RuntimeError(stderr.strip()[-1200:] or "FFmpeg retornou erro sem detalhes.")

    def detect_start_end_silence(self, source: Path) -> tuple[float, float]:
        """Detecta somente silêncio no começo e no fim, preservando o meio."""
        ffmpeg = executable_path("ffmpeg", self.project_root)
        if not ffmpeg:
            raise RuntimeError("FFmpeg não foi encontrado. Instale as ferramentas antes de converter.")
        command = [ffmpeg, "-i", str(source), "-af", f"silencedetect=n={DEFAULT_THRESHOLD_DB}dB:d={DEFAULT_MIN_SILENCE_SECONDS}", "-f", "null", "-"]
        code, _stdout, stderr = self.command_output(command)
        if code != 0 and not stderr:
            raise RuntimeError(f"FFmpeg não conseguiu analisar {source.name}.")
        audio_duration = self.get_duration(source)
        events: list[tuple[str, float]] = []
        for line in stderr.splitlines():
            if "silence_start" in line:
                match = re.search(r"silence_start:\s*([-+]?\d+(?:\.\d+)?)", line)
                if match:
                    events.append(("start", float(match.group(1))))
            elif "silence_end" in line:
                match = re.search(r"silence_end:\s*([-+]?\d+(?:\.\d+)?)", line)
                if match:
                    events.append(("end", float(match.group(1))))
        events.sort(key=lambda item: item[1])
        start_trim = 0.0
        end_trim = audio_duration
        if events and events[0][0] == "start" and events[0][1] <= 0.1:
            first_end = next((time_value for event_type, time_value in events if event_type == "end" and time_value > 0), None)
            if first_end is not None:
                start_trim = max(0.0, first_end)
        trailing_start = None
        for index in range(len(events) - 1, -1, -1):
            event_type, event_time = events[index]
            if event_type != "start":
                continue
            following_end = next((time_value for next_type, time_value in events[index + 1:] if next_type == "end"), None)
            if following_end is None or abs(following_end - audio_duration) < 0.1:
                trailing_start = event_time
                break
        if trailing_start is not None and trailing_start > start_trim:
            end_trim = min(audio_duration, trailing_start)
        if start_trim >= end_trim:
            return 0.0, audio_duration
        return start_trim, end_trim

    def silence_trim(self, source: Path, temp_dir: Path) -> Path:
        """Corta somente as extremidades detectadas, preservando o áudio central."""
        target = temp_dir / f"{source.stem}_sem_silencio.wav"
        start_time, end_time = self.detect_start_end_silence(source)
        if start_time <= 0.0 and abs(end_time - self.get_duration(source)) < 0.01:
            shutil.copy2(source, target)
            return target
        duration = end_time - start_time
        self.run_ffmpeg(["-y", "-i", str(source), "-ss", f"{start_time:.6f}", "-t", f"{duration:.6f}", "-c", "copy", "-avoid_negative_ts", "make_zero", str(target)])
        return target

    def make_atempo_chain(self, factor: float) -> str:
        # atempo aceita fatores entre 0.5 e 2.0; divide fatores extremos em etapas.
        factor = max(0.01, factor)
        parts: list[str] = []
        while factor > 2.0:
            parts.append("atempo=2.0")
            factor /= 2.0
        while factor < 0.5:
            parts.append("atempo=0.5")
            factor /= 0.5
        parts.append(f"atempo={factor:.8f}")
        return ",".join(parts)

    def convert_equal(self, source: Path, target: Path, target_duration: float, format_name: str):
        target.parent.mkdir(parents=True, exist_ok=True)
        self.run_ffmpeg(["-y", "-i", str(source), "-t", f"{target_duration:.6f}", *self.output_format_args(format_name), str(target)])

    def convert_shorter(self, source: Path, target: Path, target_duration: float, source_duration: float, format_name: str):
        target.parent.mkdir(parents=True, exist_ok=True)
        pad = max(0.0, target_duration - source_duration)
        self.run_ffmpeg(["-y", "-i", str(source), "-af", f"apad=pad_dur={pad:.6f},atrim=duration={target_duration:.6f}", *self.output_format_args(format_name), str(target)])

    def convert_longer(self, source: Path, target: Path, target_duration: float, source_duration: float, temp_dir: Path, format_name: str):
        target.parent.mkdir(parents=True, exist_ok=True)
        factor = source_duration / target_duration
        sox = executable_path("sox", self.project_root)
        stretched = temp_dir / f"{source.stem}_esticado.wav"
        if sox:
            code, _stdout, stderr = self.command_output([sox, str(source), str(stretched), "tempo", f"{factor:.8f}"])
            if code != 0:
                self.append_log(f"SoX falhou em {source.name}; usando fallback FFmpeg: {stderr.strip()[-300:]}")
                stretched = source
        else:
            stretched = source
        if stretched == source:
            self.run_ffmpeg(["-y", "-i", str(source), "-filter:a", self.make_atempo_chain(factor), "-t", f"{target_duration:.6f}", *self.output_format_args(format_name), str(target)])
        else:
            self.run_ffmpeg(["-y", "-i", str(stretched), "-t", f"{target_duration:.6f}", *self.output_format_args(format_name), str(target)])

    def pair_items(self):
        stems = sorted(set(self.original_by_stem) & set(self.dubbed_by_stem))
        return [(stem, self.original_by_stem[stem], self.dubbed_by_stem[stem]) for stem in stems]

    def tool_storage_dir(self) -> Path:
        app_dir = Path(os.environ.get("DUBLASKIZON_APP_DIR", Path(__file__).resolve().parent)).expanduser().resolve()
        target = app_dir / TOOLS_DIR_NAME
        target.mkdir(parents=True, exist_ok=True)
        return target

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
        temp_dir = Path(tempfile.mkdtemp(prefix="dublagenskizon_download_"))
        archive_path = temp_dir / f"{description}.zip"
        try:
            self.append_log(f"Baixando {description}...")
            self.queue.put(("download_progress", (description, 0, 0)))
            request = urllib.request.Request(url, headers={"User-Agent": "Dublaskizon/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as output:
                total = response.headers.get("Content-Length")
                total_bytes = int(total) if total and total.isdigit() else 0
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    self.queue.put(("download_progress", (description, downloaded, total_bytes)))
            self.queue.put(("download_complete", description))
            extract_dir = temp_dir / "extraido"
            self.safe_extract_zip(archive_path, extract_dir)
            return extract_dir
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def copy_executables_from_tree(self, source_root: Path, names: set[str], destination: Path) -> list[Path]:
        copied: list[Path] = []
        destination.mkdir(parents=True, exist_ok=True)
        wanted = {name.casefold() for name in names}
        for candidate in source_root.rglob("*"):
            if not candidate.is_file() or candidate.name.casefold() not in wanted:
                continue
            target = destination / candidate.name
            shutil.copy2(candidate, target)
            copied.append(target)
        return copied

    def copy_sibling_runtime_files(self, source_root: Path, executable_name: str, destination: Path):
        destination.mkdir(parents=True, exist_ok=True)
        executable = next((path for path in source_root.rglob(executable_name) if path.is_file()), None)
        if executable is None:
            return
        for sibling in executable.parent.iterdir():
            if sibling.is_file() and sibling.suffix.casefold() in {".dll", ".exe"}:
                shutil.copy2(sibling, destination / sibling.name)

    def dependency_worker(self):
        try:
            if os.name != "nt":
                self.append_log("Preparação automática de FFmpeg/SoX está disponível para Windows; no Linux/macOS use ferramentas no PATH.")
                self.queue.put(("download_progress", ("ferramentas", 1, 1)))
                self.queue.put(("dependencies_done", "No Windows, use este botão para baixar as ferramentas; neste sistema o PATH deve fornecê-las."))
                return
            tools_dir = self.tool_storage_dir()
            ffmpeg_ready = all(executable_path(name, self.project_root) is not None for name in ("ffmpeg", "ffprobe", "ffplay"))
            sox_ready = executable_path("sox", self.project_root) is not None
            if not ffmpeg_ready:
                extracted = self.download_and_extract(FFMPEG_WINDOWS_URL, tools_dir / "ffmpeg", "ffmpeg")
                copied = self.copy_executables_from_tree(extracted, {"ffmpeg.exe", "ffprobe.exe", "ffplay.exe"}, tools_dir)
                self.copy_sibling_runtime_files(extracted, "ffmpeg.exe", tools_dir)
                copied_names = {path.name.casefold() for path in copied}
                if not copied_names.issuperset({"ffmpeg.exe", "ffprobe.exe", "ffplay.exe"}):
                    raise RuntimeError("O pacote do FFmpeg não continha ffmpeg.exe, ffprobe.exe e ffplay.exe.")
                self.append_log("FFmpeg, FFprobe e FFplay foram preparados na pasta ferramentas_audio.")
            else:
                self.append_log("FFmpeg, FFprobe e FFplay já estão disponíveis; download ignorado.")
            if not sox_ready:
                extracted = self.download_and_extract(SOX_WINDOWS_URL, tools_dir / "sox", "sox")
                copied = self.copy_executables_from_tree(extracted, {"sox.exe", "libsox-3.dll"}, tools_dir)
                self.copy_sibling_runtime_files(extracted, "sox.exe", tools_dir)
                if not any(path.name.casefold() == "sox.exe" for path in copied):
                    raise RuntimeError("O pacote do SoX não continha sox.exe.")
                self.append_log("SoX foi preparado na pasta ferramentas_audio.")
            else:
                self.append_log("SoX já está disponível; download ignorado.")
            self.queue.put(("download_progress", ("ferramentas", 1, 1)))
            self.queue.put(("dependencies_done", "Ferramentas preparadas. FFmpeg/FFprobe e SoX estão prontos quando necessários."))
        except Exception as exc:
            self.append_log(f"ERRO ao preparar ferramentas: {exc}")
            self.queue.put(("download_progress", ("ferramentas", 0, 1)))
            self.queue.put(("dependencies_done", "Não foi possível preparar todas as ferramentas; confira o painel de processos."))

    def show_tools_help(self):
        messagebox.showinfo(i18n.tr("Ferramentas de áudio"), i18n.tr(TOOLS_HELP_TEXT), parent=self.root)

    def start_dependency_setup(self):
        self.stop_tool_alert()
        if self.dependencies_running or self.running:
            return
        self.dependencies_running = True
        self.dependencies_button.configure(state="disabled")
        self.download_progress.stop()
        self.download_progress.configure(mode="determinate", value=0)
        self.status_var.set("Preparando FFmpeg, FFprobe e SoX; aguarde...")
        self.dependency_thread = threading.Thread(target=self.dependency_worker, daemon=True)
        self.dependency_thread.start()

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
        self.rebuild_maps()
        pairs = self.pair_items()
        if not pairs:
            messagebox.showwarning("Conversão", "Nenhum par com o mesmo nome-base foi encontrado.", parent=self.root)
            return
        format_name = i18n.source_text(self.format_var.get())
        output_mode = i18n.source_text(self.output_mode_var.get())
        output_root = self.output_dir_var.get().strip() or str(self.project_root)
        try:
            Path(output_root).expanduser().resolve().mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Pasta de saída", f"Não foi possível preparar a pasta de duração:\n{output_root}\n\n{exc}", parent=self.root)
            return
        apply_silence = self.silence_var.get() == "1"
        self.forced_channels = None
        if self.preserve_channels_var.get() != "1":
            choice = messagebox.askyesnocancel(
                "Canais do resultado",
                "A preservação de mono/estéreo foi desativada.\n\nSIM = gerar tudo em ESTÉREO\nNÃO = gerar tudo em MONO\nCANCELAR = não iniciar",
                parent=self.root,
            )
            if choice is None:
                return
            self.forced_channels = 2 if choice else 1
        self.running = True
        self.cancel_event.clear()
        self.convert_button.configure(state="disabled")
        self.conversion_progress.configure(value=0)
        self.conversion_progress_var.set(f"Conversão: 0/{len(pairs)} áudios")
        self.status_var.set(f"Convertendo {len(pairs)} par(es)...")
        self._log_central(f"Iniciada conversão de {len(pairs)} par(es); formato: {format_name}; saída: {output_root}", "info")
        self.worker = threading.Thread(target=self.conversion_worker, args=(pairs, format_name, output_mode, output_root, apply_silence), daemon=True)
        self.worker.start()

    def conversion_worker(self, pairs, format_name: str, output_mode: str, output_root_value: str, apply_silence: bool):
        try:
            output_root = Path(output_root_value).expanduser().resolve()
            greater_dir = output_root / "AUDIO CONVERTIDO ..MAIOR.. DURAÇÃO"
            less_dir = output_root / "AUDIO CONVERTIDO ..MENOR.. DURAÇÃO"
            equal_dir = output_root / "AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO"
            single_dir = output_root / "AUDIO CONVERTIDO"
            separate = output_mode == OUTPUT_MODE_CHOICES[0]
            done = {"maior": 0, "menor": 0, "igual": 0, "erro": 0, "cancelado": 0}

            def target_for(category: str, stem: str) -> Path:
                if not separate:
                    target_dir = single_dir
                elif category == "maior":
                    target_dir = greater_dir
                elif category == "menor":
                    target_dir = less_dir
                else:
                    target_dir = equal_dir
                return target_dir / f"{stem}{self.output_extension(format_name)}"

            with tempfile.TemporaryDirectory(prefix="dublagenskizon_duracao_") as temp_name:
                temp_dir = Path(temp_name)
                total = len(pairs)
                for index, (stem, original, dubbed) in enumerate(pairs, start=1):
                    if self.cancel_event.is_set():
                        done["cancelado"] += total - index + 1
                        self._log_central(f"Conversão cancelada após {index - 1}/{total} par(es).", "info")
                        break
                    try:
                        self.current_output_channels = self.detect_channels_quick(original) if self.preserve_channels_var.get() == "1" else self.forced_channels
                        if self.current_output_channels not in (1, 2):
                            self.current_output_channels = self.detect_channels_quick(dubbed) or self.forced_channels or 1
                        original_duration = self.get_duration(original)
                        source = self.silence_trim(dubbed, temp_dir) if apply_silence else dubbed
                        dubbed_duration = self.get_duration(source)
                        difference = dubbed_duration - original_duration
                        if abs(difference) <= DURATION_EQUAL_TOLERANCE:
                            category = "igual"
                            self.convert_equal(source, target_for(category, stem), original_duration, format_name)
                        elif difference > 0:
                            category = "maior"
                            self.convert_longer(source, target_for(category, stem), original_duration, dubbed_duration, temp_dir, format_name)
                        else:
                            category = "menor"
                            self.convert_shorter(source, target_for(category, stem), original_duration, dubbed_duration, format_name)
                        done[category] += 1
                        self.append_log(f"[{index}/{total}] {stem}: dublado {dubbed_duration:.3f}s / original {original_duration:.3f}s -> {category.upper()}")
                    except Exception as exc:
                        done["erro"] += 1
                        self.append_log(f"[{index}/{total}] ERRO {stem}: {exc}")
                    self.queue.put(("progress", f"Processados {index}/{total} — maior: {done['maior']} | menor: {done['menor']} | igual: {done['igual']} | erros: {done['erro']}"))
                    self.queue.put(("conversion_progress", (index, total)))
            summary = f"Conversão finalizada. Maior: {done['maior']} | Menor: {done['menor']} | Igual: {done['igual']} | Erros: {done['erro']}"
            if done["cancelado"]:
                summary += f" | Cancelados: {done['cancelado']}"
            output_names = [single_dir.name] if not separate else [greater_dir.name, less_dir.name, equal_dir.name]
            output_message = f"Saídas: {', '.join(output_names)}"
            self._log_central(output_message, "info")
            self.queue.put(("log", output_message))
            self._log_central(summary, "ok" if done["erro"] == 0 and done["cancelado"] == 0 else "info")
            self.queue.put(("done", summary))
        except Exception as exc:
            self._log_central(f"FALHA GERAL: {exc}", "error")
            self.queue.put(("log", f"FALHA GERAL: {exc}"))
            self.queue.put(("done", "Conversão encerrada com erro."))

    def cancel_run(self):
        if self.running:
            self.cancel_event.set()
            self.status_var.set("Cancelando após o par atual...")


if not TK_AVAILABLE:
    DurationConverterApp = None
