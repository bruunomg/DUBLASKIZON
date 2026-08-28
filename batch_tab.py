#!/usr/bin/env python3
"""Gerador grafico portatil de clonagem e dublagem.

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

O programa inicia automaticamente a fila. A interface usa progresso visual
por etapas: azul para preparacao da referencia/clonagem e lilas para a
sintese da dublagem. O OmniVoice nao fornece uma porcentagem separada para
cada subetapa, portanto a barra lilas representa o andamento da cena enquanto
ela esta sendo processada e termina em 100% quando o WAV e salvo.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import shutil
import time
import re
import json
import tempfile
import wave
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
try:
    from .audio_player import AudioPlayerManager, reveal_in_file_manager
    from .ui_theme import apply_button_style, apply_button_style_to_tree, surface_color
    from .duration_converter_tab import FFMPEG_WINDOWS_URL, TOOLS_DIR_NAME, HoverTooltip, executable_path, update_download_progress
except ImportError:
    from audio_player import AudioPlayerManager, reveal_in_file_manager
    from ui_theme import apply_button_style, apply_button_style_to_tree, surface_color
    from duration_converter_tab import FFMPEG_WINDOWS_URL, TOOLS_DIR_NAME, HoverTooltip, executable_path, update_download_progress

try:
    from tkinter import END, Menu, StringVar, Text, Tk, messagebox, ttk
    from tkinter import Button, Canvas, Entry, Frame, Label, Listbox, Scrollbar, Toplevel
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

try:
    from tkinterdnd2 import DND_FILES  # type: ignore
except Exception:
    DND_FILES = "DND_Files"

MODEL = "edwixx/omnivoice-brpt-v15"
LANGUAGE = "pt"
INSTRUCT = "portuguese accent"
OVERWRITE = False
DEFAULT_MODEL_CHOICES = [
    ("OmniVoice BR-PT v1.5 — recomendado", "edwixx/omnivoice-brpt-v15"),
    ("OmniVoice base — 600+ idiomas", "k2-fsa/OmniVoice"),
]
MODEL_CHOICES = list(DEFAULT_MODEL_CHOICES)
MODE_CHOICES = [
    ("Voice Cloning — usa o WAV de cada cena", "clone"),
    ("Voice Design — usa descrição da voz", "design"),
    ("Auto Voice — voz automática", "auto"),
]
VOICE_PROFILES = {
    "Automática — OmniVoice escolhe": "",
    "Homem jovem — natural": "young adult male voice, natural, expressive, clear Brazilian Portuguese",
    "Homem adulto — natural": "adult male voice, natural, confident, clear Brazilian Portuguese",
    "Homem adulto — grave": "adult male voice, deep, strong, cinematic, clear Brazilian Portuguese",
    "Homem idoso — experiente": "elderly male voice, experienced, warm, slightly raspy, clear Brazilian Portuguese",
    "Mulher jovem — natural": "young adult female voice, natural, expressive, clear Brazilian Portuguese",
    "Mulher adulta — natural": "adult female voice, natural, confident, clear Brazilian Portuguese",
    "Mulher adulta — grave": "adult female voice, deep, strong, cinematic, clear Brazilian Portuguese",
    "Mulher idosa — experiente": "elderly female voice, experienced, warm, clear Brazilian Portuguese",
    "Criança — menino": "young boy voice, natural, expressive, clear Brazilian Portuguese",
    "Criança — menina": "young girl voice, natural, expressive, clear Brazilian Portuguese",
    "Narrador — cinematográfico": "cinematic narrator voice, authoritative, dramatic, clear Brazilian Portuguese",
    "Robô / inteligência artificial": "robotic artificial intelligence voice, precise, controlled, clear Brazilian Portuguese",
}

R_PRONUNCIATION_CHOICES = (
    ("SEM ALTERAÇÃO", "unchanged"),
    ("R SUAVE", "soft"),
    ("R NORMAL", "normal"),
    ("R FORTE", "strong"),
)
# O OmniVoice BR-PT atual aceita apenas itens enumerados no --instruct
# (por exemplo, ``portuguese accent``); frases livres sobre o R causam
# ``ValueError: Unsupported instruct items``. O ajuste do R é feito somente
# por grafia segura quando houver uma correspondência ortográfica inequívoca.
R_PRONUNCIATION_INSTRUCTIONS: dict[str, str] = {
    "soft": "",
    "normal": "",
    "strong": "",
}
_R_LETTERS = "aáàâãeéêèiíìîoóôõuúùûAÁÀÂÃEÉÊÈIÍÌÎOÓÔÕUÚÙÛ"


def apply_r_pronunciation(text: str, mode: str = "unchanged") -> str:
    """Aplica o melhor ajuste textual seguro antes do OmniVoice.

    O OmniVoice rejeita frases livres no ``--instruct``; por isso o método
    nunca envia instrução textual inválida. Para R suave, a grafia ``rr``
    entre vogais é reduzida para ``r``; para R forte, um ``r`` simples entre
    vogais vira ``rr``. Isso cobre a alternância ortográfica mais comum sem
    alterar números, caminhos ou pontuação. O modo normal preserva o texto.
    """
    source = str(text or "")
    normalized = str(mode or "unchanged").casefold()
    if normalized == "soft":
        pattern = re.compile(rf"([{_R_LETTERS}])rr(?=[{_R_LETTERS}])", re.IGNORECASE)
        return pattern.sub(lambda match: f"{match.group(1)}r", source)
    if normalized == "strong":
        pattern = re.compile(rf"([{_R_LETTERS}])r(?=[{_R_LETTERS}])", re.IGNORECASE)
        return pattern.sub(lambda match: f"{match.group(1)}rr", source)
    return source


def r_pronunciation_instruction(mode: str = "unchanged") -> str:
    return R_PRONUNCIATION_INSTRUCTIONS.get(str(mode or "unchanged").casefold(), "")


_PROJECT_ROOT = os.environ.get("DUBLASKIZON_PROJECT_ROOT")
ROOT = Path(_PROJECT_ROOT).resolve() if _PROJECT_ROOT else Path(__file__).resolve().parent
AUDIO_DIR = ROOT / "WAV ORIGINAIS"
TEXT_DIR = ROOT / "TXT TEXTO PORTUGUES"
OUTPUT_DIR = ROOT / "dublado"
REVISIONS_DIR = ROOT / "revisoes"
REVIEW_BAT = ROOT / "revisoes" / "REVISAR-DUBLAGEM.bat"
VOICE_SETTINGS_FILE = ROOT / "Dublaskizon_vozes.json"
AUDIO_EXTENSIONS = {".wav", ".wave", ".waw", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".aiff", ".aif", ".wma", ".opus"}
WAV_EXTENSIONS = {".wav", ".wave", ".waw"}
OMNIVOICE_REFERENCE_SAMPLE_RATE = 24000
OMNIVOICE_REFERENCE_CHANNELS = 1
OMNIVOICE_REFERENCE_CODEC = "pcm_s16le"
OMNIVOICE_BACKUP_DIR_NAME = "_BACKUP_OMNIVOICE"


def parse_drop_paths(raw: str, tk_root=None) -> list[Path]:
    if not raw:
        return []
    try:
        values = list(tk_root.tk.splitlist(raw)) if tk_root is not None else [raw]
    except Exception:
        values = [raw]
    return [Path(str(value).strip().strip('"')).expanduser().resolve() for value in values if str(value).strip()]


def audio_stem(path: Path) -> str:
    """Retorna somente o nome-base físico do arquivo."""
    return Path(path).stem


def relative_scene_key(path: Path, root_dir: Path) -> str:
    """Retorna a chave estável `subpasta/cena` sem depender do separador do SO."""
    path = Path(path).expanduser().resolve()
    try:
        relative = path.relative_to(Path(root_dir).expanduser().resolve()).with_suffix("")
        return relative.as_posix()
    except ValueError:
        return path.stem


def is_wav_path(path: Path) -> bool:
    return Path(path).suffix.casefold() in WAV_EXTENSIONS


def is_internal_omnivoice_backup(path: Path) -> bool:
    return OMNIVOICE_BACKUP_DIR_NAME.casefold() in {part.casefold() for part in Path(path).parts}


def wav_needs_omnivoice_adjustment(path: Path) -> bool:
    """Verifica se um WAV ainda não está no perfil PCM mono de 24 kHz."""
    path = Path(path).expanduser().resolve()
    if not is_wav_path(path) or not path.is_file() or is_internal_omnivoice_backup(path):
        return False
    try:
        with wave.open(str(path), "rb") as wav_file:
            return not (
                wav_file.getcomptype() == "NONE"
                and wav_file.getsampwidth() == 2
                and wav_file.getnchannels() == OMNIVOICE_REFERENCE_CHANNELS
                and wav_file.getframerate() == OMNIVOICE_REFERENCE_SAMPLE_RATE
            )
    except (EOFError, wave.Error, OSError):
        pass
    ffprobe = executable_path("ffprobe", ROOT)
    if not ffprobe:
        # Sem FFprobe não é seguro afirmar que o arquivo já está no perfil-alvo.
        return True
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,sample_rate,channels,bits_per_sample",
                "-of", "json", str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            **hidden_process_kwargs(),
        )
        if result.returncode != 0:
            return True
        data = json.loads(result.stdout or "{}")
        streams = data.get("streams") or []
        stream = streams[0] if streams else {}
        return not (
            str(stream.get("codec_name", "")).casefold() == OMNIVOICE_REFERENCE_CODEC
            and int(stream.get("sample_rate", 0) or 0) == OMNIVOICE_REFERENCE_SAMPLE_RATE
            and int(stream.get("channels", 0) or 0) == OMNIVOICE_REFERENCE_CHANNELS
            and int(stream.get("bits_per_sample", 0) or 0) == 16
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return True


def is_format_archive_dir(path: Path) -> bool:
    return Path(path).name.casefold() in {extension.lstrip(".").casefold() for extension in AUDIO_EXTENSIONS if extension.casefold() not in WAV_EXTENSIONS}


def configure_project_root(project_root: Path) -> None:
    global ROOT, AUDIO_DIR, TEXT_DIR, OUTPUT_DIR, REVISIONS_DIR, REVIEW_BAT, VOICE_SETTINGS_FILE
    ROOT = Path(project_root).expanduser().resolve()
    os.environ["DUBLASKIZON_PROJECT_ROOT"] = str(ROOT)
    AUDIO_DIR = ROOT / "WAV ORIGINAIS"
    TEXT_DIR = ROOT / "TXT TEXTO PORTUGUES"
    OUTPUT_DIR = ROOT / "dublado"
    REVISIONS_DIR = ROOT / "revisoes"
    REVIEW_BAT = ROOT / "revisoes" / "REVISAR-DUBLAGEM.bat"
    VOICE_SETTINGS_FILE = ROOT / "Dublaskizon_vozes.json"


def _revision_scene_dir(stem: str) -> Path:
    return REVISIONS_DIR / Path(stem).parent


def _revision_scene_basename(stem: str) -> str:
    return Path(stem).name


def _next_revision_version(stem: str) -> int:
    directory = _revision_scene_dir(stem)
    prefix = f"{_revision_scene_basename(stem)}_v"
    highest = 0
    if directory.is_dir():
        for path in directory.glob(f"{_revision_scene_basename(stem)}_v*.wav"):
            suffix = path.stem[len(prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return highest + 1


def _archive_dubbed_before_replace(stem: str, source: Path) -> Path | None:
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        return None
    directory = _revision_scene_dir(stem)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{_revision_scene_basename(stem)}_v{_next_revision_version(stem):02d}.wav"
    shutil.copy2(source, destination)
    return destination


def character_from_stem(stem: str) -> str:
    ignored = {"beep", "dialog", "dialogue", "voice", "line", "audio", "wav", "take"}
    parts = [part for part in re.split(r"[_\-. ]+", stem) if part]
    for part in reversed(parts):
        if not part.isdigit() and part.casefold() not in ignored and not re.fullmatch(r"\d+", part):
            return part
    return "Geral"


def find_ffmpeg_directory() -> Path | None:
    found = shutil.which("ffmpeg")
    if found:
        return Path(found).resolve().parent
    roots = [ROOT / "ferramentas_audio", Path(os.environ.get("DUBLASKIZON_APP_DIR", ROOT)) / "ferramentas_audio"]
    for base in roots:
        if not base.is_dir():
            continue
        for candidate in base.rglob("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"):
            if candidate.is_file():
                return candidate.parent
    return None


class RoundedProgress:
    def __init__(self, parent, width=420, height=22, track="#E8E8EE", fill="#4F81BD"):
        self.width = width
        self.height = height
        self.track = track
        self.fill = fill
        self.canvas = Canvas(parent, width=width, height=height, highlightthickness=0, bg=parent.cget("background"))
        self.fraction = 0.0
        self.draw()

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)

    def draw_round_rect(self, x1, y1, x2, y2, radius, color, tag):
        radius = max(1, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
        self.canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=color, outline=color, tags=tag)
        self.canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=color, outline=color, tags=tag)
        self.canvas.create_oval(x1, y1, x1 + 2 * radius, y1 + 2 * radius, fill=color, outline=color, tags=tag)
        self.canvas.create_oval(x2 - 2 * radius, y1, x2, y1 + 2 * radius, fill=color, outline=color, tags=tag)
        self.canvas.create_oval(x1, y2 - 2 * radius, x1 + 2 * radius, y2, fill=color, outline=color, tags=tag)
        self.canvas.create_oval(x2 - 2 * radius, y2 - 2 * radius, x2, y2, fill=color, outline=color, tags=tag)

    def set(self, fraction):
        self.fraction = max(0.0, min(1.0, float(fraction)))
        self.draw()

    def set_theme(self, track: str, fill: str, background: str):
        self.track = track
        self.fill = fill
        self.canvas.configure(bg=background)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        margin = 1
        radius = (self.height - 2 * margin) / 2
        self.draw_round_rect(margin, margin, self.width - margin, self.height - margin, radius, self.track, "track")
        if self.fraction > 0:
            right = margin + max(2 * radius, (self.width - 2 * margin) * self.fraction)
            self.draw_round_rect(margin, margin, min(right, self.width - margin), self.height - margin, radius, self.fill, "fill")


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "--:--:--"
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def hidden_process_kwargs() -> dict:
    if not sys.platform.startswith("win"):
        return {}
    kwargs = {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    kwargs["startupinfo"] = startupinfo
    kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return kwargs


def find_omnivoice_command() -> list[str] | None:
    configured = os.environ.get("OMNIVOICE_INFER")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    for name in ("omnivoice-infer", "omnivoice-infer.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    if sys.platform.startswith("win"):
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            base = Path(local_appdata)
            candidates.extend(base.glob("Packages/PythonSoftwareFoundation.Python*/LocalCache/local-packages/Python*/Scripts/omnivoice-infer.exe"))
            candidates.extend(base.glob("Programs/Python/Python*/Scripts/omnivoice-infer.exe"))
        candidates.extend(Path.home().glob("AppData/Roaming/Python/Python*/Scripts/omnivoice-infer.exe"))
    candidates.append(Path(sys.executable).parent / "Scripts" / "omnivoice-infer.exe")
    for candidate in candidates:
        if candidate.is_file():
            return [str(candidate)]
    if not getattr(sys, "frozen", False):
        return [sys.executable, "-u", "-m", "omnivoice.cli.infer"]
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            return [found, "-u", "-m", "omnivoice.cli.infer"]
    launcher = shutil.which("py")
    if launcher:
        return [launcher, "-3.12", "-m", "omnivoice.cli.infer"]
    return None


def model_cache_roots() -> list[Path]:
    """Retorna os diretórios comuns de cache sem fazer uma busca recursiva pesada."""
    roots: list[Path] = []
    for variable in ("HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value).expanduser())
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        roots.append(Path(hf_home).expanduser() / "hub")
    roots.append(Path.home() / ".cache" / "huggingface" / "hub")
    if sys.platform.startswith("win"):
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            roots.append(Path(local_appdata) / "huggingface" / "hub")
        roots.append(Path.home() / "AppData" / "Local" / "huggingface" / "hub")
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = os.path.normcase(os.path.abspath(str(root)))
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def cached_model_ids() -> list[str]:
    """Lista repositórios de modelos já baixados no cache local do Hugging Face."""
    model_ids: set[str] = set()
    for cache_root in model_cache_roots():
        try:
            if not cache_root.is_dir():
                continue
            for entry in cache_root.iterdir():
                if not entry.is_dir() or not entry.name.startswith("models--"):
                    continue
                encoded = entry.name[len("models--") :]
                if "--" in encoded:
                    model_ids.add(encoded.replace("--", "/", 1))
        except (OSError, PermissionError):
            continue
    return sorted(model_ids, key=str.casefold)


def discover_model_choices() -> list[tuple[str, str]]:
    """Combina modelos conhecidos com todos os repositórios encontrados no cache."""
    choices = list(DEFAULT_MODEL_CHOICES)
    known_ids = {model_id for _label, model_id in choices}
    for model_id in cached_model_ids():
        if model_id not in known_ids:
            choices.append((f"Modelo detectado no cache — {model_id}", model_id))
    return choices


def model_is_cached(model_id: str) -> bool:
    encoded = model_id.replace("/", "--")
    return any((cache_root / f"models--{encoded}").is_dir() for cache_root in model_cache_roots())


def find_audio_by_stem() -> dict[str, Path]:
    if not AUDIO_DIR.is_dir():
        return {}
    files: dict[str, Path] = {}
    for path in sorted(AUDIO_DIR.rglob("*"), key=lambda item: str(item).casefold()):
        if (
            is_internal_omnivoice_backup(path)
            or is_format_archive_dir(path.parent)
            or not path.is_file()
            or path.suffix.casefold() not in AUDIO_EXTENSIONS
        ):
            continue
        stem = relative_scene_key(path, AUDIO_DIR)
        current = files.get(stem)
        if current is None or (is_wav_path(path) and not is_wav_path(current)):
            files[stem] = path
    return files


def find_text_by_stem() -> dict[str, Path]:
    if not TEXT_DIR.is_dir():
        return {}
    return {
        relative_scene_key(path, TEXT_DIR): path
        for path in sorted(TEXT_DIR.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file() and path.suffix.lower() == ".txt"
    }


def _unique_archive_destination(source: Path, archive_dir: Path) -> Path:
    destination = archive_dir / source.name
    if not destination.exists():
        return destination
    index = 2
    while True:
        candidate = archive_dir / f"{source.stem}_original_{index}{source.suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def archive_source_audio(source: Path) -> Path | None:
    """Move a fonte para uma subpasta da extensão, sem sair de WAV ORIGINAIS.

    O WAV convertido permanece no mesmo diretório da fonte. Arquivos externos e WAVs
    não são movidos; o nome original é preservado sempre que não houver colisão.
    """
    source = Path(source).expanduser().resolve()
    audio_root = AUDIO_DIR.resolve()
    try:
        source.relative_to(audio_root)
    except ValueError:
        return None
    if source.suffix.casefold() not in AUDIO_EXTENSIONS or is_wav_path(source):
        return None
    if is_format_archive_dir(source.parent):
        return None
    archive_dir = source.parent / source.suffix.lstrip(".").lower()
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = _unique_archive_destination(source, archive_dir)
    try:
        source.rename(destination)
    except OSError:
        return None
    return destination


def archive_existing_sources_with_wav() -> list[str]:
    """Organiza fontes não-WAV que já ficaram ao lado do WAV correspondente."""
    if not AUDIO_DIR.is_dir():
        return []
    archived: list[str] = []
    archive_folder_names = {extension.lstrip(".").casefold() for extension in AUDIO_EXTENSIONS if not is_wav_path(Path(f"x{extension}"))}
    directories = [AUDIO_DIR, *[path for path in AUDIO_DIR.rglob("*") if path.is_dir() and not is_internal_omnivoice_backup(path)]]
    for directory in sorted(directories, key=lambda item: str(item).casefold()):
        if directory.name.casefold() in archive_folder_names:
            continue
        try:
            entries = list(directory.iterdir())
        except (OSError, PermissionError):
            continue
        wav_stems = {path.stem for path in entries if path.is_file() and is_wav_path(path)}
        for path in sorted(entries, key=lambda item: item.name.casefold()):
            if is_internal_omnivoice_backup(path) or not path.is_file() or is_wav_path(path) or path.suffix.casefold() not in AUDIO_EXTENSIONS or path.stem not in wav_stems:
                continue
            destination = archive_source_audio(path)
            if destination is not None:
                archived.append(f"{path.name} → {destination.parent.name}/{destination.name}")
    return archived


def migrate_legacy_converted_wavs() -> list[str]:
    """Corrige nomes antigos e organiza fontes que já possuem WAV correspondente."""
    if not AUDIO_DIR.is_dir():
        return []
    txt_stems = {
        relative_scene_key(path, TEXT_DIR)
        for path in TEXT_DIR.rglob("*")
        if path.is_file() and path.suffix.casefold() == ".txt"
    } if TEXT_DIR.is_dir() else set()
    renamed: list[str] = []
    legacy_pattern = re.compile(r"^(?P<base>.+?)[_ .-]+(?:convertido|converted)(?:[_ .-]+\d+)?$", re.IGNORECASE)
    for path in sorted(AUDIO_DIR.rglob("*"), key=lambda item: str(item).casefold()):
        if is_internal_omnivoice_backup(path) or not path.is_file() or path.suffix.casefold() not in WAV_EXTENSIONS:
            continue
        match = legacy_pattern.match(path.stem)
        if not match:
            continue
        destination_dir = path.parent.parent if is_format_archive_dir(path.parent) else path.parent
        try:
            relative_parent = destination_dir.resolve().relative_to(AUDIO_DIR.resolve()).as_posix()
        except ValueError:
            relative_parent = ""
        target_key = f"{relative_parent}/{match.group('base')}" if relative_parent and relative_parent != "." else match.group("base")
        if target_key not in txt_stems:
            continue
        destination = destination_dir / f"{match.group('base')}{path.suffix}"
        if destination.exists():
            continue
        try:
            path.rename(destination)
            renamed.append(f"{path.name} → {destination.name}")
        except OSError:
            continue
    renamed.extend(archive_existing_sources_with_wav())
    return renamed


def natural_key(value: str):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


class BatchApp:
    def __init__(self, root, embedded=False, review_callback=None, project_actions=None):
        self.root = root
        self.embedded = embedded
        self.review_callback = review_callback
        self.project_actions = project_actions or {}
        self.central_log_callback = self.project_actions.get("central_log")
        self.theme = {"mode": "claro", "input": "#FFFFFF", "input_text": "#1F2937", "select": "#DBEAFE"}
        if not embedded:
            self.root.title("Clonar + Dublar — OmniVoice BR-PT")
            self.root.geometry("1120x760")
            self.root.minsize(820, 580)
            self.root.protocol("WM_DELETE_WINDOW", self.close_window)

        self.legacy_audio_renames = migrate_legacy_converted_wavs()
        discovered_audio = find_audio_by_stem()
        self.pending_non_wav_audio = [Path(path) for path in discovered_audio.values() if not is_wav_path(path)]
        # WAVs existentes também podem precisar do perfil indicado para referência OmniVoice.
        self.audio_by_stem = {stem: path for stem, path in discovered_audio.items() if is_wav_path(path)}
        self.pending_wav_audio = [path for path in self.audio_by_stem.values() if wav_needs_omnivoice_adjustment(path)]
        self.initial_audio_conversion_errors: list[str] = [f"WAV legado renomeado: {item}" for item in self.legacy_audio_renames]
        self.initial_conversion_prompted = False
        self.text_by_stem = find_text_by_stem()
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
            self.text_by_stem = find_text_by_stem()
        self.stems = sorted(set(self.audio_by_stem) & set(self.text_by_stem), key=str.casefold)
        self.sort_mode = "alphabetical"
        self.run_stems = list(self.stems)
        self.force_overwrite = False
        self.statuses = {stem: "pendente" for stem in self.stems}
        self.message_queue: queue.Queue = queue.Queue()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.running = False
        self.paused = False
        self.stop_after_current = False
        self.dependencies_running = False
        self.dependency_thread = None
        self.tool_alert_after_id = None
        self.tool_alert_until = 0.0
        self.tool_alert_on = False
        self.download_status_var = StringVar(value="Ferramentas: não verificadas")
        self.audio_conversion_status_var = StringVar(value="")
        self.audio_count_var = StringVar(value="Áudios carregados: 0 | Cenas prontas: 0")
        self.audio_conversion_thread = None
        self.audio_conversion_queue: queue.Queue = queue.Queue()
        self.cancel_requested = False
        self.worker_thread = None
        self.current_process = None
        self.current_stem = None
        self.stage_after_id = None
        self.clock_after_id = None
        self.run_started_at = None
        self.last_elapsed_seconds = 0.0
        self.counts = {"gerados": 0, "pulados": 0, "falhas": 0}
        self.infer_prefix = None
        self.audio_player = AudioPlayerManager(self.root, ROOT, status_callback=lambda text: self.emit_log(text, "info"))

        self.current_var = StringVar(value="Aguardando início — escolha a ferramenta e clique em INICIAR DUBLAGEM")
        self.summary_var = StringVar(value="")
        self.model_choices = discover_model_choices()
        self.model_var = StringVar(value=self.display_model(*self.model_choices[0]))
        self.mode_var = StringVar(value=MODE_CHOICES[0][0])
        self.instruct_var = StringVar(value=INSTRUCT)
        self.voice_profile_var = StringVar(value=next(iter(VOICE_PROFILES)))
        self.r_pronunciation_var = StringVar(value=R_PRONUNCIATION_CHOICES[0][0])
        self.character_voice_profiles: dict[str, str] = {}
        self.load_voice_settings()
        self.model_info_var = StringVar(value="")
        self.mode_info_var = StringVar(value="")
        self.status_var = StringVar(value="Pronto")
        self.audio_player.set_scene_integration(self._sync_audio_player_selection)
        self.audio_player.set_scene_text_integration(self.load_scene_text_for_player, self.save_scene_text_from_player)
        self.review_audio_target = None
        self.review_regen_marker_state = None
        self.review_regen_last_progress_state = None
        self.elapsed_var = StringVar(value="Tempo decorrido: 00:00:00")
        self.eta_var = StringVar(value="Tempo restante estimado: --:--:--")
        self.finish_banner_var = StringVar(value="")
        self.build_ui()
        self.populate_queue()
        for conversion_error in self.initial_audio_conversion_errors:
            self.emit_log(conversion_error, "error")
        self.emit_log("Selecione o modelo e o modo. A fila só começa ao clicar em INICIAR DUBLAGEM.", "info")
        self.update_model_info()
        self.update_mode_info()
        self.root.after(100, self.poll_messages)
        # O botão fica visível e sinalizado assim que a aba é aberta quando os
        # binários portáteis ainda não estão disponíveis.
        self.start_tool_alert()
        # O usuário já consegue ver e usar BAIXAR / PREPARAR FERRAMENTAS quando
        # o aviso de conversão inicial aparecer.
        self.root.after(700, self.prompt_initial_reference_preparation)

    def load_voice_settings(self):
        try:
            data = json.loads(VOICE_SETTINGS_FILE.read_text(encoding="utf-8"))
            profile = str(data.get("default_profile", ""))
            if profile in VOICE_PROFILES:
                self.voice_profile_var.set(profile)
            self.instruct_var.set(str(data.get("complement", INSTRUCT)))
            saved_r_raw = str(data.get("r_pronunciation", "unchanged"))
            saved_r_mode = saved_r_raw.casefold()
            saved_r_source = i18n.source_text(saved_r_raw)
            saved_r_label = next(
                (label for label, mode_id in R_PRONUNCIATION_CHOICES if mode_id == saved_r_mode or label == saved_r_source),
                R_PRONUNCIATION_CHOICES[0][0],
            )
            self.r_pronunciation_var.set(saved_r_label)
            mappings = data.get("characters", {})
            if isinstance(mappings, dict):
                self.character_voice_profiles = {str(key): str(value) for key, value in mappings.items() if str(value) in VOICE_PROFILES}
        except (OSError, ValueError, TypeError):
            pass

    def save_voice_settings(self):
        try:
            VOICE_SETTINGS_FILE.write_text(json.dumps({
                "default_profile": self.voice_profile_var.get(),
                "complement": self.instruct_var.get().strip(),
                "r_pronunciation": self.selected_r_pronunciation_id(),
                "characters": self.character_voice_profiles,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.emit_log(f"Não foi possível salvar as escolhas de voz: {exc}", "error")

    def apply_theme(self, theme):
        self.theme = theme
        try:
            style = ttk.Style(self.root)
            track = theme.get("border", "#CBD5E1")
            fill = theme.get("warning", "#F97316")
            style.configure("BatchDownload.Horizontal.TProgressbar", troughcolor=track, background=fill, lightcolor=fill, darkcolor=fill)
            conversion_fill = theme.get("select", "#2563EB")
            style.configure("BatchConversion.Horizontal.TProgressbar", troughcolor=track, background=conversion_fill, lightcolor=conversion_fill, darkcolor=conversion_fill)
            if hasattr(self, "download_progress"):
                self.download_progress.configure(style="BatchDownload.Horizontal.TProgressbar")
            if hasattr(self, "audio_conversion_progress"):
                self.audio_conversion_progress.configure(style="BatchConversion.Horizontal.TProgressbar")
        except Exception:
            pass
        root_bg = theme.get("root", "#F5F6FA")
        surface = theme.get("surface", "#FFFFFF")
        footer = theme.get("footer", surface)
        text = theme.get("text", "#1F2937")
        muted = theme.get("muted", "#64748B")
        input_bg = theme.get("input", surface)
        input_fg = theme.get("input_text", text)
        # Inclui também as cores claras usadas depois de aplicar o tema escuro.
        # Sem elas, ao voltar para o tema claro alguns Labels permaneciam quase brancos.
        neutral_fgs = {"#1F2937", "#26364A", "#5B6472", "#6B7280", "#334155", "#374151", "#475569", "#64748B", "#CBD5E1", "#F8FAFC", "#FFFFFF", "white"}
        root_backgrounds = {"#F5F6FA", "#111827", "#202938", "#334155"}
        surface_backgrounds = {"#FFFFFF", "white", "#1F2937", "#243244", "#2A3546", "#3F4D5F", "#314055", "#475569"}
        footer_backgrounds = {"#E8EDF5", "#EEF2F7", "#172033", "#253246", "#3B4A5E"}
        neutral_backgrounds = root_backgrounds | surface_backgrounds | footer_backgrounds | {"#FBFBFD", "#F8FAFC"}

        def parent_background(widget):
            try:
                candidate = str(widget.master.cget("bg"))
            except Exception:
                candidate = surface
            return candidate if candidate in {root_bg, surface, footer} else surface

        def visit(widget):
            try:
                cls = widget.winfo_class()
                current_bg = str(widget.cget("bg"))
                if cls == "Frame":
                    if widget is self.root or current_bg in root_backgrounds:
                        widget.configure(bg=root_bg)
                    elif current_bg in footer_backgrounds:
                        widget.configure(bg=footer)
                    elif current_bg in surface_backgrounds:
                        widget.configure(bg=surface)
                elif cls == "Label":
                    current_fg = str(widget.cget("fg"))
                    if current_fg in neutral_fgs:
                        widget.configure(fg=text if current_fg != "#6B7280" else muted)
                    if current_bg in neutral_backgrounds:
                        widget.configure(bg=parent_background(widget))
                elif cls == "Text":
                    widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg)
                    if widget is getattr(self, "log_box", None):
                        widget.tag_configure("normal", foreground=input_fg)
                        widget.tag_configure("ok", foreground="#2E7D32")
                        widget.tag_configure("skip", foreground="#2E7D32")
                        widget.tag_configure("error", foreground="#C00000")
                        widget.tag_configure("info", foreground="#2F75B5")
                elif cls == "Listbox":
                    widget.configure(bg=input_bg, fg=input_fg, selectbackground=theme.get("select", "#DBEAFE"), selectforeground=input_fg)
                elif cls == "Entry":
                    widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg, readonlybackground=input_bg)
            except Exception:
                pass
            try:
                for child in widget.winfo_children():
                    visit(child)
            except Exception:
                pass
        visit(self.root)
        apply_button_style_to_tree(self.root, theme)
        self._apply_queue_and_log_colors(theme)
        if hasattr(self, "clone_progress"):
            self.clone_progress.set_theme(
                surface_color(theme, "progress_track", theme.get("border", "#CBD5E1")),
                surface_color(theme, "progress_clone", theme.get("select", "#2563EB")),
                surface,
            )
        if hasattr(self, "dub_progress"):
            self.dub_progress.set_theme(
                surface_color(theme, "progress_track", theme.get("border", "#CBD5E1")),
                surface_color(theme, "progress_dub", "#7C3AED"),
                surface,
            )
        if hasattr(self, "audio_player"):
            self.audio_player.apply_theme(theme)
        if hasattr(self, "dependencies_button"):
            self.start_tool_alert()

    def _apply_queue_and_log_colors(self, theme):
        """Mantém texto legível na lista e no log em todos os temas."""
        dark_theme = theme.get("mode") in {"medio", "escuro"}
        input_bg = theme.get("input", theme.get("surface", "#FFFFFF"))
        input_fg = "#FFFFFF" if dark_theme else theme.get("input_text", "#1F2937")
        select_fg = "#FFFFFF" if dark_theme else theme.get("input_text", "#1F2937")
        if hasattr(self, "queue_list"):
            self.queue_list.configure(bg=input_bg, fg=input_fg, selectbackground=theme.get("select", "#DBEAFE"), selectforeground=select_fg)
            for index in range(self.queue_list.size()):
                self.queue_list.itemconfig(index, foreground=input_fg)
        if hasattr(self, "log_box"):
            log_colors = {
                "normal": input_fg,
                "ok": "#86EFAC" if dark_theme else "#2E7D32",
                "skip": "#86EFAC" if dark_theme else "#2E7D32",
                "error": "#FCA5A5" if dark_theme else "#C00000",
                "info": "#93C5FD" if dark_theme else "#2F75B5",
            }
            self.log_box.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg)
            for tag, color in log_colors.items():
                self.log_box.tag_configure(tag, foreground=color)

    def _set_audio_conversion_progress(self, current: int, total: int, status: str = "", reset: bool = False):
        if not hasattr(self, "audio_conversion_progress"):
            return
        try:
            previous = 0.0 if reset else float(self.audio_conversion_progress.cget("value"))
            fraction = 100.0 if total <= 0 else max(0.0, min(100.0, float(current) / float(total) * 100.0))
            value = fraction if reset else max(previous, fraction)
            self.audio_conversion_progress.configure(mode="determinate", value=value)
            self.audio_conversion_status_var.set(status or (f"Conversão WAV: {int(current)}/{int(total)}" if total else ""))
            self.root.update_idletasks()
        except (tk.TclError, ValueError, TypeError):
            pass

    def _pending_reference_audio(self) -> list[Path]:
        pending = [Path(path) for path in (*self.pending_wav_audio, *self.pending_non_wav_audio) if Path(path).is_file()]
        unique: list[Path] = []
        seen: set[str] = set()
        for path in pending:
            key = os.path.normcase(str(path.resolve()))
            if key not in seen:
                seen.add(key)
                unique.append(path)
        return sorted(unique, key=lambda item: str(item).casefold())

    def prompt_initial_reference_preparation(self):
        try:
            if not self.root.winfo_exists() or self.initial_conversion_prompted or not self._pending_reference_audio():
                return
        except Exception:
            return
        self.initial_conversion_prompted = True
        self._prepare_non_wav_audio()

    def prompt_initial_non_wav_conversion(self):
        # Nome antigo mantido para compatibilidade com testes e chamadas externas.
        self.prompt_initial_reference_preparation()

    def retry_pending_audio_conversion(self):
        if not self._pending_reference_audio() or executable_path("ffmpeg", ROOT) is None:
            return
        self.initial_conversion_prompted = False
        self.root.after(80, self.prompt_initial_reference_preparation)

    def notify_project_audio_refresh(self):
        callback = self.project_actions.get("refresh_review")
        if callable(callback):
            try:
                callback()
            except Exception:
                pass

    def _prepare_non_wav_audio(self):
        pending = self._pending_reference_audio()
        if not pending:
            self.pending_non_wav_audio = []
            self.pending_wav_audio = []
            return False
        non_wav = [path for path in pending if not is_wav_path(path)]
        wav_to_adjust = [path for path in pending if is_wav_path(path)]
        if executable_path("ffmpeg", ROOT) is None:
            self._set_audio_conversion_progress(0, len(pending), "Aguardando FFmpeg portátil", reset=True)
            text = "Há áudio(s) que precisam do perfil OmniVoice. Clique em BAIXAR / PREPARAR FERRAMENTAS para continuar."
            if hasattr(self, "status_var"):
                self.status_var.set(text)
            if hasattr(self, "message_queue"):
                self.emit_log(text, "error")
            return False
        details = [
            f"Foram encontrados {len(pending)} áudio(s) que ainda não estão no perfil de referência do OmniVoice.",
            f"WAVs que serão reajustados e substituídos: {len(wav_to_adjust)}.",
            f"Formatos que serão convertidos para WAV: {len(non_wav)}.",
            "O perfil será WAV PCM 16-bit, 24 kHz e mono.",
            f"Antes da substituição, os WAVs atuais serão copiados para WAV ORIGINAIS/{OMNIVOICE_BACKUP_DIR_NAME}.",
            "Deseja preparar esses áudios para Voice Cloning?",
        ]
        if not messagebox.askyesno("Converter áudios para WAV", "\n\n".join(details), parent=self.root):
            self.pending_non_wav_audio = []
            self.pending_wav_audio = []
            self._set_audio_conversion_progress(0, len(pending), "Preparação OmniVoice cancelada", reset=True)
            self.initial_audio_conversion_errors.append("A preparação OmniVoice foi recusada; os áudios foram mantidos sem substituição.")
            return False
        self._set_audio_conversion_progress(0, len(pending), f"Preparando OmniVoice: 0/{len(pending)}", reset=True)
        converted: list[Path] = []
        conversion_errors: list[str] = []
        remaining_non_wav: list[Path] = []
        remaining_wav: list[Path] = []
        for index, path in enumerate(pending, start=1):
            try:
                if is_wav_path(path):
                    wav_path = self._normalize_wav_in_place(path)
                else:
                    wav_path = self._convert_to_wav(path)
                converted.append(wav_path)
                archived = archive_source_audio(path)
                if archived is not None:
                    conversion_errors.append(f"Formato original arquivado: {archived.parent.name}/{archived.name}.")
            except Exception as exc:
                conversion_errors.append(f"Não foi possível preparar {path.name} para OmniVoice: {exc}")
                (remaining_wav if is_wav_path(path) else remaining_non_wav).append(path)
            finally:
                self._set_audio_conversion_progress(index, len(pending), f"Preparando OmniVoice: {index}/{len(pending)}")
        self.pending_non_wav_audio = remaining_non_wav
        self.pending_wav_audio = remaining_wav
        rebuilt = find_audio_by_stem()
        self.audio_by_stem = {stem: path for stem, path in rebuilt.items() if is_wav_path(path)}
        self.text_by_stem = find_text_by_stem()
        self.stems = sorted(set(self.audio_by_stem) & set(self.text_by_stem), key=str.casefold)
        self.run_stems = list(self.stems)
        if hasattr(self, "statuses"):
            self.statuses = {stem: self.statuses.get(stem, "pendente") for stem in self.stems}
        if hasattr(self, "queue_list"):
            self.populate_queue()
        for error in conversion_errors:
            if hasattr(self, "message_queue"):
                self.emit_log(error, "info" if "arquivado" in error else "error")
        if converted:
            self._set_audio_conversion_progress(len(pending), len(pending), f"Preparação OmniVoice concluída: {len(converted)}/{len(pending)}")
            if hasattr(self, "status_var"):
                self.status_var.set(f"{len(converted)} áudio(s) preparado(s): WAV PCM 16-bit, 24 kHz, mono.")
            self.notify_project_audio_refresh()
            return True
        if conversion_errors and hasattr(self, "status_var"):
            self.status_var.set("Nenhum áudio pôde ser preparado para o perfil OmniVoice.")
        return False

    def _backup_wav_before_replace(self, source: Path) -> Path:
        audio_root = AUDIO_DIR.resolve()
        backup_root = audio_root / OMNIVOICE_BACKUP_DIR_NAME
        try:
            relative = Path(source).resolve().relative_to(audio_root)
            backup_dir = backup_root / relative.parent
        except ValueError:
            backup_dir = backup_root
        backup_dir.mkdir(parents=True, exist_ok=True)
        destination = backup_dir / Path(source).name
        if destination.exists():
            destination = _unique_archive_destination(Path(source), backup_dir)
        shutil.copy2(source, destination)
        return destination

    def _reference_output_path(self, source: Path) -> Path:
        source = Path(source).expanduser().resolve()
        audio_root = AUDIO_DIR.resolve()
        try:
            source.relative_to(audio_root)
            destination_dir = source.parent.parent if is_format_archive_dir(source.parent) else source.parent
        except ValueError:
            destination_dir = audio_root
        destination_dir.mkdir(parents=True, exist_ok=True)
        return destination_dir / f"{audio_stem(source)}.wav"

    def _transcode_reference(self, source: Path, destination: Path) -> None:
        ffmpeg = executable_path("ffmpeg", ROOT)
        if not ffmpeg:
            raise RuntimeError("FFmpeg não está disponível. Use BAIXAR / PREPARAR FERRAMENTAS e tente novamente.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.stem}.omnivoice_tmp_{os.getpid()}.wav")
        try:
            command = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
                "-ar", str(OMNIVOICE_REFERENCE_SAMPLE_RATE),
                "-ac", str(OMNIVOICE_REFERENCE_CHANNELS),
                "-c:a", OMNIVOICE_REFERENCE_CODEC, str(temporary),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False, **hidden_process_kwargs())
            if completed.returncode != 0 or not temporary.is_file():
                detail = (completed.stderr or "sem detalhes").strip().splitlines()[-1]
                raise RuntimeError(detail)
            temporary.replace(destination)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _normalize_wav_in_place(self, source: Path) -> Path:
        source = Path(source).expanduser().resolve()
        if not is_wav_path(source):
            raise ValueError(f"A fonte não é WAV: {source.name}")
        destination = self._reference_output_path(source)
        backup = self._backup_wav_before_replace(source)
        if destination.exists() and destination.resolve() != source.resolve():
            raise RuntimeError(f"Já existe outro WAV com o nome de saída {destination.name}; cópia de segurança criada em {backup}.")
        self._transcode_reference(source, destination)
        if source.resolve() != destination.resolve():
            try:
                source.relative_to(AUDIO_DIR.resolve())
            except ValueError:
                # Arquivos externos são copiados para o projeto, nunca removidos sem autorização.
                return destination
            try:
                source.unlink()
            except OSError as exc:
                raise RuntimeError(f"WAV ajustado, mas não foi possível remover a fonte antiga: {exc}") from exc
        return destination

    def _convert_to_wav(self, source: Path) -> Path:
        source = Path(source).expanduser().resolve()
        destination = self._reference_output_path(source)
        if destination.exists() and destination.resolve() != source.resolve():
            if is_wav_path(destination) and not wav_needs_omnivoice_adjustment(destination):
                return destination
            raise RuntimeError(f"Já existe outro arquivo com o nome de saída {destination.name}.")
        self._transcode_reference(source, destination)
        return destination

    def _merge_audio_paths(self, paths: list[Path], source_label: str = "Arquivos carregados"):
        for path in paths:
            path = Path(path).expanduser().resolve()
            if not path.is_file() or not is_wav_path(path):
                continue
            try:
                stem = relative_scene_key(path, AUDIO_DIR)
            except Exception:
                stem = audio_stem(path)
            current = self.audio_by_stem.get(stem)
            if current is None or not is_wav_path(current) or path == current:
                self.audio_by_stem[stem] = path
        self.stems = sorted(set(self.audio_by_stem) & set(self.text_by_stem), key=str.casefold)
        self.run_stems = list(self.stems)
        self.statuses = {stem: self.statuses.get(stem, "pendente") for stem in self.stems}
        self.populate_queue()
        self.status_var.set(f"{len(paths)} áudio(s) WAV carregado(s) de {source_label}.")

    def load_audio_paths(self, paths: list[Path], source_label: str = "Arquivos carregados"):
        unique: list[Path] = []
        seen: set[str] = set()
        for raw_path in paths:
            path = Path(raw_path).expanduser().resolve()
            if (
                not path.is_file()
                or path.suffix.casefold() not in AUDIO_EXTENSIONS
                or is_internal_omnivoice_backup(path)
                or is_format_archive_dir(path.parent)
            ):
                continue
            key = os.path.normcase(str(path))
            if key not in seen:
                seen.add(key)
                unique.append(path)
        if not unique:
            self.status_var.set("Nenhum formato de áudio compatível foi encontrado.")
            return
        wav_paths = [path for path in unique if is_wav_path(path)]
        non_wav = [path for path in unique if not is_wav_path(path)]
        wav_to_adjust = [path for path in wav_paths if wav_needs_omnivoice_adjustment(path)]
        ready_wav = [path for path in wav_paths if path not in wav_to_adjust]
        self._merge_audio_paths(ready_wav, source_label)
        pending = [*wav_to_adjust, *non_wav]
        if not pending:
            return
        if self.audio_conversion_thread is not None and self.audio_conversion_thread.is_alive():
            self.status_var.set("Aguarde a preparação de áudio atual terminar.")
            return
        if executable_path("ffmpeg", ROOT) is None:
            self.status_var.set("FFmpeg não está disponível. Clique em BAIXAR / PREPARAR FERRAMENTAS e tente novamente.")
            self.emit_log("Preparação não iniciada: FFmpeg ausente; use BAIXAR / PREPARAR FERRAMENTAS.", "error")
            return
        if not messagebox.askyesno(
            "Converter áudios para WAV",
            f"{len(pending)} áudio(s) ainda não estão no perfil de referência OmniVoice.\n\nWAVs que serão reajustados: {len(wav_to_adjust)}.\nFormatos que serão convertidos para WAV: {len(non_wav)}.\n\nDeseja preparar em WAV PCM 16-bit, 24 kHz e mono?",
            parent=self.root,
        ):
            self.status_var.set(f"{len(ready_wav)} áudio(s) WAV carregado(s); preparação cancelada para os demais.")
            return
        self._set_audio_conversion_progress(0, len(pending), f"Preparando OmniVoice: 0/{len(pending)}", reset=True)
        self.status_var.set(f"Preparando {len(pending)} áudio(s) para OmniVoice...")
        self.audio_conversion_thread = threading.Thread(target=self._convert_dropped_audio_worker, args=(pending, source_label), daemon=True)
        self.audio_conversion_thread.start()

    def _convert_dropped_audio_worker(self, paths: list[Path], source_label: str):
        converted: list[Path] = []
        errors: list[str] = []
        total = len(paths)
        self.message_queue.put(("audio_conversion_progress", 0, total, "Preparando OmniVoice: 0/" + str(total)))
        for index, path in enumerate(paths, start=1):
            try:
                wav_path = self._normalize_wav_in_place(path) if is_wav_path(path) else self._convert_to_wav(path)
                converted.append(wav_path)
                archived = archive_source_audio(path)
                if archived is not None:
                    errors.append(f"Formato original arquivado em {archived.parent.name}/{archived.name}.")
            except Exception as exc:
                errors.append(f"Não foi possível converter {path.name} para WAV: {exc}")
            self.message_queue.put(("audio_conversion_progress", index, total, f"Preparando OmniVoice: {index}/{total}"))
        self.message_queue.put(("audio_conversion_done", converted, errors, source_label))

    def enable_drag_drop(self, widget):
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", lambda event: self.handle_drop(event.data))
        except Exception:
            pass

    def handle_drop(self, raw: str):
        found: list[Path] = []
        for path in parse_drop_paths(raw, self.root):
            if path.is_dir():
                try:
                    found.extend(
                        candidate for candidate in path.rglob("*")
                        if candidate.is_file()
                        and candidate.suffix.casefold() in AUDIO_EXTENSIONS
                        and not is_internal_omnivoice_backup(candidate)
                        and not is_format_archive_dir(candidate.parent)
                    )
                except (OSError, PermissionError):
                    continue
            elif path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS:
                found.append(path)
        self.load_audio_paths(found, "Arraste")

    def missing_tools(self) -> list[str]:
        return [name for name in ("ffmpeg", "ffprobe", "ffplay") if executable_path(name, ROOT) is None]

    def show_tools_help(self):
        messagebox.showinfo(
            "Ferramentas de áudio",
            "Esta aba usa FFmpeg para preparar as referências do OmniVoice em WAV PCM 16-bit, 24 kHz e mono, FFprobe para verificar o perfil e FFplay para ouvir cenas. Formatos como MP3 e OGG são convertidos para WAV; WAVs fora do perfil também são reajustados.\n\nUse BAIXAR / PREPARAR FERRAMENTAS para instalar os binários portáteis quando eles não estiverem no PATH.",
            parent=self.root,
        )

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
        if hasattr(self, "dependencies_button"):
            try:
                apply_button_style(self.dependencies_button, self.theme, "teal")
            except Exception:
                pass

    def start_tool_alert(self):
        if not hasattr(self, "dependencies_button"):
            return
        missing = self.missing_tools()
        if not missing or self.dependencies_running:
            self.stop_tool_alert()
            return
        if self.tool_alert_after_id is None:
            self.tool_alert_until = time.monotonic() + 2.0
            self.tool_alert_on = False
            self.tool_alert_tick()
        if hasattr(self, "status_var"):
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
        return ROOT / TOOLS_DIR_NAME

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

    def start_dependency_setup(self):
        if self.dependencies_running:
            return
        if self.missing_tools() == []:
            self.download_progress.stop()
            self.download_progress.configure(mode="determinate", value=100)
            self.download_status_var.set("FFmpeg, FFprobe e FFplay já estão disponíveis.")
            return
        self.dependencies_running = True
        self.dependencies_button.configure(state="disabled")
        self.download_progress.stop()
        self.download_progress.configure(mode="determinate", value=0)
        self.download_status_var.set("Preparando FFmpeg, FFprobe e FFplay...")
        self.dependency_thread = threading.Thread(target=self.dependency_worker, daemon=True)
        self.dependency_thread.start()

    def dependency_worker(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="dublaskizon_batch_tools_"))
        try:
            if os.name != "nt":
                self.message_queue.put(("download_progress", "FFmpeg", 1, 1))
                self.message_queue.put(("dependencies_done", "Neste sistema, use FFmpeg/FFprobe/FFplay instalados no PATH."))
                return
            tools_dir = self.tool_storage_dir()
            tools_dir.mkdir(parents=True, exist_ok=True)
            archive_path = temp_dir / "ffmpeg.zip"
            request = urllib.request.Request(FFMPEG_WINDOWS_URL, headers={"User-Agent": "Dublaskizon/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as output:
                header = response.headers.get("Content-Length")
                total = int(header) if header and header.isdigit() else 0
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    self.message_queue.put(("download_progress", "FFmpeg", downloaded, total))
            extracted = temp_dir / "extracted"
            self.safe_extract_zip(archive_path, extracted)
            wanted = {"ffmpeg.exe", "ffprobe.exe", "ffplay.exe"}
            copied = set()
            for candidate in extracted.rglob("*"):
                if candidate.is_file() and candidate.name.casefold() in wanted:
                    shutil.copy2(candidate, tools_dir / candidate.name)
                    copied.add(candidate.name.casefold())
                    for sibling in candidate.parent.iterdir():
                        if sibling.is_file() and sibling.suffix.casefold() == ".dll":
                            shutil.copy2(sibling, tools_dir / sibling.name)
            if copied != wanted:
                raise RuntimeError("O pacote baixado não continha todos os executáveis do FFmpeg.")
            self.message_queue.put(("download_progress", "FFmpeg", 1, 1))
            self.message_queue.put(("dependencies_done", "FFmpeg, FFprobe e FFplay preparados na pasta ferramentas_audio."))
        except Exception as exc:
            self.message_queue.put(("dependencies_done", f"Falha ao preparar ferramentas: {exc}"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def apply_language(self, _language=None):
        self.audio_count_var.set(f"{i18n.tr('Áudios carregados:')} {len(self.audio_by_stem)} | {i18n.tr('Cenas prontas:')} {len(self.stems)}")
        if self.download_status_var.get() == "Ferramentas: não verificadas":
            self.download_status_var.set(i18n.tr("Ferramentas: não verificadas"))

    def display_model(self, label, model_id):
        cache = "cache local" if model_is_cached(model_id) else "download sob demanda"
        return f"{label} [{cache}]"

    def selected_r_pronunciation_id(self) -> str:
        variable = getattr(self, "r_pronunciation_var", None)
        raw_value = variable.get() if variable is not None else getattr(self, "selected_r_pronunciation", R_PRONUNCIATION_CHOICES[0][0])
        source_value = i18n.source_text(str(raw_value))
        for label, mode_id in R_PRONUNCIATION_CHOICES:
            if source_value == label or str(raw_value) == mode_id:
                return mode_id
        return R_PRONUNCIATION_CHOICES[0][1]

    def selected_model_id(self):
        selected = self.model_var.get()
        for label, model_id in self.model_choices:
            if selected.startswith(label):
                return model_id
        return self.model_choices[0][1]

    def selected_mode_id(self):
        selected = i18n.source_text(self.mode_var.get())
        for label, mode_id in MODE_CHOICES:
            if selected == label:
                return mode_id
        return MODE_CHOICES[0][1]

    def refresh_model_choices(self):
        """Atualiza o combobox com modelos encontrados no cache local."""
        selected_id = None
        if hasattr(self, "model_combo"):
            selected_id = self.selected_model_id()
        self.model_choices = discover_model_choices()
        values = [self.display_model(label, model_id) for label, model_id in self.model_choices]
        if hasattr(self, "model_combo"):
            self.model_combo.configure(values=values)
        selected_model_id = selected_id if selected_id in {model_id for _label, model_id in self.model_choices} else self.model_choices[0][1]
        chosen_label = next(label for label, model_id in self.model_choices if model_id == selected_model_id)
        self.model_var.set(self.display_model(chosen_label, selected_model_id))
        self.update_model_info()
        if hasattr(self, "append_log"):
            self.append_log(f"Catálogo de modelos atualizado: {len(self.model_choices)} modelo(s) disponível(is).", "info")

    def update_model_info(self):
        model_id = self.selected_model_id()
        if model_is_cached(model_id):
            self.model_info_var.set(f"Modelo detectado no cache local: {model_id}")
        else:
            self.model_info_var.set(f"Compatível; será baixado sob demanda se necessário: {model_id}")

    def update_mode_info(self):
        mode_id = self.selected_mode_id()
        if mode_id == "clone":
            self.mode_info_var.set("Mais indicado para dublagem: replica a voz do WAV de referência.")
            self.instruct_entry.configure(state="disabled")
            self.voice_profile_combo.configure(state="disabled")
            self.character_voices_button.configure(state="disabled")
        elif mode_id == "design":
            self.mode_info_var.set("Cria a voz escolhida; pode usar perfis diferentes por personagem.")
            self.instruct_entry.configure(state="normal")
            self.voice_profile_combo.configure(state="readonly")
            self.character_voices_button.configure(state="normal")
        else:
            self.mode_info_var.set("Automática ou uma voz escolhida; aceita perfis por personagem.")
            self.instruct_entry.configure(state="normal")
            self.voice_profile_combo.configure(state="readonly")
            self.character_voices_button.configure(state="normal")

    def bind_combo_click_only(self, combo):
        combo.bind("<MouseWheel>", lambda _event: "break")
        combo.bind("<Button-4>", lambda _event: "break")
        combo.bind("<Button-5>", lambda _event: "break")

    def on_model_changed(self, _event=None):
        self.update_model_info()

    def on_mode_changed(self, _event=None):
        self.update_mode_info()

    def open_character_voice_selector(self):
        characters = sorted({character_from_stem(stem) for stem in self.stems}, key=str.casefold)
        if not characters:
            messagebox.showwarning("Vozes por personagem", "Nenhum personagem foi identificado nos nomes dos áudios.", parent=self.root)
            return
        window = Toplevel(self.root)
        window.title("Escolher voz por personagem")
        window.transient(self.root.winfo_toplevel())
        window.grab_set()
        Label(window, text="Escolha uma voz para cada personagem identificado", font=("Segoe UI", 11, "bold"), padx=12, pady=10).grid(row=0, column=0, columnspan=2, sticky="w")
        variables: dict[str, StringVar] = {}
        for row, character in enumerate(characters, start=1):
            Label(window, text=character, font=("Segoe UI", 9, "bold"), padx=12, pady=4).grid(row=row, column=0, sticky="w")
            variable = StringVar(value=self.character_voice_profiles.get(character, self.voice_profile_var.get()))
            variables[character] = variable
            combo = ttk.Combobox(window, textvariable=variable, values=list(VOICE_PROFILES), state="readonly", width=48)
            combo.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=4)
            self.bind_combo_click_only(combo)

        def save_and_close():
            self.character_voice_profiles = {character: variable.get() for character, variable in variables.items()}
            self.save_voice_settings()
            self.status_var.set(f"Vozes configuradas para {len(variables)} personagem(ns).")
            window.destroy()

        save_button = Button(window, text="SALVAR VOZES", command=save_and_close, relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=6, cursor="hand2")
        apply_button_style(save_button, getattr(self, "theme", {}), "success")
        save_button.grid(row=len(characters) + 1, column=0, columnspan=2, pady=12)
        window.columnconfigure(1, weight=1)

    def voice_instruction_for_stem(self, stem: str) -> tuple[str, str]:
        character = character_from_stem(stem)
        profile_name = self.character_voice_profiles.get(character, self.voice_profile_var.get())
        base = VOICE_PROFILES.get(profile_name, "")
        complement = getattr(self, "selected_instruct", "")
        if not complement and hasattr(self, "instruct_var"):
            complement = self.instruct_var.get().strip()
        if not base:
            # Auto realmente automático: não força Voice Design.
            if self.selected_mode == "auto":
                return "", profile_name
            return complement, profile_name
        instruction = ", ".join(part for part in (base, complement) if part)
        return instruction, profile_name

    def set_generation_controls(self, state):
        self.model_combo.configure(state="readonly" if state == "normal" else "disabled")
        self.mode_combo.configure(state="readonly" if state == "normal" else "disabled")
        voice_enabled = self.selected_mode_id() in {"design", "auto"}
        self.instruct_entry.configure(state=state if voice_enabled else "disabled")
        self.voice_profile_combo.configure(state="readonly" if state == "normal" and voice_enabled else "disabled")
        self.character_voices_button.configure(state=state if voice_enabled else "disabled")
        if hasattr(self, "r_pronunciation_combo"):
            self.r_pronunciation_combo.configure(state="readonly" if state == "normal" else "disabled")

    def build_ui(self):
        self.root.configure(bg="#F5F6FA")
        header = Frame(self.root, bg="#F5F6FA")
        header.pack(fill="x", padx=16, pady=(14, 8))
        Label(header, text="CLONAR + DUBLAR", font=("Segoe UI", 18, "bold"), bg="#F5F6FA", fg="#1F2937").pack(anchor="w")
        project_line = Frame(header, bg="#F5F6FA")
        project_line.pack(fill="x", pady=(3, 0))
        Label(project_line, text="Projeto:", font=("Segoe UI", 9), bg="#F5F6FA", fg="#5B6472").pack(side="left")
        self.project_entry = Entry(project_line, font=("Segoe UI", 9), relief="flat", bd=0, readonlybackground="#F5F6FA", fg="#334155", width=110)
        self.project_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.project_entry.insert(0, str(ROOT))
        self.project_entry.configure(state="readonly")

        top = Frame(self.root, bg="#F5F6FA")
        top.pack(fill="x", padx=16, pady=(0, 8))
        Label(top, textvariable=self.current_var, font=("Segoe UI", 12, "bold"), bg="#F5F6FA", fg="#26364A").pack(side="left", fill="x", expand=True)
        project_actions = Frame(top, bg="#F5F6FA")
        project_actions.pack(side="right")
        Button(project_actions, text="SELECIONAR PROJETO", command=self.project_actions.get("select_project", lambda: None), bg="#2563EB", activebackground="#1D4ED8", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5, cursor="hand2").pack(side="left", padx=(4, 0))
        Button(project_actions, text="USAR PASTA DO EXE", command=self.project_actions.get("use_exe_folder", lambda: None), bg="#475569", activebackground="#334155", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5, cursor="hand2").pack(side="left", padx=(4, 0))
        Button(project_actions, text="TUTORIAL PDF", command=self.project_actions.get("tutorial", lambda: None), bg="#D97706", activebackground="#B45309", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5, cursor="hand2").pack(side="left", padx=(4, 0))

        options = Frame(self.root, bg="#FFFFFF", bd=1, relief="solid")
        options.pack(fill="x", padx=16, pady=(0, 8))
        model_header = Frame(options, bg="#FFFFFF")
        model_header.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=(9, 2))
        Label(model_header, text="Ferramenta / modelo", bg="#FFFFFF", fg="#26364A", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.refresh_models_button = Button(model_header, text="ATUALIZAR", command=self.refresh_model_choices, bg="#64748B", activebackground="#475569", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 7, "bold"), padx=6, pady=2, cursor="hand2")
        self.refresh_models_button.pack(side="right")
        self.model_combo = ttk.Combobox(options, textvariable=self.model_var, values=[self.display_model(label, model) for label, model in self.model_choices], state="readonly", width=42)
        self.model_combo.grid(row=1, column=0, sticky="ew", padx=(10, 6), pady=(0, 8))
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_changed)
        self.bind_combo_click_only(self.model_combo)
        Label(options, textvariable=self.model_info_var, bg="#FFFFFF", fg="#6B7280", font=("Segoe UI", 8)).grid(row=2, column=0, sticky="w", padx=(10, 6), pady=(0, 8))

        Label(options, text="Modo de geração", bg="#FFFFFF", fg="#26364A", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=6, pady=(9, 2))
        self.mode_combo = ttk.Combobox(options, textvariable=self.mode_var, values=[label for label, _mode in MODE_CHOICES], state="readonly", width=42)
        self.mode_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 8))
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_changed)
        self.bind_combo_click_only(self.mode_combo)
        Label(options, textvariable=self.mode_info_var, bg="#FFFFFF", fg="#6B7280", font=("Segoe UI", 8)).grid(row=2, column=1, sticky="w", padx=6, pady=(0, 8))

        Label(options, text="Quem fará a voz", bg="#FFFFFF", fg="#26364A", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=6, pady=(9, 2))
        voice_choice = Frame(options, bg="#FFFFFF")
        voice_choice.grid(row=1, column=2, sticky="ew", padx=6, pady=(0, 8))
        self.voice_profile_combo = ttk.Combobox(voice_choice, textvariable=self.voice_profile_var, values=list(VOICE_PROFILES), state="disabled", width=31)
        self.voice_profile_combo.pack(side="left", fill="x", expand=True)
        self.bind_combo_click_only(self.voice_profile_combo)
        self.character_voices_button = Button(voice_choice, text="POR PERSONAGEM", command=self.open_character_voice_selector, bg="#7C3AED", activebackground="#6D28D9", fg="white", relief="flat", font=("Segoe UI", 7, "bold"), padx=6, pady=3, cursor="hand2", state="disabled")
        self.character_voices_button.pack(side="left", padx=(5, 0))
        Label(options, text="Escolha uma voz geral ou configure Gray, Trishka, Ishi etc.", bg="#FFFFFF", fg="#6B7280", font=("Segoe UI", 8)).grid(row=2, column=2, sticky="w", padx=6, pady=(0, 8))

        Label(options, text="Pronúncia do R", bg="#FFFFFF", fg="#26364A", font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w", padx=6, pady=(9, 2))
        self.r_pronunciation_combo = ttk.Combobox(options, textvariable=self.r_pronunciation_var, values=[label for label, _mode_id in R_PRONUNCIATION_CHOICES], state="readonly", width=18)
        self.r_pronunciation_combo.grid(row=1, column=3, sticky="ew", padx=6, pady=(0, 8))
        self.bind_combo_click_only(self.r_pronunciation_combo)
        Label(options, text="Suaviza ou reforça o R na síntese.", bg="#FFFFFF", fg="#6B7280", font=("Segoe UI", 8)).grid(row=2, column=3, sticky="w", padx=6, pady=(0, 8))

        Label(options, text="Complemento da voz (opcional)", bg="#FFFFFF", fg="#26364A", font=("Segoe UI", 9, "bold")).grid(row=0, column=4, sticky="w", padx=6, pady=(9, 2))
        self.instruct_entry = ttk.Entry(options, textvariable=self.instruct_var, width=36)
        self.instruct_entry.grid(row=1, column=4, sticky="ew", padx=(6, 10), pady=(0, 8))
        Label(options, text="Ex.: sotaque, emoção, idade, intensidade ou estilo.", bg="#FFFFFF", fg="#6B7280", font=("Segoe UI", 8)).grid(row=2, column=4, sticky="w", padx=(6, 10), pady=(0, 8))
        options.grid_columnconfigure(0, weight=1)
        options.grid_columnconfigure(1, weight=1)
        options.grid_columnconfigure(2, weight=1)
        options.grid_columnconfigure(3, weight=1)
        options.grid_columnconfigure(4, weight=1)
        main = Frame(self.root, bg="#F5F6FA")
        main.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.main_pane = ttk.PanedWindow(main, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True)

        left = Frame(self.main_pane, bg="white", bd=1, relief="solid", width=270)
        left.pack_propagate(False)
        self.main_pane.add(left, weight=1)

        scenes_header = Frame(left, bg="white")
        scenes_header.pack(fill="x", padx=10, pady=(10, 4))
        Label(scenes_header, text="Cenas / processos", font=("Segoe UI", 11, "bold"), bg="white", fg="#26364A").pack(side="left")
        self.audio_count_label = Label(scenes_header, textvariable=self.audio_count_var, font=("Segoe UI", 7, "bold"), bg="white", fg="#64748B", anchor="e")
        self.audio_count_label.pack(side="right", padx=(4, 0))
        Button(scenes_header, text="A-Z", command=lambda: self.sort_scenes("alphabetical"), bg="#475569", fg="white", relief="flat", padx=6, pady=2, cursor="hand2").pack(side="right", padx=(3, 0))
        Button(scenes_header, text="1-9", command=lambda: self.sort_scenes("numeric"), bg="#2563EB", fg="white", relief="flat", padx=6, pady=2, cursor="hand2").pack(side="right")
        list_frame = Frame(left, bg="white")
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.queue_list = Listbox(list_frame, exportselection=False, activestyle="none", font=("Segoe UI", 9), borderwidth=0, highlightthickness=0)
        list_scroll = Scrollbar(list_frame, orient="vertical", command=self.queue_list.yview)
        self.queue_list.configure(yscrollcommand=list_scroll.set)
        self.queue_list.pack(side="left", fill="both", expand=True)
        list_scroll.pack(side="right", fill="y")
        self.queue_list.bind("<Double-Button-1>", self.play_selected_scene)
        self.queue_list.bind("<Button-3>", self.show_scene_context_menu)
        self.enable_drag_drop(self.queue_list)
        self.enable_drag_drop(left)
        audio_controls = Frame(left, bg="white")
        audio_controls.pack(fill="x", padx=8, pady=(0, 8))
        self.play_scene_button = Button(audio_controls, text="▶ OUVIR CENA", command=self.play_selected_scene, bg="#0F766E", activebackground="#115E59", fg="white", relief="flat", padx=8, pady=4, cursor="hand2")
        self.play_scene_button.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.play_all_button = Button(audio_controls, text="▶ OUVIR TODOS", command=self.play_all_scenes, bg="#7C3AED", activebackground="#6D28D9", fg="white", relief="flat", padx=8, pady=4, cursor="hand2")
        self.play_all_button.pack(side="left", fill="x", expand=True, padx=(3, 0))
        self.redub_button = Button(left, text="REDUBLAR ÁUDIO SELECIONADO", command=self.redub_selected_scene, bg="#DC2626", activebackground="#B91C1C", fg="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5, cursor="hand2")
        self.redub_button.pack(fill="x", padx=8, pady=(0, 8))

        right = Frame(self.main_pane, bg="white", bd=1, relief="solid")
        self.main_pane.add(right, weight=4)
        scene_header = Frame(right, bg="white")
        scene_header.pack(fill="x", padx=14, pady=(10, 4))
        Label(scene_header, text="Progresso da cena", font=("Segoe UI", 11, "bold"), bg="white", fg="#26364A").pack(side="left")
        self.dependencies_button = Button(scene_header, text="BAIXAR / PREPARAR FERRAMENTAS", command=self.start_dependency_setup, relief="flat", font=("Segoe UI", 7, "bold"), padx=5, pady=2, cursor="hand2")
        apply_button_style(self.dependencies_button, self.theme, "teal")
        self.dependencies_button.pack(side="right", padx=(5, 0))
        self.tools_help_button = Button(scene_header, text="?", command=self.show_tools_help, relief="flat", font=("Segoe UI", 8, "bold"), width=2, padx=0, pady=2, cursor="hand2")
        apply_button_style(self.tools_help_button, self.theme, "secondary")
        self.tools_help_button.pack(side="right", padx=(4, 0))
        HoverTooltip(self.tools_help_button, "FFmpeg: converte formatos para WAV e participa do processamento.\n\nFFprobe: consulta duração, frequência e canais.\n\nFFplay: reproduz a cena no player interno.")
        self.download_progress = ttk.Progressbar(scene_header, orient="horizontal", mode="determinate", maximum=100, value=0, length=125, style="BatchDownload.Horizontal.TProgressbar")
        self.download_progress.pack(side="right", padx=(4, 0))
        Label(scene_header, textvariable=self.download_status_var, bg="white", fg="#64748B", font=("Segoe UI", 7), anchor="e").pack(side="right", padx=(4, 0))
        self.audio_conversion_progress = ttk.Progressbar(scene_header, orient="horizontal", mode="determinate", maximum=100, value=0, length=105, style="BatchConversion.Horizontal.TProgressbar")
        self.audio_conversion_progress.pack(side="right", padx=(4, 0))
        Label(scene_header, textvariable=self.audio_conversion_status_var, bg="white", fg="#2563EB", font=("Segoe UI", 7), anchor="e").pack(side="right", padx=(4, 0))

        progress_frame = Frame(right, bg="white")
        progress_frame.pack(fill="x", padx=14, pady=(2, 10))
        Label(progress_frame, text="Clonagem / referência", bg="white", fg="#2F75B5", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.clone_progress = RoundedProgress(progress_frame, width=560, height=22, track="#E7EEF8", fill="#2F75B5")
        self.clone_progress.pack(fill="x", pady=(3, 8))
        Label(progress_frame, text="Dublagem / síntese", bg="white", fg="#8E6BBE", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.dub_progress = RoundedProgress(progress_frame, width=560, height=22, track="#F0EAF7", fill="#9B7BC5")
        self.dub_progress.pack(fill="x", pady=(3, 3))
        Label(progress_frame, text="Azul = referência/clonagem   Lilás = fala em português   Verde = cena pulada/concluída", bg="white", fg="#6B7280", font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))

        controls = Frame(right, bg="white")
        controls.pack(fill="x", padx=14, pady=(0, 10))
        self.pause_button = Button(controls, text="Pausar", command=self.toggle_pause, bg="#6B7280", fg="white", relief="flat", padx=12, pady=5)
        self.pause_button.pack(side="left", padx=(0, 6))
        self.stop_button = Button(controls, text="Parar após cena", command=self.stop_after_scene, bg="#D97706", fg="white", relief="flat", padx=12, pady=5)
        self.stop_button.pack(side="left", padx=(0, 6))
        self.cancel_button = Button(controls, text="Cancelar", command=self.cancel_run, bg="#C00000", fg="white", relief="flat", padx=12, pady=5)
        self.cancel_button.pack(side="left")
        self.start_button = Button(controls, text="INICIAR DUBLAGEM", command=self.start_run, bg="#C00000", activebackground="#8B0000", fg="white", activeforeground="white", font=("Segoe UI", 11, "bold"), relief="flat", padx=22, pady=10, cursor="hand2")
        self.start_button.pack(side="right")

        log_label = Frame(right, bg="white")
        log_label.pack(fill="x", padx=14)
        Label(log_label, text="Processos e mensagens", font=("Segoe UI", 10, "bold"), bg="white", fg="#26364A").pack(side="left")
        self.log_box = Text(right, height=16, wrap="word", state="disabled", font=("Consolas", 9), bg="#FBFBFD", fg="#374151", relief="flat", borderwidth=0)
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self.log_box.tag_configure("normal", foreground="#374151")
        self.log_box.tag_configure("ok", foreground="#2E7D32")
        self.log_box.tag_configure("skip", foreground="#2E7D32")
        self.log_box.tag_configure("error", foreground="#C00000")
        self.log_box.tag_configure("info", foreground="#2F75B5")

        folder_bar = Frame(self.root, bg="#F5F6FA")
        folder_bar.pack(fill="x", padx=16, pady=(0, 6))
        self.make_folder_button(folder_bar, "WAV ORIGINAL", AUDIO_DIR, "#2F75B5").pack(side="left", padx=(0, 5))
        self.make_folder_button(folder_bar, "WAV DUBLADO", OUTPUT_DIR, "#9B7BC5").pack(side="left", padx=5)
        self.make_folder_button(folder_bar, "REVISÕES", ROOT / "revisoes", "#3A7D44").pack(side="left", padx=5)
        self.make_folder_button(folder_bar, "TXT PT", TEXT_DIR, "#D97706").pack(side="left", padx=5)
        self.make_folder_button(folder_bar, "TXT ORIGINAL", ROOT / "TXT TEXTO ORIGINAL", "#475569").pack(side="left", padx=5)
        self.make_folder_button(folder_bar, "TXT TRANSCRITO", ROOT / "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO", "#0F766E").pack(side="left", padx=5)
        self.make_folder_button(folder_bar, "OUTRAS TRADUÇÕES", ROOT / "OUTRAS TRADUÇÕES", "#7C3AED").pack(side="left", padx=5)

        result_bar = Frame(self.root, bg="#E8EDF5", bd=1, relief="solid")
        result_bar.pack(fill="x", padx=16, pady=(0, 12))

        left_status = Frame(result_bar, bg="#E8EDF5")
        left_status.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=9)
        Label(left_status, textvariable=self.elapsed_var, bg="#E8EDF5", fg="#1F2937", font=("Segoe UI", 11, "bold")).pack(side="left")
        Label(left_status, textvariable=self.status_var, bg="#E8EDF5", fg="#334155", font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=(18, 0))
        Label(left_status, textvariable=self.eta_var, bg="#E8EDF5", fg="#475569", font=("Segoe UI", 11), anchor="w").pack(side="left", padx=(18, 0))

        right_status = Frame(result_bar, bg="#E8EDF5")
        right_status.pack(side="right", padx=(8, 12), pady=9)
        self.finish_banner = Label(right_status, textvariable=self.finish_banner_var, font=("Segoe UI", 14, "bold"), bg="#E8EDF5", fg="#2E7D32", anchor="e")
        self.finish_banner.pack(side="left", padx=(0, 20))
        Label(right_status, textvariable=self.summary_var, bg="#E8EDF5", fg="#172033", font=("Segoe UI", 11, "bold"), anchor="e").pack(side="left")

    def scene_playback_path(self, stem: str) -> Path | None:
        dubbed = OUTPUT_DIR / f"{stem}.wav"
        if dubbed.is_file():
            return dubbed
        return self.audio_by_stem.get(stem)

    def _scene_stem_from_context_event(self, event):
        """Seleciona somente a linha sob o botão direito e retorna sua chave de cena."""
        if not self.stems or not hasattr(self, "queue_list"):
            return None
        try:
            index = int(self.queue_list.nearest(event.y))
            bounds = self.queue_list.bbox(index)
        except (AttributeError, tk.TclError, TypeError, ValueError):
            return None
        if not bounds or not (bounds[1] <= event.y < bounds[1] + bounds[3]) or index >= len(self.stems):
            return None
        self.queue_list.selection_clear(0, END)
        self.queue_list.selection_set(index)
        self.queue_list.see(index)
        return self.stems[index]

    def _context_audio_paths(self, stem: str):
        original = self.audio_by_stem.get(stem)
        dubbed = OUTPUT_DIR / f"{stem}.wav"
        return original if original is not None and original.is_file() else None, dubbed if dubbed.is_file() else None

    def open_scene_audio_folder(self, stem: str | None = None, kind: str = "dubbed") -> None:
        stem = stem or (self.stems[self.queue_list.curselection()[0]] if self.queue_list.curselection() else None)
        if not stem:
            self.status_var.set("Selecione uma cena para acessar o local do áudio.")
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
        stem = stem or (self.stems[self.queue_list.curselection()[0]] if self.queue_list.curselection() else None)
        if not stem:
            self.status_var.set("Selecione uma cena para copiar o nome do áudio.")
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
        try:
            self.queue_list.selection_clear(0, END)
            self.queue_list.selection_set(target)
            self.queue_list.activate(target)
            self.queue_list.see(target)
        except Exception:
            pass

    def _fixed_r_pronunciation_for_review(self) -> str:
        return self.selected_r_pronunciation_id()

    def load_scene_text_for_player(self, stem):
        key = str(stem or "")
        path = self.text_by_stem.get(key) if key else None
        if path is None and key:
            candidate = TEXT_DIR / f"{key}.txt"
            path = candidate if candidate.is_file() else None
        if path is None:
            return {"text": "", "path": None, "title": f"Áudio: {Path(key).name if key else 'não selecionado'}"}
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            text = ""
        return {"text": text, "path": path, "title": f"Áudio: {Path(key).name}.wav"}

    def save_scene_text_from_player(self, stem, text):
        key = str(stem or "")
        new_text = str(text or "").strip()
        if not key:
            return False, "Nenhuma cena selecionada."
        if not new_text:
            return False, "Digite algum texto antes de salvar a alteração."
        text_file = self.text_by_stem.get(key) or (TEXT_DIR / f"{key}.txt")
        try:
            text_file.parent.mkdir(parents=True, exist_ok=True)
            text_file.write_text(new_text + "\n", encoding="utf-8")
            self.text_by_stem[key] = text_file
            self.emit_log(f"Texto em português salvo pela janela OUVIR CENA: {text_file}", "ok")
            return True, f"Texto salvo em {text_file.name}."
        except OSError as exc:
            self.emit_log(f"ERRO ao salvar texto pela janela OUVIR CENA: {exc}", "error")
            return False, f"Não foi possível salvar o texto: {exc}"

    def append_review_process_message(self, stem, text, tag="info", section="REVISÃO") -> None:
        """Mostra no Processos e Mensagens o conteúdo contextual vindo da Revisão."""
        if not hasattr(self, "log_box"):
            return
        stem_label = str(stem or "cena atual")
        lines = str(text).splitlines() or [""]
        try:
            self.log_box.configure(state="normal")
            for line in lines:
                self.log_box.insert(END, f"[REVISÃO — {section}] {stem_label}: {line}\n", tag)
            self.log_box.see(END)
            self.log_box.configure(state="disabled")
        except Exception:
            pass

    def _sync_review_regeneration_progress(self, stem, clone, dub, phase, done=False, success=False) -> None:
        """Espelha REFAZER CENA nas barras da cena, quando a fila Batch está parada."""
        if self.running or not stem or stem not in self.stems:
            return
        try:
            clone_value = max(0.0, min(1.0, float(clone) / 100.0 if float(clone) > 1.0 else float(clone)))
            dub_value = max(0.0, min(1.0, float(dub) / 100.0 if float(dub) > 1.0 else float(dub)))
        except (TypeError, ValueError):
            return
        self.current_stem = stem
        self.current_var.set(f"REFAZENDO: {stem}")
        self.clone_progress.set(clone_value)
        self.dub_progress.set(dub_value)
        self.status_var.set(f"{stem}: {phase}")
        progress_state = (stem, str(phase), bool(done), bool(success))
        if progress_state != getattr(self, "review_regen_last_progress_state", None):
            self.review_regen_last_progress_state = progress_state
            progress_tag = "ok" if done and success else "error" if done else "info"
            self.append_review_process_message(stem, f"{phase} — clonagem: {clone_value * 100:.1f}% | dublagem: {dub_value * 100:.1f}%", progress_tag, "REFAZENDO A CENA")
        marker = "[REVISADA]" if done and success else "[ERRO REVISÃO]" if done else "[REFAZENDO]"
        marker_state = (stem, marker)
        if marker_state != self.review_regen_marker_state:
            color = "#2E7D32" if marker == "[REVISADA]" else "#C00000" if marker == "[ERRO REVISÃO]" else "#7C3AED"
            self.update_queue_item(stem, marker, color)
            self.review_regen_marker_state = marker_state

    def set_review_audio_target(self, review_app) -> None:
        """Mostra ações da Revisão na janela de áudio aberta pelo Batch."""
        self.review_audio_target = review_app
        if review_app is None:
            self.audio_player.set_scene_integration(self._sync_audio_player_selection)
            self.audio_player.set_scene_text_integration(self.load_scene_text_for_player, self.save_scene_text_from_player)
            self.audio_player.set_review_snapshot_provider(None)
            return
        actions = {
            "open_audacity": lambda stem: review_app.run_audio_review_action(stem, "open_audacity"),
            "approve": lambda stem: review_app.run_audio_review_action(stem, "approve"),
            "reject": lambda stem: review_app.run_audio_review_action(stem, "reject"),
            "redub": lambda stem: review_app.run_audio_review_action(stem, "redub"),
            "redub_other": lambda stem: review_app.run_audio_review_action(stem, "redub_other"),
        }
        self.audio_player.set_scene_integration(self._sync_audio_player_selection, actions)
        self.audio_player.set_scene_text_integration(review_app.load_scene_text_for_player, review_app.save_scene_text_from_player)
        self.audio_player.set_review_snapshot_provider(getattr(review_app, "player_review_snapshot", None))
        if hasattr(review_app, "set_player_refresh_callback"):
            review_app.set_player_refresh_callback(self.audio_player.refresh_current_scene)
        if hasattr(review_app, "set_process_message_callback"):
            review_app.set_process_message_callback(self.append_review_process_message)
            if getattr(review_app, "stems", None) and getattr(review_app, "current_stem", lambda: None)():
                review_app.update_history(review_app.current_stem())
        if hasattr(review_app, "set_regeneration_progress_callback"):
            review_app.set_regeneration_progress_callback(self._sync_review_regeneration_progress)
        if hasattr(review_app, "set_fixed_r_pronunciation_provider"):
            review_app.set_fixed_r_pronunciation_provider(self._fixed_r_pronunciation_for_review)
        self.audio_player.set_review_preferences({
            "auto_open_var": review_app.auto_open_var,
            "auto_open_command": review_app.toggle_auto_open,
            "request_r_var": review_app.request_r_var,
            "request_r_command": review_app.toggle_r_request,
        })

    def play_selected_scene(self, _event=None):
        selection = self.queue_list.curselection()
        if not selection or not self.stems:
            return
        index = int(selection[0])
        if index >= len(self.stems):
            return
        stem = self.stems[index]
        path = self.scene_playback_path(stem)
        if path is None:
            return
        # Não chama scene_playback_path para todas as cenas. Os vizinhos são
        # representados pelos caminhos de saída esperados e resolvidos apenas ao
        # navegar, deixando a abertura imediata mesmo com milhares de itens.
        playlist = [OUTPUT_DIR / f"{scene_stem}.wav" for scene_stem in self.stems]
        playlist[index] = path
        self.audio_player.play_one(path, f"OUVIR CENA — {stem}", playlist=playlist, index=index, scene_key=stem, scene_keys=self.stems)

    def play_all_scenes(self):
        pairs = [(stem, self.scene_playback_path(stem)) for stem in self.stems]
        pairs = [(stem, path) for stem, path in pairs if path is not None]
        self.audio_player.play_all([path for _stem, path in pairs], "OUVIR TODOS — CENAS / PROCESSOS", scene_keys=[stem for stem, _path in pairs])

    def sort_scenes(self, mode: str):
        self.sort_mode = mode
        self.stems.sort(key=natural_key if mode == "numeric" else str.casefold)
        self.populate_queue()

    def redub_selected_scene(self):
        if self.running:
            messagebox.showwarning("Redublagem", "Aguarde o processo atual terminar.", parent=self.root)
            return
        selection = self.queue_list.curselection()
        if not selection or int(selection[0]) >= len(self.stems):
            messagebox.showwarning("Redublagem", "Selecione um áudio na lista.", parent=self.root)
            return
        stem = self.stems[int(selection[0])]
        if not messagebox.askyesno("Redublar áudio", f"Redublar somente {stem}?\n\nO WAV dublado atual será substituído.", parent=self.root):
            return
        self.run_stems = [stem]
        self.force_overwrite = True
        self.start_run()

    def scene_display_name(self, stem: str) -> str:
        path = self.audio_by_stem.get(stem)
        return path.name if path is not None else f"{Path(stem).name}.wav"

    def populate_queue(self):
        self.audio_count_var.set(f"{i18n.tr('Áudios carregados:')} {len(self.audio_by_stem)} | {i18n.tr('Cenas prontas:')} {len(self.stems)}")
        self.queue_list.delete(0, END)
        if not self.stems:
            self.queue_list.insert(END, i18n.tr("Nenhum par de wav + txt encontrado."))
            empty_color = "#FFFFFF" if self.theme.get("mode") in {"medio", "escuro"} else "#C00000"
            self.queue_list.itemconfig(0, foreground=empty_color)
            return
        queue_color = "#FFFFFF" if self.theme.get("mode") in {"medio", "escuro"} else self.theme.get("input_text", "#374151")
        for index, stem in enumerate(self.stems):
            self.queue_list.insert(END, f"[ ] {self.scene_display_name(stem)}")
            self.queue_list.itemconfig(index, foreground=queue_color)
        missing_text = sorted(set(self.audio_by_stem) - set(self.text_by_stem))
        missing_audio = sorted(set(self.text_by_stem) - set(self.audio_by_stem))
        if missing_text:
            self.emit_log("AVISO: áudio sem TXT: " + ", ".join(missing_text), "error")
        if missing_audio:
            self.emit_log("AVISO: TXT sem áudio: " + ", ".join(missing_audio), "error")
        self.emit_log(f"{len(self.stems)} pares válidos encontrados.", "info")
        self.emit_log(f"Saída: {OUTPUT_DIR}", "info")

    def emit_log(self, text, tag="normal"):
        self.message_queue.put(("log", text, tag))

    def _log_central(self, text, tag="normal") -> None:
        callback = getattr(self, "central_log_callback", None)
        if callable(callback):
            try:
                callback("CLONAGEM + DUBLAGEM", str(text), tag)
            except Exception:
                pass

    def update_queue_item(self, stem, marker, color):
        if stem not in self.stems:
            return
        index = self.stems.index(stem)
        self.queue_list.delete(index)
        self.queue_list.insert(index, f"{marker} {self.scene_display_name(stem)}")
        queue_color = "#FFFFFF" if self.theme.get("mode") in {"medio", "escuro"} else color
        self.queue_list.itemconfig(index, foreground=queue_color)
        self.queue_list.selection_clear(0, END)
        self.queue_list.selection_set(index)
        self.queue_list.see(index)

    def poll_messages(self):
        try:
            while True:
                message = self.message_queue.get_nowait()
                self.handle_message(message)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_messages)

    def handle_message(self, message):
        kind = message[0]
        if kind == "log":
            _, text, tag = message
            self.append_log(text, tag)
        elif kind == "download_progress":
            _, description, downloaded, total = message
            percent = update_download_progress(self.download_progress, description, downloaded, total)
            if total:
                self.download_status_var.set(f"Baixando {description}: {percent:.1f}%")
            else:
                self.download_status_var.set(f"Baixando {description}: {percent:.1f}% estimado")
        elif kind == "dependencies_done":
            _, text = message
            self.dependencies_running = False
            self.dependency_thread = None
            self.dependencies_button.configure(state="normal")
            self.download_progress.stop()
            if self.missing_tools():
                self.download_progress.configure(mode="determinate", value=max(0.0, float(self.download_progress.cget("value"))))
                self.download_status_var.set(str(text))
                self.start_tool_alert()
            else:
                self.download_progress.configure(mode="determinate", value=100)
                self.download_status_var.set(str(text))
                self.stop_tool_alert()
                self.retry_pending_audio_conversion()
        elif kind == "audio_conversion_progress":
            _, current, total, description = message
            self._set_audio_conversion_progress(int(current), int(total), str(description))
        elif kind == "audio_conversion_done":
            _, converted, errors, source_label = message
            self.audio_conversion_thread = None
            self._merge_audio_paths(converted, source_label)
            for error in errors:
                self.append_log(error, "error")
            if converted:
                self._set_audio_conversion_progress(max(1, len(converted)), max(1, len(converted)), f"Preparação OmniVoice concluída: {len(converted)} áudio(s)")
                self.status_var.set(f"{len(converted)} áudio(s) preparado(s) para OmniVoice e carregado(s).")
            elif errors:
                self.status_var.set("Nenhum áudio não-WAV pôde ser convertido para WAV.")
        elif kind == "started":
            _, stem, number, total = message
            self.current_stem = stem
            self.current_var.set(f"[{number}/{total}] {stem}")
            self.status_var.set("Preparando referência e clonagem...")
            self.clone_progress.set(0.10)
            self.dub_progress.set(0.02)
            self.update_queue_item(stem, "[CLONANDO]", "#2F75B5")
            self.animate_dub_progress()
        elif kind == "stage":
            _, stem, stage, fraction = message
            if stage == "clone":
                self.clone_progress.set(fraction)
                self.status_var.set(f"{stem}: clonando/preparando referência...")
            elif stage == "dub":
                self.clone_progress.set(1.0)
                self.dub_progress.set(fraction)
                self.status_var.set(f"{stem}: dublando em português...")
        elif kind == "skipped":
            _, stem = message
            self.statuses[stem] = "pulada"
            self.clone_progress.set(1.0)
            self.dub_progress.set(1.0)
            self.update_queue_item(stem, "[PULADO]", "#2E7D32")
            self.counts["pulados"] += 1
        elif kind == "success":
            _, stem = message
            self.statuses[stem] = "ok"
            self.clone_progress.set(1.0)
            self.dub_progress.set(1.0)
            self.update_queue_item(stem, "[OK]", "#2E7D32")
            self.counts["gerados"] += 1
            self.status_var.set(f"Concluído: {stem}")
            try:
                self.audio_player.refresh_current_scene(stem)
            except Exception:
                pass
        elif kind == "error":
            _, stem, text = message
            self.statuses[stem] = "erro"
            self.update_queue_item(stem, "[ERRO]", "#C00000")
            self.counts["falhas"] += 1
            self.status_var.set(f"Erro em {stem}")
            self.append_log(text, "error")
        elif kind == "finished":
            _, reason = message
            self.running = False
            self.current_process = None
            self.stop_progress_animation()
            self.finish_clock()
            self.pause_button.configure(text="Pausar")
            self.start_button.configure(state="normal")
            self.set_generation_controls("normal")
            self.status_var.set(reason)
            self.summary_var.set(f"Gerados: {self.counts['gerados']} | Pulados: {self.counts['pulados']} | Falhas: {self.counts['falhas']}")
            if reason == "Fila finalizada." and self.counts["falhas"] == 0:
                self.finish_banner_var.set("PRONTOS — FILA FINALIZADA")
                self.finish_banner.configure(fg="#2E7D32")
            elif self.counts["falhas"] > 0:
                self.finish_banner_var.set("FINALIZADO COM ERROS")
                self.finish_banner.configure(fg="#C00000")
            elif "cancelada" in reason.lower():
                self.finish_banner_var.set("CANCELADO")
                self.finish_banner.configure(fg="#C00000")
            else:
                self.finish_banner_var.set("PARADO")
                self.finish_banner.configure(fg="#D97706")
            self.append_log(reason, "ok" if self.counts["falhas"] == 0 else "error")

    def update_clock(self):
        if self.run_started_at is None:
            return
        self.last_elapsed_seconds = max(0.0, time.monotonic() - self.run_started_at)
        completed = self.counts["gerados"] + self.counts["pulados"] + self.counts["falhas"]
        total = len(self.stems)
        self.elapsed_var.set(f"Tempo decorrido: {format_duration(self.last_elapsed_seconds)}")
        if completed > 0 and total > completed:
            average = self.last_elapsed_seconds / completed
            remaining = max(0.0, average * (total - completed))
            self.eta_var.set(f"Tempo restante estimado: {format_duration(remaining)}")
        elif completed >= total and total > 0:
            self.eta_var.set("Tempo restante estimado: 00:00:00")
        else:
            self.eta_var.set("Tempo restante estimado: calculando...")
        if self.running:
            self.clock_after_id = self.root.after(500, self.update_clock)

    def finish_clock(self):
        if self.run_started_at is not None:
            self.last_elapsed_seconds = max(0.0, time.monotonic() - self.run_started_at)
        self.elapsed_var.set(f"Tempo decorrido: {format_duration(self.last_elapsed_seconds)}")
        self.eta_var.set("Tempo restante estimado: 00:00:00")
        if self.clock_after_id:
            self.root.after_cancel(self.clock_after_id)
            self.clock_after_id = None
        self.run_started_at = None

    def append_log(self, text, tag="normal"):
        self._log_central(text, tag)
        self.log_box.configure(state="normal")
        self.log_box.insert(END, i18n.tr(str(text)).rstrip() + "\n", tag)
        self.log_box.see(END)
        self.log_box.configure(state="disabled")

    def animate_dub_progress(self):
        if not self.running or not self.current_stem:
            return
        current = self.dub_progress.fraction
        if current < 0.90:
            self.dub_progress.set(current + 0.008)
            self.stage_after_id = self.root.after(250, self.animate_dub_progress)

    def stop_progress_animation(self):
        if self.stage_after_id:
            self.root.after_cancel(self.stage_after_id)
            self.stage_after_id = None

    def start_run(self):
        if self.running:
            if self.paused:
                self.toggle_pause()
            return
        if self.audio_conversion_thread is not None and self.audio_conversion_thread.is_alive():
            messagebox.showwarning("Conversão em andamento", "Aguarde a conversão dos áudios para WAV terminar antes de iniciar a dublagem.", parent=self.root)
            return
        if self._pending_reference_audio():
            if executable_path("ffmpeg", ROOT) is None:
                messagebox.showwarning(
                    "Converter áudios para WAV",
                    "Há áudio(s) que ainda não estão no perfil OmniVoice aguardando preparação.\n\nClique primeiro em BAIXAR / PREPARAR FERRAMENTAS; depois clique novamente em INICIAR DUBLAGEM.",
                    parent=self.root,
                )
                return
            if not self._prepare_non_wav_audio():
                return
        if not self.stems:
            messagebox.showwarning("Fila vazia", "Não encontrei pares com o mesmo nome-base em wav e txt.", parent=self.root)
            return
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            probe = OUTPUT_DIR / ".write_test.tmp"
            probe.write_text("ok", encoding="ascii")
            probe.unlink()
        except OSError as exc:
            self.append_log(f"ERRO: não foi possível gravar em {OUTPUT_DIR}: {exc}", "error")
            messagebox.showerror("Pasta de saída", f"Não foi possível gravar em:\n{OUTPUT_DIR}\n\n{exc}")
            return

        self.infer_prefix = find_omnivoice_command()
        if not self.infer_prefix:
            messagebox.showerror("OmniVoice não encontrado", "Não encontrei o comando omnivoice-infer. Instale o pacote OmniVoice ou defina a variável OMNIVOICE_INFER com o caminho do executável.", parent=self.root)
            self.append_log("ERRO: omnivoice-infer não foi encontrado.", "error")
            return
        self.selected_model = self.selected_model_id()
        self.selected_mode = self.selected_mode_id()
        self.selected_instruct = self.instruct_var.get().strip()
        self.selected_r_pronunciation = self.selected_r_pronunciation_id()
        selected_profile_instruction = VOICE_PROFILES.get(self.voice_profile_var.get(), "")
        if self.selected_mode == "design" and not self.selected_instruct and not selected_profile_instruction:
            messagebox.showwarning("Descrição vazia", "Informe uma descrição para Voice Design antes de iniciar.")
            return
        self.save_voice_settings()

        if not self.force_overwrite:
            self.run_stems = list(self.stems)
        self.running = True
        self.paused = False
        self.stop_after_current = False
        self.cancel_requested = False
        self.pause_event.set()
        self.counts = {"gerados": 0, "pulados": 0, "falhas": 0}
        self.run_started_at = time.monotonic()
        self.last_elapsed_seconds = 0.0
        self.finish_banner_var.set("")
        self.elapsed_var.set("Tempo decorrido: 00:00:00")
        self.eta_var.set("Tempo restante estimado: calculando...")
        self.start_button.configure(state="disabled")
        self.set_generation_controls("disabled")
        self.pause_button.configure(text="Pausar")
        mode_label = dict((mode_id, label) for label, mode_id in MODE_CHOICES).get(self.selected_mode, self.selected_mode)
        self.emit_log(f"Modelo selecionado: {self.selected_model}", "info")
        self.emit_log(f"Modo selecionado: {mode_label}", "info")
        pronunciation_label = next((label for label, mode_id in R_PRONUNCIATION_CHOICES if mode_id == self.selected_r_pronunciation), R_PRONUNCIATION_CHOICES[0][0])
        self.emit_log(f"Pronúncia do R: {pronunciation_label}", "info")
        self.status_var.set("Fila em execução...")
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)
        self.worker_thread.start()
        self.update_clock()

    def toggle_pause(self):
        if not self.running:
            return
        if not self.paused:
            self.paused = True
            self.pause_event.clear()
            self.pause_button.configure(text="Continuar")
            self.status_var.set("Pausado; a cena atual termina antes da pausa.")
            self.emit_log("PAUSADO: aguardando a cena atual terminar.", "info")
        else:
            self.paused = False
            self.pause_event.set()
            self.pause_button.configure(text="Pausar")
            self.status_var.set("Fila continuando...")
            self.emit_log("CONTINUANDO a fila.", "info")

    def stop_after_scene(self):
        if not self.running:
            return
        self.stop_after_current = True
        self.pause_event.set()
        self.status_var.set("Parada solicitada; não iniciarei outra cena.")
        self.emit_log("PARAR: a cena atual termina e a fila será encerrada.", "info")

    def cancel_run(self):
        if not self.running:
            self.close_window()
            return
        self.cancel_requested = True
        self.pause_event.set()
        process = self.current_process
        if process and process.poll() is None:
            try:
                process.terminate()
            except OSError as exc:
                self.emit_log(f"Não foi possível interromper o processo: {exc}", "error")
        self.status_var.set("Cancelamento solicitado...")
        self.emit_log("CANCELAR: interrompendo a cena atual e encerrando a fila.", "error")

    def build_infer_command(self, stem: str, text: str, output_file: Path) -> list[str]:
        r_mode = getattr(self, "selected_r_pronunciation", None) or self.selected_r_pronunciation_id()
        rendered_text = apply_r_pronunciation(text, r_mode)
        command = [
            *self.infer_prefix,
            "--model",
            self.selected_model,
            "--text",
            rendered_text,
            "--language",
            LANGUAGE,
        ]
        instruction = ""
        if self.selected_mode == "clone":
            command.extend(["--ref_audio", str(self.audio_by_stem[stem])])
            instruction = getattr(self, "selected_instruct", "")
        elif self.selected_mode in {"design", "auto"}:
            instruction, _profile_name = self.voice_instruction_for_stem(stem)
        # Não anexar frases livres de pronúncia: a versão instalada do
        # OmniVoice valida --instruct contra uma lista fechada de itens.
        r_instruction = r_pronunciation_instruction(r_mode)
        instruction = ", ".join(part for part in (instruction.strip(), r_instruction) if part)
        if instruction:
            command.extend(["--instruct", instruction])
        command.extend(["--output", str(output_file)])
        return command

    def omnivoice_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        ffmpeg_dir = find_ffmpeg_directory()
        if ffmpeg_dir:
            environment["PATH"] = str(ffmpeg_dir) + os.pathsep + environment.get("PATH", "")
            environment["FFMPEG_BINARY"] = str(ffmpeg_dir / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"))
        return environment

    def worker(self):
        active_stems = list(self.run_stems or self.stems)
        total = len(active_stems)
        for number, stem in enumerate(active_stems, start=1):
            self.pause_event.wait()
            if self.cancel_requested:
                break
            if self.stop_after_current and number > 1:
                break

            ref_audio = self.audio_by_stem[stem]
            text_file = self.text_by_stem[stem]
            output_file = OUTPUT_DIR / f"{stem}.wav"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            self.message_queue.put(("started", stem, number, total))
            self.emit_log(f"[{number}/{total}] {stem}: clonando referência e preparando dublagem.", "info")

            if output_file.exists() and not OVERWRITE and not self.force_overwrite:
                self.emit_log(f"[{number}/{total}] PULADO: já existe {output_file.name}.", "skip")
                self.message_queue.put(("skipped", stem))
                continue

            try:
                text = text_file.read_text(encoding="utf-8-sig").strip()
            except UnicodeDecodeError as exc:
                self.message_queue.put(("error", stem, f"[{number}/{total}] FALHA: TXT inválido em {text_file.name}: {exc}"))
                continue
            except OSError as exc:
                self.message_queue.put(("error", stem, f"[{number}/{total}] FALHA lendo {text_file.name}: {exc}"))
                continue

            if not text:
                self.emit_log(f"[{number}/{total}] PULADO: TXT vazio em {text_file.name}; preencha o texto para dublar.", "skip")
                self.message_queue.put(("skipped", stem))
                continue

            temporary_output_file = output_file.with_name(f".{output_file.stem}.__dublaskizon_tmp_{os.getpid()}_{threading.get_ident()}.wav")
            try:
                temporary_output_file.unlink(missing_ok=True)
            except OSError:
                pass
            command = self.build_infer_command(stem, text, temporary_output_file)
            if self.selected_mode in {"design", "auto"}:
                _instruction, profile_name = self.voice_instruction_for_stem(stem)
                self.emit_log(f"[{number}/{total}] voz de {character_from_stem(stem)}: {profile_name}", "info")
            self.emit_log(f"[{number}/{total}] dublando: {text_file.name} -> {output_file.name}", "info")
            try:
                self.current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=self.omnivoice_environment(), **hidden_process_kwargs())
                if self.current_process.stdout:
                    for raw_line in self.current_process.stdout:
                        line = raw_line.strip()
                        if line:
                            self.emit_log(line, "normal")
                            lower = line.lower()
                            if "loading model" in lower or "fetching" in lower:
                                self.message_queue.put(("stage", stem, "clone", 0.35))
                            elif "loading weights" in lower or "model loaded" in lower:
                                self.message_queue.put(("stage", stem, "clone", 0.72))
                            elif "asr model" in lower or "generating audio" in lower:
                                self.message_queue.put(("stage", stem, "clone", 1.0))
                                self.message_queue.put(("stage", stem, "dub", 0.18))
                            elif "saved to" in lower:
                                self.message_queue.put(("stage", stem, "dub", 1.0))
                return_code = self.current_process.wait()
            except Exception as exc:
                self.current_process = None
                self.message_queue.put(("error", stem, f"[{number}/{total}] FALHA ao iniciar OmniVoice: {exc}"))
                continue
            finally:
                self.current_process = None

            if self.cancel_requested:
                try:
                    temporary_output_file.unlink(missing_ok=True)
                except OSError:
                    pass
                
                self.emit_log(f"[{number}/{total}] CANCELADA: {stem}", "error")
                break
            if return_code == 0 and temporary_output_file.exists():
                try:
                    backup_path = _archive_dubbed_before_replace(stem, output_file)
                    os.replace(temporary_output_file, output_file)
                    self.message_queue.put(("success", stem))
                    self.emit_log(f"[{number}/{total}] OK: {output_file.name}", "ok")
                    if backup_path is not None:
                        self.emit_log(f"[{number}/{total}] Versão anterior preservada em revisoes: {backup_path.name}", "info")
                except Exception as exc:
                    try:
                        temporary_output_file.unlink(missing_ok=True)
                    except OSError:
                        pass
                    if "backup_path" in locals() and backup_path is not None:
                        try:
                            backup_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                    self.message_queue.put(("error", stem, f"[{number}/{total}] FALHA ao substituir o dublado: {exc}"))
            else:
                try:
                    temporary_output_file.unlink(missing_ok=True)
                except OSError:
                    pass

                self.message_queue.put(("error", stem, f"[{number}/{total}] FALHA: OmniVoice terminou com código {return_code} e não gerou o WAV esperado."))

            if self.stop_after_current:
                self.emit_log("Fila encerrada após a cena atual.", "info")
                break

        if self.cancel_requested:
            reason = "Fila cancelada."
        elif self.stop_after_current:
            reason = "Fila parada após a cena atual."
        else:
            reason = "Fila finalizada."
        self.message_queue.put(("finished", reason))
        self.run_stems = list(self.stems)
        self.force_overwrite = False

    def make_folder_button(self, parent, text: str, path: Path, color: str):
        return Button(parent, text=text, command=lambda: self.open_folder(path, text), bg=color, fg="white", activebackground=color, activeforeground="white", relief="flat", padx=9, pady=4, cursor="hand2")

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

    def open_review(self):
        if self.review_callback is not None:
            self.review_callback()
            self.append_log("Aba de revisão selecionada.", "info")
            return
        if not REVIEW_BAT.exists():
            messagebox.showwarning("Revisão", f"Não encontrei:\n{REVIEW_BAT}")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(REVIEW_BAT))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["bash", str(REVIEW_BAT)])
            else:
                subprocess.Popen(["bash", str(REVIEW_BAT)])
            self.append_log("Aba/janela de revisão aberta.", "info")
        except Exception as exc:
            messagebox.showerror("Revisão", str(exc))

    def close_window(self):
        if self.embedded:
            if self.running:
                self.cancel_run()
            return
        if self.running:
            answer = messagebox.askyesno("Sair", "A fila ainda está em execução. Cancelar e fechar?")
            if not answer:
                return
            self.cancel_run()
            self.root.after(400, self.root.destroy)
            return
        self.root.destroy()


def main() -> int:
    if not TK_AVAILABLE:
        print("ERRO: Tkinter não está disponível neste Python.")
        print(f"Detalhes: {TK_IMPORT_ERROR}")
        return 2
    root = Tk()
    try:
        ttk.Style(root).theme_use("clam")
    except Exception:
        pass
    BatchApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
