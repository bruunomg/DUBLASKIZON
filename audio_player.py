"""Reprodução de áudio portátil para o Dublaskizon.

Usa FFplay, distribuído com o FFmpeg, ou o reprodutor padrão do Windows, conforme a preferência global do aplicativo. O modo FFplay não abre janela de terminal.
"""

from __future__ import annotations
import audioop

import os
import math
import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
import weakref
from pathlib import Path

try:
    from .audio_clip_timeline import AudioClip, split_clip, move_clip, move_clip_group, render_clips, paste_clip
except ImportError:
    from audio_clip_timeline import AudioClip, split_clip, move_clip, move_clip_group, render_clips, paste_clip

try:
    import tkinter as tk
    from tkinter import Button, Canvas, DoubleVar, END, Frame, Label, Menu, Scrollbar, StringVar, Text, Toplevel, filedialog, messagebox, ttk
except ModuleNotFoundError:
    TK_AVAILABLE = False
    ttk = None  # type: ignore
    apply_button_style = None
    button_style = None
else:
    try:
        from .ui_theme import apply_button_style, button_style
    except ImportError:
        from ui_theme import apply_button_style, button_style
    TK_AVAILABLE = True

try:
    from . import i18n
except ImportError:
    import i18n


def hidden_process_kwargs() -> dict:
    if not sys.platform.startswith("win"):
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
    }


def play_wav_with_winsound(path: Path) -> bool:
    """Tenta reproduzir WAV de forma assíncrona para que PARAR possa interrompê-lo."""
    if not sys.platform.startswith("win") or path.suffix.casefold() not in {".wav", ".wave"}:
        return False
    try:
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC)
        return True
    except Exception:
        return False


def stop_winsound() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import winsound
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            winsound.PlaySound(None, 0)
    except Exception:
        pass


def reveal_in_file_manager(path: Path) -> bool:
    """Abre uma única janela na pasta pai de um arquivo absoluto existente."""
    path = Path(path).expanduser()
    # Exigir caminho absoluto evita que uma chave relativa seja resolvida a
    # partir do diretório atual do EXE, que poderia ser Documentos.
    if not path.is_absolute():
        return False
    path = path.resolve()
    if not path.is_file() or not path.parent.is_dir():
        return False
    target_dir = path.parent
    try:
        if sys.platform.startswith("win"):
            # Apenas uma chamada, sem /select e sem os.startfile no caminho
            # normal: o Explorer recebe explicitamente a pasta correta.
            subprocess.Popen(["explorer.exe", str(target_dir)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target_dir)])
        else:
            subprocess.Popen(["xdg-open", str(target_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def find_ffplay(project_root: Path | None = None) -> str | None:
    from shared_audio_tools import find_tool
    return find_tool('ffplay',project_root)


def process_scene_volume(track, decibels):
    """Uniform float64 PCM gain, capped at -1 dBFS sample peak; no compressor.

    Retains rate, channels, sample width, frame count and independent clip IDs.
    No noise/dither or lossy encoding is introduced; final PCM is rounded once.
    """
    import numpy as np
    decibels=float(decibels)
    if not math.isfinite(decibels) or not -24 <= decibels <= 24:
        raise ValueError("Ajuste de volume inválido.")
    width=int(track['sample_width']);channels=int(track['channels'])
    raw=track['frames']
    if width not in (1,2,3,4) or channels<1 or len(raw)%(width*channels):
        raise ValueError("Formato PCM inválido para ajustar volume.")
    if not raw:raise ValueError("Áudio vazio.")
    if width==1:
        samples=np.frombuffer(raw,dtype=np.uint8).astype(np.float64)-128
    elif width==3:
        packed=np.frombuffer(raw,dtype=np.uint8).reshape(-1,3).astype(np.int32)
        values=packed[:,0] | (packed[:,1]<<8) | (packed[:,2]<<16)
        samples=((values ^ 0x800000)-0x800000).astype(np.float64)
    else:
        samples=np.frombuffer(raw,dtype='<i'+str(width)).astype(np.float64)
    peak=float(np.max(np.abs(samples)))
    ceiling=math.floor(((1 << (width*8-1))-1)*10**(-1/20))
    requested=10**(decibels/20)
    gain=min(requested,max(1.0,ceiling/peak)) if decibels>0 and peak else requested
    applied=20*math.log10(gain) if peak else 0.0
    if peak==0 or abs(applied)<1e-9:
        return raw,tuple(track.get('clips') or (AudioClip(1,0,raw),)),0.0
    values=np.rint(samples*gain)
    if width==1:
        result=(values+128).astype(np.uint8).tobytes()
    elif width==3:
        values=values.astype(np.int32)
        packed=np.empty((len(values),3),dtype=np.uint8)
        for byte in range(3):packed[:,byte]=(values>>(8*byte)) & 255
        result=packed.tobytes()
    else:
        result=values.astype('<i'+str(width)).tobytes()
    result,clips=preserve_processed_clips(track,result)
    return result,clips,applied


def process_scene_internal_silence(track):
    """Remove long internal pauses; keep utterance margins and 60 ms separators."""
    import numpy as np
    from pydub import AudioSegment
    from personalized_dubbing_tab import _silero_speech_regions, _speech_regions, _protected_speech_regions
    audio = AudioSegment(data=track['frames'], sample_width=track['sample_width'],
                         frame_rate=track['sample_rate'], channels=track['channels'])
    mono = audio.set_channels(1).set_sample_width(2)
    pcm = np.frombuffer(mono.raw_data, dtype=np.int16)
    try:
        regions, _ = _silero_speech_regions(pcm, pcm, track['sample_rate'])
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        regions = _speech_regions(pcm, track['sample_rate'])
    if not regions:
        raise RuntimeError('Nenhuma fala detectada; silêncio não removido e edição preservada.')
    protection_pcm = pcm.copy()
    # Opposite stereo phases may cancel in mono; never delete that channel signal.
    channels_pcm = np.frombuffer(audio.set_sample_width(2).raw_data, dtype=np.int16).reshape(-1, track['channels'])
    protection_pcm = np.clip(np.max(np.abs(channels_pcm.astype(np.int32)),axis=1),0,32767).astype(np.int16)
    regions = _protected_speech_regions(protection_pcm, regions, track['sample_rate'])
    if not regions:
        raise RuntimeError('Nenhuma fala utilizável detectada; edição preservada.')
    frame_bytes = track['channels'] * track['sample_width']
    # This button removes only the middle gaps; preserve the outer edges.
    regions[0] = (0, regions[0][1]); regions[-1] = (regions[-1][0], len(pcm))
    silence = (b'\x80' if track['sample_width']==1 else b'\x00'*track['sample_width']) * track['channels']
    separator = silence * round(track['sample_rate'] * .06)
    return separator.join(track['frames'][a*frame_bytes:b*frame_bytes] for a,b in regions)


def process_scene_alignment(track, original):
    """Align an editor snapshot; never overwrite either source audio."""
    from personalized_dubbing_tab import _align_speech_regions, _ffmpeg_path
    from pydub import AudioSegment
    ffmpeg = _ffmpeg_path()
    if not ffmpeg or original is None:
        raise RuntimeError('Original e FFmpeg são necessários para organizar as ondas.')
    with tempfile.TemporaryDirectory(prefix='dublaskizon-organizar-') as folder:
        source, target = Path(folder)/'entrada.wav', Path(folder)/'saida.wav'
        AudioSegment(data=track['frames'], sample_width=track['sample_width'],
                     frame_rate=track['sample_rate'], channels=track['channels']).export(source, format='wav')
        if not _align_speech_regions(source, original, target, ffmpeg, max_change=100):
            raise RuntimeError('Não foi possível detectar fala nos dois áudios; edição preservada.')
        result = AudioSegment.from_file(target).set_frame_rate(track['sample_rate']).set_channels(track['channels']).set_sample_width(track['sample_width'])
        return result.raw_data


def process_exact_original_duration(track, project, seconds):
    rate=track['sample_rate'];width=track['channels']*track['sample_width']
    total=round(seconds*rate)
    if total<1 or not track['frames']:raise ValueError('Duração original ou áudio dublado indisponível.')
    current=len(track['frames'])//width
    silence=(b'\x80' if track['sample_width']==1 else b'\x00'*track['sample_width'])*track['channels']
    if current<=total:
        raw=track['frames']+silence*(total-current)
        return raw,tuple(track.get('clips') or (AudioClip(1,0,raw),))
    working=dict(track)
    while total/(len(working['frames'])//width)<.5:
        working['frames'],working['clips']=process_scene_audio(working,project,.5,preserve_clips=True)
    return process_scene_audio(working,project,total/(len(working['frames'])//width),preserve_clips=True)


def process_scene_audio(track: dict, project_root, duration_factor=None, preserve_clips=False):
    """Processa uma cópia PCM com os mesmos métodos do conversor de duração."""
    try:
        from .duration_converter_tab import DurationConverterApp
    except ImportError:
        from duration_converter_tab import DurationConverterApp
    converter = DurationConverterApp.__new__(DurationConverterApp)
    converter.project_root = project_root
    converter.append_log = lambda _text: None
    codecs = {1: "pcm_u8", 2: "pcm_s16le", 3: "pcm_s24le", 4: "pcm_s32le"}
    codec = codecs[track["sample_width"]]
    converter.output_format_args = lambda _format: ["-c:a", codec, "-ar", str(track["sample_rate"]), "-ac", str(track["channels"])]
    if duration_factor is not None and preserve_clips:
        if not math.isfinite(duration_factor) or not 0.5 <= duration_factor <= 2:
            raise ValueError("A duração deve ficar entre 50% e 200% da base deste ajuste.")
        frame_bytes=track['channels']*track['sample_width']
        if abs(duration_factor-1.0)<1e-10:
            return track['frames'],tuple(track.get('clips') or (AudioClip(1,0,track['frames']),))
        updated=[]
        total=round(len(track['frames'])/frame_bytes*duration_factor)
        silence=bytes([128])*frame_bytes if track['sample_width']==1 else bytes(frame_bytes)
        for clip in track.get('clips') or (AudioClip(1,0,track['frames']),):
            start=round(clip.start*duration_factor)
            end=round(clip.end(frame_bytes)*duration_factor)
            count=end-start
            if count<1:raise ValueError("Um trecho ficaria menor que uma amostra.")
            single=dict(track,frames=clip.pcm);single.pop('clips',None)
            # Exactly the converter's 'maior' engine, once per independent clip.
            raw=process_scene_audio(single,project_root,duration_factor,preserve_clips=False)
            raw=raw[:count*frame_bytes]
            raw+=silence*(count-len(raw)//frame_bytes)
            updated.append(AudioClip(clip.id,start,raw))
        return render_clips(updated,frame_bytes,track['sample_width'],total,max(total*frame_bytes,1)),tuple(updated)
    with tempfile.TemporaryDirectory(prefix="dublaskizon_scene_") as folder:
        folder = Path(folder)
        source = folder / "entrada.wav"
        with wave.open(str(source), "wb") as output:
            output.setnchannels(track["channels"])
            output.setsampwidth(track["sample_width"])
            output.setframerate(track["sample_rate"])
            output.writeframes(track["frames"])
        trim_start = 0
        if duration_factor is None:
            if preserve_clips:
                start, end = converter.detect_start_end_silence(source)
                frame_bytes = track["channels"] * track["sample_width"]
                trim_start = max(0, round(start * track["sample_rate"]))
                trim_end = min(len(track["frames"]) // frame_bytes, round(end * track["sample_rate"]))
                raw = track["frames"][trim_start*frame_bytes:trim_end*frame_bytes]
                if not raw:
                    raise ValueError("O corte retornou áudio vazio; a edição foi preservada.")
                return preserve_processed_clips(track, raw, trim_start=trim_start)
            target = converter.silence_trim(source, folder)
        else:
            duration = len(track["frames"]) / track["sample_width"] / track["channels"] / track["sample_rate"]
            if duration <= 0 or not 0.5 <= duration_factor <= 2:
                raise ValueError("Áudio vazio ou ajuste de duração inválido.")
            target = folder / "saida.wav"
            converter.convert_longer(source, target, duration * duration_factor, duration, folder, "wav")
        with wave.open(str(target), "rb") as result:
            if (result.getnchannels(), result.getsampwidth(), result.getframerate()) != (track["channels"], track["sample_width"], track["sample_rate"]):
                raise ValueError("O processamento alterou o formato PCM do áudio.")
            raw = result.readframes(result.getnframes())
        if not raw:
            raise ValueError("O processamento retornou áudio vazio; a edição foi preservada.")
        if preserve_clips:
            return preserve_processed_clips(track, raw, stretch=True)
        return raw


def preserve_processed_clips(track, raw, trim_start=0, stretch=False):
    """Reposiciona limites sem juntar IDs; mantém os intervalos como silêncio PCM."""
    frame_bytes = track["channels"] * track["sample_width"]
    total = len(raw) // frame_bytes
    original_total = len(track["frames"]) // frame_bytes
    ratio = total / original_total if stretch else 1.0
    clips = track.get("clips") or (AudioClip(1, 0, track["frames"]),)
    updated = []
    for clip in clips:
        start = max(0, min(total, round(clip.start * ratio) - trim_start))
        end = max(0, min(total, round(clip.end(frame_bytes) * ratio) - trim_start))
        if end > start:
            updated.append(AudioClip(clip.id, start, raw[start*frame_bytes:end*frame_bytes]))
        elif stretch:
            raise ValueError("Um trecho ficaria menor que uma amostra. A edição foi preservada.")
    if not updated:
        raise ValueError("Nenhum trecho permaneceu após o corte. A edição foi preservada.")
    result = render_clips(updated, frame_bytes, track["sample_width"], total, max(len(raw), 1))
    return result, tuple(updated)


_PLAYER_INSTANCES=weakref.WeakSet()

def set_global_playback_mode(root, mode):
    root._dublaskizon_playback_mode=mode
    for player in list(_PLAYER_INSTANCES):
        parent=player.parent
        while parent is not None and parent is not root:parent=getattr(parent,'master',None)
        if parent is root:player.set_playback_mode(mode)

class AudioPlayerManager:
    def __init__(self, parent, project_root: Path | None = None, status_callback=None):
        self.parent = parent
        self.project_root = Path(project_root).expanduser().resolve() if project_root else None
        self.status_callback = status_callback
        self.process = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.window = None
        self.window_status = None
        self.window_body = None
        self.window_content = None
        self.window_border_color = "#FACC15"
        self.pending_paths: list[Path] = []
        self.original_pending_paths: list[Path] = []
        self.dubbed_pending_paths: list[Path] = []
        self.pending_title = "OUVIR ÁUDIO"
        self.start_button = None
        self.original_button = None
        self.previous_button = None
        self.next_button = None
        self.navigation_paths: list[Path] = []
        self.original_navigation_paths: list[Path | None] = []
        self.dubbed_navigation_paths: list[Path | None] = []
        self._resolved_pair_indices: set[int] = set()
        self._project_audio_index: dict[str, dict[str, list[Path]]] = {}
        self._ffplay_path: str | None = None
        self.playback_mode = "ffplay"
        ancestor=parent
        while ancestor is not None:
            if hasattr(ancestor,'_dublaskizon_playback_mode'):
                self.playback_mode=ancestor._dublaskizon_playback_mode;break
            ancestor=getattr(ancestor,'master',None)
        _PLAYER_INSTANCES.add(self)
        self.current_source_kind = "unknown"
        self.dubbed_folder_name = "dublado"
        self.current_index = -1
        self.stop_button = None
        self.close_button = None
        self.review_preferences_frame = None
        self.review_controls_buttons = None
        self.review_action_buttons = []
        self.audio_action_buttons = []
        self.review_preference_widgets = []
        self.scene_text_loader = None
        self.scene_text_saver = None
        self.scene_text_title_var = None
        self.scene_text_status_var = None
        self.scene_text_box = None
        self.scene_text_save_button = None
        self.scene_text_path: Path | None = None
        self.waveform_canvases = {}
        self.waveform_duration_vars = {}
        self.waveform_data = {}
        self.waveform_panel = None
        self.waveform_split = None
        self.waveform_widgets = []
        self.review_top_row = None
        self.review_top_spacer = None
        self.review_top_panel = None
        self.waveform_duration_labels = {}
        self.waveform_reference_duration = 0.0
        self.waveform_zoom = 1.0
        self.waveform_scroll = 0.0
        self.waveform_zoom_var = None
        self.waveform_zoom_status = None
        self.waveform_scrollbar = None
        self.waveform_navigation = None
        self.waveform_vertical_view = None
        self.waveform_progress = {"original": 0.0, "dubbed": 0.0}
        self.waveform_active_kind: str | None = None
        self.waveform_active_path: Path | None = None
        self.waveform_active_playback_id: int | None = None
        self.waveform_active_started_at = 0.0
        self.waveform_active_duration = 0.0
        self.waveform_active_offset = 0.0
        self.waveform_progress_after_id = None
        self.selected_clip_ids = set()
        self.clip_selection_anchor = None
        self.audio_edit_mode = False
        self.audio_edit_dirty = False
        self.audio_edit_status_var = None
        self.audio_clip_buffer = None
        self.audio_edit_working: dict[str, dict] = {}
        self.waveform_selection_ranges: dict[str, tuple[float, float] | None] = {"original": None, "dubbed": None}
        self.waveform_selection_kind: str | None = None
        self.waveform_drag_kind: str | None = None
        self.waveform_drag_start_x = 0.0
        self.audio_edit_button = None
        self.audio_split_button = None
        self.clip_timeline_canvas = None
        self.clip_drag = None
        self.audio_undo_button = None
        self.audio_redo_button = None
        self.audio_cut_button = None
        self.audio_delete_button = None
        self.audio_copy_button = None
        self.audio_paste_button = None
        self.audio_save_button = None
        self.audio_edit_undo_stack: list[tuple[str, dict]] = []
        self.audio_edit_redo_stack: list[tuple[str, dict]] = []
        self.audio_edit_base_frames: dict[str, bytes] = {}
        self.audio_edit_preview_path: Path | None = None
        self.audio_paused_kind: str | None = None
        self.audio_paused_path: Path | None = None
        self.audio_paused_seconds = 0.0
        self.review_snapshot_provider = None
        self.review_snapshot_after_id = None
        self.review_panel = None
        self.review_panel_widgets = []
        self.review_history_box = None
        self.review_regen_box = None
        self.review_clone_var = None
        self.review_dub_var = None
        self.review_clone_bar = None
        self.review_dub_bar = None
        self.review_phase_var = None
        self.review_progress_frame = None
        self.review_progress_widgets = []
        self.selection_callback = None
        self.review_actions = {}
        self.review_preferences = {}
        self.navigation_context_keys: list[str | None] = []
        self.current_context_key: str | None = None
        self.playback_id = 0
        self.theme = {"mode": "claro", "surface": "#FFFFFF", "text": "#1F2937"}

    def set_dubbed_folder_name(self, folder_name: str) -> None:
        """Define qual pasta representa a faixa DUBLADO na janela OUVIR CENA."""
        name = str(folder_name or "dublado").strip() or "dublado"
        if name != self.dubbed_folder_name:
            self.dubbed_folder_name = name
            self._project_audio_index.clear()
            self.apply_theme({})

    def set_scene_integration(self, selection_callback=None, review_actions=None) -> None:
        """Configura sincronização da lista e ações opcionais de Revisão."""
        self.selection_callback = selection_callback
        self.review_actions = dict(review_actions or {})

    def refresh_current_scene(self, scene_key: str | None = None) -> None:
        """Recarrega o par atual após dublagem/redublagem sem fechar a janela."""
        had_window = False
        try:
            had_window = self.window is not None and self.window.winfo_exists()
        except Exception:
            had_window = False
        if not self.navigation_paths or self.current_index < 0 or self.current_index >= len(self.navigation_paths):
            return
        if scene_key is not None and self.current_context_key is not None and str(scene_key) != str(self.current_context_key):
            return
        index = self.current_index
        self._resolved_pair_indices.discard(index)
        self._resolve_navigation_pair(index)
        path = self.navigation_paths[index]
        self._set_current_mode_paths(index, path)
        original = self.original_pending_paths[0] if self.original_pending_paths else None
        dubbed = self.dubbed_pending_paths[0] if self.dubbed_pending_paths else None
        if self.window_status is not None:
            try:
                self.window_status.set(i18n.tr(self._scene_status_text(index + 1, len(self.navigation_paths), path, original, dubbed)))
            except Exception:
                pass
        self._refresh_scene_text()
        if not self.audio_edit_dirty:
            self.audio_edit_working.clear()
            self.audio_edit_undo_stack.clear()
            self.audio_edit_redo_stack.clear()
            if self.audio_edit_mode:
                self._load_edit_track('original')
                self._load_edit_track('dubbed')
        self._refresh_waveforms()
        self._update_audio_edit_buttons()
        self._update_mode_buttons()
        self._refresh_review_snapshot()
        if had_window:
            self.emit_status(f"Cena atualizada: {path.name}")

    def set_scene_text_integration(self, loader=None, saver=None) -> None:
        """Configura o carregamento e o salvamento do TXT da cena atual."""
        self.scene_text_loader = loader
        self.scene_text_saver = saver
        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self._refresh_scene_text()
            except Exception:
                pass

    def set_review_preferences(self, preferences=None) -> None:
        """Atualiza os controles auxiliares de Revisão exibidos no player."""
        self.review_preferences = dict(preferences or {})
        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self._refresh_review_preferences()
            except Exception:
                pass

    def set_review_snapshot_provider(self, provider=None) -> None:
        """Exibe no player um retrato leve do histórico e do progresso da Revisão."""
        self.review_snapshot_provider = provider
        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self._refresh_review_snapshot()
            except Exception:
                pass

    @staticmethod
    def _review_snapshot_text(widget) -> str:
        if widget is None:
            return ""
        try:
            return str(widget.get("1.0", "end-1c"))
        except Exception:
            return ""

    def _refresh_review_snapshot(self) -> None:
        self.review_snapshot_after_id = None
        if self.review_clone_var is None and self.review_dub_var is None:
            return
        if not callable(self.review_snapshot_provider):
            return
        try:
            if not self.window.winfo_exists():
                return
        except Exception:
            return
        snapshot = {}
        try:
            result = self.review_snapshot_provider(self.current_context_key)
            if isinstance(result, dict):
                snapshot = result
        except TypeError:
            try:
                result = self.review_snapshot_provider()
                if isinstance(result, dict):
                    snapshot = result
            except Exception:
                snapshot = {}
        except Exception:
            snapshot = {}
        history = str(snapshot.get("history") or "")
        regen = str(snapshot.get("regen") or "")
        for widget, value in ((self.review_history_box, history), (self.review_regen_box, regen)):
            if widget is None:
                continue
            try:
                widget.configure(state="normal")
                widget.delete("1.0", END)
                widget.insert("1.0", value)
                widget.see(END)
                widget.configure(state="disabled")
            except Exception:
                pass
        for variable, value in ((self.review_clone_var, snapshot.get("clone_progress", 0.0)), (self.review_dub_var, snapshot.get("dub_progress", 0.0))):
            if variable is None:
                continue
            try:
                variable.set(min(100.0, max(0.0, float(value or 0.0))))
            except (TypeError, ValueError):
                variable.set(0.0)
        if self.review_phase_var is not None:
            try:
                self.review_phase_var.set(str(snapshot.get("phase") or "Pronto para refazer a cena"))
            except Exception:
                pass
        try:
            self.review_snapshot_after_id = self.parent.after(250, self._refresh_review_snapshot)
        except Exception:
            self.review_snapshot_after_id = None

    def _refresh_review_preferences(self) -> None:
        for widget in getattr(self, "review_preference_widgets", []):
            try:
                widget.destroy()
            except Exception:
                pass
        self.review_preference_widgets = []
        container = getattr(self, "review_preferences_frame", None)
        controls = getattr(self, "review_controls_buttons", None)
        if container is None or controls is None:
            return
        try:
            container.pack_forget()
        except Exception:
            pass
        auto_var = self.review_preferences.get("auto_open_var")
        auto_command = self.review_preferences.get("auto_open_command")
        request_r_var = self.review_preferences.get("request_r_var")
        request_r_command = self.review_preferences.get("request_r_command")
        request_character_var=self.review_preferences.get("request_character_var")
        request_translation_var=self.review_preferences.get("request_translation_var")
        if auto_var is None and request_r_var is None and request_character_var is None and request_translation_var is None:
            return
        try:
            basic_row=container
            request_row=container
            container.columnconfigure(0, weight=1)
            container.columnconfigure(1, weight=1)
            container.columnconfigure(2, weight=1)
            container.columnconfigure(3, weight=1)
            if auto_var is not None:
                widget = ttk.Checkbutton(basic_row, text=i18n.tr("Abrir Audacity após redublar"), variable=auto_var, command=auto_command)
                widget.grid(row=0, column=0, sticky='w', padx=(0, 18), pady=(2, 4))
                self.review_preference_widgets.append(widget)
            if request_r_var is not None:
                widget = ttk.Checkbutton(basic_row, text=i18n.tr("Pedido de alterar pronúncia do R"), variable=request_r_var, command=request_r_command)
                widget.grid(row=0, column=1, sticky='w', pady=(2, 4))
                self.review_preference_widgets.append(widget)
            if request_character_var is not None:
                widget=ttk.Checkbutton(request_row,text=i18n.tr("Alterar personagem da dublagem"),variable=request_character_var,onvalue="1",offvalue="0")
                widget.grid(row=1, column=0, sticky='w', padx=(0, 12), pady=(2, 4))
                self.review_preference_widgets.append(widget)
            if request_translation_var is not None:
                widget=ttk.Checkbutton(request_row,text=i18n.tr("Transcrever e traduzir original"),variable=request_translation_var,onvalue="1",offvalue="0")
                widget.grid(row=1, column=1, sticky='w', pady=(2, 4))
                self.review_preference_widgets.append(widget)
            for column, (name, label) in enumerate((('align_original_var', 'Alinhar ritmo e duração ao original'), ('translate_missing_var', 'Transcrever e traduzir quando faltar TXT'))):
                variable = self.review_preferences.get(name)
                if variable is not None:
                    widget = ttk.Checkbutton(container, text=i18n.tr(label), variable=variable, onvalue='1', offvalue='0')
                    widget.grid(row=column, column=2, sticky='w', padx=(12,0), pady=(2,4))
                    self.review_preference_widgets.append(widget)
            natural=self.review_preferences.get('preserve_original_voice_var')
            if natural is not None:
                widget=ttk.Checkbutton(container,text=i18n.tr('Manter voz natural do áudio original'),variable=natural,onvalue='1',offvalue='0')
                widget.grid(row=0,column=3,sticky='w',padx=(8,0),pady=(2,4))
                self.review_preference_widgets.append(widget)
            container.pack(fill="x", pady=(0, 4), before=controls)
        except Exception:
            pass

    def follow_scene_selection(self, scene_key, playlist, scene_keys):
        """Follow an owning list only while its scene window is already open."""
        if getattr(self, '_notifying_scene_selection', False):
            return
        try:
            if self.window is None or not self.window.winfo_exists():
                return
        except Exception:
            return
        keys = [str(key) for key in scene_keys]
        if str(scene_key) not in keys:
            return
        index = keys.index(str(scene_key))
        if self.navigation_context_keys == keys:
            if self.current_context_key != str(scene_key):
                self.navigate(index - self.current_index)
            return
        if not self._prepare_audio_edit_scene_change():
            return
        self.navigation_paths = [Path(os.path.abspath(os.path.expanduser(str(path)))) for path in playlist]
        self.navigation_context_keys = keys
        self.original_navigation_paths = [None] * len(keys)
        self.dubbed_navigation_paths = [None] * len(keys)
        self._resolved_pair_indices.clear()
        self.current_index = index
        self.navigate(0)

    def _notify_scene_selection(self) -> None:
        if not callable(self.selection_callback) or getattr(self, '_notifying_scene_selection', False):
            return
        self._notifying_scene_selection = True
        try:
            self.selection_callback(self.current_context_key, self.current_index)
        except Exception:
            pass
        finally:
            self._notifying_scene_selection = False

    def _invoke_review_action(self, action_name: str) -> None:
        callback = self.review_actions.get(action_name)
        if not callable(callback):
            return
        controller=getattr(self,'translation_controller',None)
        if controller is not None:
            controller.active_scene_player = self
        if controller is not None and getattr(self, 'show_original_text', False):
            controller.player_text_override = None
        if controller is not None and action_name in {'redub','redub_other','redub_personalized'} and self.scene_text_box is not None and not getattr(self, 'show_original_text', False):
            controller.player_text_override=(self.current_context_key,self.scene_text_box.get('1.0','end-1c'))
        try:
            callback(self.current_context_key)
        except TypeError:
            try:
                callback()
            except Exception:
                pass
        except Exception:
            pass

    def set_project_root(self, project_root: Path):
        self.project_root = Path(project_root).expanduser().resolve()
        self._project_audio_index.clear()
        self._ffplay_path = None

    def set_playback_mode(self, mode: str) -> str:
        """Seleciona FFplay ou o player padrão do Windows para novas reproduções."""
        normalized = str(mode or "ffplay").casefold()
        if normalized not in {"ffplay", "windows"}:
            normalized = "ffplay"
        if normalized != self.playback_mode:
            if normalized == "windows" and self.window is not None:
                self._destroy_window(clear_pending=True)
            else:
                self.stop(announce=False)
        self.playback_mode = normalized
        return normalized

    @staticmethod
    def _compact_path(path: Path, max_length: int = 82) -> str:
        """Exibe caminhos longos sem deixar o endereço empurrar os controles."""
        text = str(Path(path).expanduser())
        if len(text) <= max_length:
            return text
        name = Path(path).name
        if len(name) >= max_length - 8:
            return name[-max_length:]
        remaining = max_length - len(name) - 5
        return text[:remaining] + "..." + os.sep + name

    @classmethod
    def _scene_status_text(cls, index: int, total: int, path: Path, original: Path | None = None, dubbed: Path | None = None) -> str:
        original_line = cls._compact_path(original) if original is not None else "não encontrado"
        dubbed_line = cls._compact_path(dubbed) if dubbed is not None else "não encontrado"
        return (
            f"Áudio carregado {index}/{total}:\n"
            f"Nome: {path.name}\n"
            f"Arquivo selecionado: {cls._compact_path(path)}\n"
            f"Dublado: {dubbed_line}\n"
            f"Original: {original_line}\n\n"
            "Clique em INICIAR DUBLADO ou INICIAR ORIGINAL para ouvir."
        )

    def emit_status(self, text: str):
        if self.status_callback:
            try:
                self.parent.after(0, lambda: self.status_callback(i18n.tr(text)))
            except Exception:
                pass
        if self.window is not None and self.window_status is not None:
            try:
                self.parent.after(0, lambda: self.window_status.set(i18n.tr(text)) if self.window_status is not None else None)
            except Exception:
                pass

    def _cancel_waveform_progress(self, reset: bool = True) -> None:
        after_id = self.waveform_progress_after_id
        self.waveform_progress_after_id = None
        if after_id is not None:
            try:
                self.parent.after_cancel(after_id)
            except Exception:
                pass
        if reset:
            self.waveform_progress = {"original": 0.0, "dubbed": 0.0}
        self.waveform_active_kind = None
        self.waveform_active_path = None
        self.waveform_active_playback_id = None
        self.waveform_active_started_at = 0.0
        self.waveform_active_duration = 0.0
        self.waveform_active_offset = 0.0
        for kind in tuple(self.waveform_canvases):
            self._draw_waveform(kind)

    def _begin_waveform_progress(self, kind: str, path: Path, playback_id: int, start_seconds: float = 0.0) -> None:
        if playback_id != self.playback_id or self.window is None:
            return
        try:
            if not self.window.winfo_exists():
                return
        except Exception:
            return
        self._cancel_waveform_progress(reset=True)
        data = self.waveform_data.get(kind) or {}
        duration = float(data.get("duration", 0.0) or 0.0)
        self.waveform_active_kind = kind
        self.waveform_active_path = Path(path).resolve()
        self.waveform_active_playback_id = playback_id
        self.waveform_active_started_at = time.monotonic()
        self.waveform_active_duration = duration
        self.waveform_active_offset = max(0.0, min(float(start_seconds or 0.0), duration))
        self.waveform_progress[kind] = self.waveform_active_offset / duration if duration > 0 else 0.0
        self._draw_waveform(kind)
        self._poll_waveform_progress()

    def _poll_waveform_progress(self) -> None:
        self.waveform_progress_after_id = None
        kind = self.waveform_active_kind
        playback_id = self.waveform_active_playback_id
        if kind not in self.waveform_canvases or playback_id != self.playback_id or self.stop_event.is_set():
            return
        elapsed = max(0.0, time.monotonic() - self.waveform_active_started_at)
        duration = self.waveform_active_duration
        progress = min(1.0, (self.waveform_active_offset + elapsed) / duration) if duration > 0 else 0.0
        self.waveform_progress[kind] = progress
        self._draw_waveform(kind)
        if progress < 1.0:
            try:
                self.waveform_progress_after_id = self.parent.after(50, self._poll_waveform_progress)
            except Exception:
                self.waveform_progress_after_id = None

    def _finish_waveform_progress(self, playback_id: int) -> None:
        if playback_id != self.playback_id:
            return
        kind = self.waveform_active_kind
        if kind not in self.waveform_canvases:
            return
        self.waveform_progress[kind] = 1.0
        after_id = self.waveform_progress_after_id
        self.waveform_progress_after_id = None
        if after_id is not None:
            try:
                self.parent.after_cancel(after_id)
            except Exception:
                pass
        self.waveform_active_kind = None
        self.waveform_active_path = None
        self.waveform_active_playback_id = None
        self.waveform_active_started_at = 0.0
        self.waveform_active_duration = 0.0
        self.waveform_active_offset = 0.0
        self._draw_waveform(kind)

    def stop(self, announce: bool = True, clear_pause: bool = True):
        self._cancel_waveform_progress(reset=True)
        if clear_pause:
            self.audio_paused_kind = None
            self.audio_paused_path = None
            self.audio_paused_seconds = 0.0
        self.playback_id += 1
        self.stop_event.set()
        stop_winsound()
        process = self.process
        if process is not None:
            try:
                process.terminate()
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
            except (OSError, subprocess.SubprocessError, AttributeError):
                pass
            self.process = None
        if self.thread is not None and self.thread is not threading.current_thread():
            # O processo filho é encerrado; a thread termina naturalmente logo depois.
            self.thread = None
        for button in (self.start_button, self.original_button):
            if button is not None:
                try:
                    button.configure(state="normal")
                except Exception:
                    pass
        self._update_original_button()
        if announce:
            self.emit_status("Reprodução parada")

    def _destroy_window(self, clear_pending: bool):
        drawer=getattr(self,'review_drawer',None)
        if drawer is not None:drawer.close()
        self.review_drawer=None
        treated=getattr(self,'audacity_ui',None)
        if treated is not None:treated.cancel.set()
        # Fechar uma janela antiga não pode apagar a fila recém-carregada.
        self.stop(announce=False)
        if clear_pending:
            self.pending_paths = []
            self.original_pending_paths = []
            self.dubbed_pending_paths = []
        window = self.window
        self.window = None
        self.window_status = None
        self.window_body = None
        self.window_content = None
        self.start_button = None
        self.original_button = None
        self.previous_button = None
        self.next_button = None
        self.stop_button = None
        self.close_button = None
        self.review_action_buttons = []
        self.audio_action_buttons = []
        self.scene_text_title_var = None
        self.scene_text_status_var = None
        self.scene_text_box = None
        self.scene_text_save_button = None
        self.scene_text_path: Path | None = None
        self.waveform_canvases = {}
        self.waveform_duration_vars = {}
        self.waveform_data = {}
        self.waveform_panel = None
        self.waveform_split = None
        self.waveform_widgets = []
        self.review_top_row = None
        self.review_top_spacer = None
        self.review_top_panel = None
        self.waveform_duration_labels = {}
        self.waveform_reference_duration = 0.0
        self.waveform_zoom = 1.0
        self.waveform_scroll = 0.0
        self.waveform_zoom_var = None
        self.waveform_zoom_status = None
        self.waveform_scrollbar = None
        self.waveform_navigation = None
        self.waveform_vertical_view = None
        self.waveform_progress = {"original": 0.0, "dubbed": 0.0}
        self.waveform_active_kind = None
        self.waveform_active_path = None
        self.waveform_active_playback_id = None
        self.waveform_active_started_at = 0.0
        self.waveform_active_duration = 0.0
        self.waveform_active_offset = 0.0
        self.waveform_progress_after_id = None
        self.audio_edit_mode = False
        self.audio_edit_dirty = False
        self.audio_edit_status_var = None
        self.audio_clip_buffer = None
        self.audio_edit_working = {}
        self.waveform_selection_ranges = {"original": None, "dubbed": None}
        self.waveform_selection_kind = None
        self.waveform_drag_kind = None
        self.waveform_drag_start_x = 0.0
        self.audio_edit_button = None
        self.audio_split_button = None
        self.clip_timeline_canvas = None
        self.clip_drag = None
        self.audio_undo_button = None
        self.audio_redo_button = None
        self.audio_cut_button = None
        self.audio_delete_button = None
        self.audio_copy_button = None
        self.audio_paste_button = None
        self.audio_save_button = None
        self.audio_edit_undo_stack = []
        self.audio_edit_redo_stack = []
        self.audio_edit_base_frames = {}
        preview_path = getattr(self, "audio_edit_preview_path", None)
        self.audio_edit_preview_path = None
        if preview_path is not None:
            try:
                preview_path.unlink(missing_ok=True)
            except OSError:
                pass
        self.audio_paused_kind = None
        self.audio_paused_path = None
        self.audio_paused_seconds = 0.0
        review_after_id = getattr(self, "review_snapshot_after_id", None)
        self.review_snapshot_after_id = None
        if review_after_id is not None:
            try:
                self.parent.after_cancel(review_after_id)
            except Exception:
                pass
        self.review_snapshot_provider = getattr(self, "review_snapshot_provider", None)
        self.review_panel = None
        self.review_panel_widgets = []
        self.review_history_box = None
        self.review_regen_box = None
        self.review_clone_var = None
        self.review_dub_var = None
        self.review_clone_bar = None
        self.review_dub_bar = None
        self.review_phase_var = None
        self.review_progress_frame = None
        self.review_progress_widgets = []
        if clear_pending:
            self.navigation_paths = []
            self.navigation_context_keys = []
            self.original_navigation_paths = []
            self.dubbed_navigation_paths = []
            self._resolved_pair_indices.clear()
            self.current_source_kind = "unknown"
            self.current_index = -1
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass

    def close_window(self):
        self._destroy_window(clear_pending=True)

    @staticmethod
    def _read_waveform(path: Path | None, points: int = 700):
        if path is None or not Path(path).is_file():
            return None
        try:
            with wave.open(str(path), "rb") as wav_file:
                channels = max(1, wav_file.getnchannels())
                sample_rate = max(1, wav_file.getframerate())
                sample_width = wav_file.getsampwidth()
                frame_count = wav_file.getnframes()
                duration = frame_count / float(sample_rate)
                if frame_count <= 0 or sample_width not in (1, 2, 3, 4):
                    return {"samples": [], "duration": duration, "sample_rate": sample_rate, "channels": channels}
                block_size = max(1, (frame_count + points - 1) // points)
                samples = []
                scale = float(1 << (sample_width * 8 - 1))
                for _ in range(points):
                    raw = wav_file.readframes(block_size)
                    if not raw:
                        break
                    if sample_width == 1:raw=audioop.bias(raw,1,-128)
                    samples.append(min(1.0,audioop.max(raw,sample_width)/scale))
                return {"samples": samples, "duration": duration, "sample_rate": sample_rate, "channels": channels}
        except (OSError, EOFError, wave.Error, ValueError):
            # Some engines write float WAV, unsupported by the stdlib wave reader.
            try:
                from pydub import AudioSegment
                decoded = AudioSegment.from_file(path).set_sample_width(2)
                return AudioPlayerManager._waveform_from_pcm(decoded.raw_data, decoded.channels,
                                                            2, decoded.frame_rate, points)
            except Exception:
                return None

    @staticmethod
    def _waveform_from_pcm(raw: bytes, channels: int, sample_width: int, sample_rate: int, points: int = 700):
        """Calcula uma onda a partir de PCM já carregado para o modo de edição."""
        channels = max(1, int(channels))
        sample_width = int(sample_width)
        sample_rate = max(1, int(sample_rate))
        frame_bytes = sample_width * channels
        frame_count = len(raw) // frame_bytes if frame_bytes > 0 else 0
        duration = frame_count / float(sample_rate)
        if frame_count <= 0 or sample_width not in (1, 2, 3, 4):
            return {"samples": [], "duration": duration, "sample_rate": sample_rate, "channels": channels}
        block_size = max(1, (frame_count + points - 1) // points)
        scale = float(1 << (sample_width * 8 - 1))
        samples = []
        for block_index in range(0, frame_count, block_size):
            block = raw[block_index * frame_bytes:min(frame_count, block_index + block_size) * frame_bytes]
            if sample_width == 1:block=audioop.bias(block,1,-128)
            samples.append(min(1.0,audioop.max(block,sample_width)/scale))
            if len(samples) >= points:
                break
        return {"samples": samples, "duration": duration, "sample_rate": sample_rate, "channels": channels}

    def _load_edit_track(self, kind: str):
        """Carrega a faixa PCM da cena atual uma única vez para edição."""
        if kind in self.audio_edit_working:
            return self.audio_edit_working[kind]
        path = self._current_audio_path(kind)
        if path is None or Path(path).suffix.casefold() not in {".wav", ".wave", ".waw"}:
            return None
        try:
            with wave.open(str(path), "rb") as wav_file:
                params = wav_file.getparams()
                raw = wav_file.readframes(params.nframes)
            track = {
                "path": Path(path).resolve(),
                "frames": raw,
                "channels": params.nchannels,
                "sample_width": params.sampwidth,
                "sample_rate": params.framerate,
                "comptype": params.comptype,
                "compname": params.compname,
            }
            if kind == "dubbed":
                self._load_clip_layout(track)
            track["saved_clips"] = self._track_clips(track)
            self.audio_edit_working[kind] = track
            return track
        except (OSError, EOFError, wave.Error, ValueError):
            try:
                from pydub import AudioSegment
                decoded = AudioSegment.from_file(path).set_sample_width(2)
                track = dict(path=Path(path).resolve(), frames=decoded.raw_data,
                             channels=decoded.channels, sample_width=2, sample_rate=decoded.frame_rate,
                             comptype='NONE', compname='not compressed')
                track['saved_clips'] = self._track_clips(track)
                self.audio_edit_working[kind] = track
                return track
            except Exception:
                return None

    def _remove_audio_edit_preview(self) -> None:
        preview = self.audio_edit_preview_path
        self.audio_edit_preview_path = None
        if preview is not None:
            try:
                preview.unlink(missing_ok=True)
            except OSError:
                pass

    def _update_audio_edit_dirty(self) -> None:
        self.audio_edit_dirty = any(
            bytes(track.get("frames", b"")) != self.audio_edit_base_frames.get(kind, bytes(track.get("frames", b"")))
            or self._track_clips(track) != track.get("saved_clips", (AudioClip(1, 0, self.audio_edit_base_frames.get(kind, bytes(track.get("frames", b"")))),))
            for kind, track in self.audio_edit_working.items()
        )

    def _clip_layout_location(self, track):
        target = Path(track["path"]).resolve()
        root = self.project_root or target.parent
        try:
            key = target.relative_to(root).as_posix()
        except ValueError:
            key = str(target)
        return Path(root) / "revisoes" / ".dublaskizon_trechos.json", key

    def _load_clip_layout(self, track):
        try:
            path, key = self._clip_layout_location(track)
            records = json.loads(path.read_text(encoding="utf-8"))
            record = records.get(key, {}) if isinstance(records, dict) else {}
            if not isinstance(record, dict) or record.get("format") != [track["channels"], track["sample_width"], track["sample_rate"]]:
                return
            if record.get("sha256") != hashlib.sha256(track["frames"]).hexdigest():
                return
            frame_bytes = self._edit_frame_bytes(track)
            total = len(track["frames"]) // frame_bytes
            clips = []
            end = 0
            ids = set()
            for identifier, start, stop in record["clips"]:
                if not all(isinstance(v, int) for v in (identifier, start, stop)) or identifier in ids or not end <= start < stop <= total:
                    return
                ids.add(identifier)
                clips.append(AudioClip(identifier, start, track["frames"][start*frame_bytes:stop*frame_bytes]))
                end = stop
            if clips:
                # Metadados externos nunca podem omitir áudio audível da faixa.
                rendered = render_clips(clips, frame_bytes, track["sample_width"], total, max(len(track["frames"]), 1))
                if rendered == track["frames"]:
                    track["clips"] = tuple(clips)
        except (OSError, ValueError, KeyError, TypeError, MemoryError):
            pass

    def _save_clip_layout(self, track):
        path, key = self._clip_layout_location(track)
        records = {}
        if path.exists():
            try:
                records = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(records, dict):
                    records = {}
            except (ValueError, OSError):
                records = {}
        frame_bytes = self._edit_frame_bytes(track)
        records[key] = {"format": [track["channels"], track["sample_width"], track["sample_rate"]], "sha256": hashlib.sha256(track["frames"]).hexdigest(), "clips": [[c.id, c.start, c.end(frame_bytes)] for c in self._track_clips(track)]}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        try:
            temporary.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _track_clips(self, track):
        return track.get("clips") or (AudioClip(1, 0, bytes(track.get("frames", b""))),)

    def _track_snapshot(self, track):
        return {"frames": bytes(track.get("frames", b"")), "clips": self._track_clips(track), "duration_base": track.get("duration_base"), "duration_ratio": track.get("duration_ratio",1.0)}

    def _restore_track_snapshot(self, kind, track, state):
        if isinstance(state, bytes):
            state = {"frames": state, "clips": (AudioClip(1, 0, state),)}
        self._set_edit_frames(kind, track, state["frames"], record_history=False, clips=state["clips"])
        if state.get('duration_base') is not None:
            track['duration_base']=state['duration_base'];track['duration_ratio']=state.get('duration_ratio',1.0)

    def _set_edit_frames(self, kind: str, track: dict, raw: bytes, record_history: bool = True, clips=None) -> None:
        current = bytes(track.get("frames", b""))
        updated = bytes(raw)
        if clips is None and current == updated:
            return
        updated_clips = tuple(clips) if clips is not None else (AudioClip(1, 0, updated),)
        if current == updated and self._track_clips(track) == updated_clips:
            return
        # Nunca deixamos um preview antigo continuar tocando enquanto a faixa
        # editável muda; isso evita ouvir o WAV anterior depois de uma colagem.
        self.stop(announce=False)
        self._remove_audio_edit_preview()
        if record_history:
            self.audio_edit_undo_stack.append((kind, self._track_snapshot(track)))
            self.audio_edit_redo_stack.clear()
        self.selected_clip_ids=set();self.clip_selection_anchor=None
        track.pop('duration_base',None);track.pop('duration_ratio',None)
        track["frames"] = updated
        track["clips"] = updated_clips
        self.audio_edit_working[kind] = track
        self._update_audio_edit_dirty()
        self.waveform_selection_ranges[kind] = None
        self.waveform_selection_kind = None
        self._refresh_waveforms()
        self._update_audio_edit_buttons()

    def _undo_audio_edit(self, _event=None):
        if not self.audio_edit_mode:
            return None
        if not self.audio_edit_undo_stack:
            self._set_audio_edit_status("Não há alterações de áudio para desfazer.")
            return "break"
        kind, previous = self.audio_edit_undo_stack.pop()
        track = self.audio_edit_working.get(kind)
        if track is None:
            self._set_audio_edit_status("A faixa da alteração não está disponível nesta cena.")
            return "break"
        self.audio_edit_redo_stack.append((kind, self._track_snapshot(track)))
        self._restore_track_snapshot(kind, track, previous)
        self._set_audio_edit_status("Última alteração de áudio desfeita. Use REFAZER ou Ctrl+Y para reaplicar.")
        return "break"

    def _redo_audio_edit(self, _event=None):
        if not self.audio_edit_mode:
            return None
        if not self.audio_edit_redo_stack:
            self._set_audio_edit_status("Não há alterações de áudio para refazer.")
            return "break"
        kind, next_frames = self.audio_edit_redo_stack.pop()
        track = self.audio_edit_working.get(kind)
        if track is None:
            self._set_audio_edit_status("A faixa da alteração não está disponível nesta cena.")
            return "break"
        self.audio_edit_undo_stack.append((kind, self._track_snapshot(track)))
        self._restore_track_snapshot(kind, track, next_frames)
        self._set_audio_edit_status("Última alteração de áudio refeita. Use Ctrl+Z para desfazer.")
        return "break"

    def _edit_frame_bytes(self, track: dict) -> int:
        return max(1, int(track.get("channels", 1)) * int(track.get("sample_width", 2)))

    def _edit_selection_frames(self, kind: str):
        track = self.audio_edit_working.get(kind) or self._load_edit_track(kind)
        selection = self.waveform_selection_ranges.get(kind)
        if track is None or selection is None:
            return None
        frame_bytes = self._edit_frame_bytes(track)
        total_frames = len(track.get("frames", b"")) // frame_bytes
        start_seconds, end_seconds = sorted((float(selection[0]), float(selection[1])))
        rate = max(1, int(track.get("sample_rate", 1)))
        start_frame = max(0, min(total_frames, int(round(start_seconds * rate))))
        end_frame = max(start_frame, min(total_frames, int(round(end_seconds * rate))))
        return track, start_frame, end_frame, frame_bytes

    def _waveform_x_to_seconds(self, kind: str, x: float) -> float:
        canvas = self.waveform_canvases.get(kind)
        data = self.waveform_data.get(kind) or {}
        duration = max(0.0, float(data.get("duration", 0.0) or 0.0))
        if canvas is None or duration <= 0:
            return 0.0
        width = max(180, int(canvas.winfo_width()))
        plot_width = self._waveform_plot_width(kind, width)
        click_x = max(2.0, min(self._audio_canvas_x(canvas, x), 2.0 + plot_width))
        return duration * (click_x - 2.0) / max(1.0, plot_width)

    def _on_waveform_press(self, kind: str, event) -> None:
        canvas = self.waveform_canvases.get(kind)
        if canvas is not None:
            try:
                canvas.focus_set()
            except Exception:
                pass
        if not self.audio_edit_mode:
            self._seek_from_waveform(kind, event)
            return
        if self._load_edit_track(kind) is None:
            self._set_audio_edit_status("Edição disponível somente para WAV PCM legível.")
            return
        self.stop(announce=False)
        if kind=='dubbed' and getattr(event,'state',0) & 5:
            track=self.audio_edit_working[kind]
            frame=round(self._waveform_x_to_seconds(kind,event.x)*track['sample_rate'])
            clip=next((c for c in self._track_clips(track) if c.start<=frame<c.end(self._edit_frame_bytes(track))),None)
            if clip is not None:self._select_clip(clip,event.state)
            return
        self.selected_clip_ids=set();self.clip_selection_anchor=None
        for other_kind in self.waveform_canvases:
            if other_kind != kind:
                self.waveform_selection_ranges[other_kind] = None
                self._draw_waveform(other_kind)
        self.waveform_drag_kind = kind
        self.waveform_drag_start_x = float(getattr(event, "x", 0.0))
        start_seconds = self._waveform_x_to_seconds(kind, self.waveform_drag_start_x)
        self.waveform_selection_ranges[kind] = (start_seconds, start_seconds)
        self.waveform_selection_kind = kind
        self._draw_waveform(kind)
        self._draw_clip_timeline()
        self._update_audio_edit_buttons()

    def _on_waveform_motion(self, kind: str, event) -> None:
        if not self.audio_edit_mode or self.waveform_drag_kind != kind:
            return
        end_seconds = self._waveform_x_to_seconds(kind, float(getattr(event, "x", 0.0)))
        start_seconds = self._waveform_x_to_seconds(kind, self.waveform_drag_start_x)
        self.waveform_selection_ranges[kind] = (start_seconds, end_seconds)
        self.waveform_selection_kind = kind
        self._draw_waveform(kind)
        self._draw_clip_timeline()

    def _on_waveform_release(self, kind: str, event) -> None:
        if not self.audio_edit_mode or self.waveform_drag_kind != kind:
            return
        self._on_waveform_motion(kind, event)
        self.waveform_drag_kind = None
        selection = self.waveform_selection_ranges.get(kind)
        if selection is not None:
            start_seconds, end_seconds = sorted(selection)
            self._set_audio_edit_status(f"Trecho {kind}: {self._format_wave_duration(start_seconds)} → {self._format_wave_duration(end_seconds)}")
        self._update_audio_edit_buttons()

    def _focused_waveform_kind(self) -> str | None:
        try:
            focused = self.window.focus_get() if self.window is not None else None
        except Exception:
            focused = None
        for kind, canvas in self.waveform_canvases.items():
            if focused is canvas:
                return kind
        return self.waveform_selection_kind if self.waveform_selection_kind in self.waveform_canvases else None

    def _set_audio_edit_status(self, text: str) -> None:
        if self.audio_edit_status_var is not None:
            self.audio_edit_status_var.set(text)
        self.emit_status(text)

    def _on_edit_space(self, event=None):
        """Permite Espaço global na janela, sem impedir espaços no editor de texto."""
        try:
            focused = self.window.focus_get() if self.window is not None else None
            if focused is not None and focused.winfo_class() in {"Text", "Entry", "TEntry"}:
                return None
        except Exception:
            pass
        return self._toggle_edit_play_pause(event)


    def _publish_audio_clip(self):
        target = getattr(self, "clipboard_target", None)
        if target is not None and self.audio_clip_buffer:
            target.audio_clip_buffer = dict(self.audio_clip_buffer)
            target._update_audio_edit_buttons()
            target._set_audio_edit_status("Áudio da parte copiado. Em EDITAR, clique no ponto desejado do DUBLADO e use COLAR.")

    def _copy_whole_part(self):
        if not self.audio_edit_mode:
            self._toggle_audio_edit()
        track = self.audio_edit_working.get("dubbed")
        if not self.audio_edit_mode or track is None:
            return
        duration = len(track["frames"]) / self._edit_frame_bytes(track) / track["sample_rate"]
        self.waveform_selection_kind = "dubbed"
        self.waveform_selection_ranges["dubbed"] = (0.0, duration)
        self._draw_waveform("dubbed")
        self._draw_clip_timeline()
        self._copy_audio_selection()

    def _copy_audio_selection(self, _event=None):
        if not self.audio_edit_mode:
            return None
        kind = self.waveform_selection_kind or self._focused_waveform_kind()
        clips=self._selected_dubbed_clips() if kind=='dubbed' else []
        if clips:
            track=self.audio_edit_working['dubbed']
            self.audio_clip_buffer={key:track[key] for key in ('channels','sample_width','sample_rate')}
            self.audio_clip_buffer.update(frames=b''.join(c.pcm for c in clips),source_kind='dubbed')
            self._publish_audio_clip();self._update_audio_edit_buttons()
            self._set_audio_edit_status(f'{len(clips)} trecho(s) copiado(s) na ordem da faixa.')
            return 'break'
        selected = self._edit_selection_frames(kind) if kind else None
        if selected is None:
            self._set_audio_edit_status("Selecione um trecho em qualquer onda para copiar.")
            return "break"
        track, start_frame, end_frame, frame_bytes = selected
        if end_frame <= start_frame:
            self._set_audio_edit_status("A seleção está vazia; arraste sobre a onda para escolher um trecho.")
            return "break"
        start_byte = start_frame * frame_bytes
        end_byte = end_frame * frame_bytes
        self.audio_clip_buffer = {
            "frames": bytes(track["frames"][start_byte:end_byte]),
            "channels": track["channels"],
            "sample_width": track["sample_width"],
            "sample_rate": track["sample_rate"],
            "source_kind": kind,
        }
        self._publish_audio_clip()
        self._set_audio_edit_status(f"Trecho copiado de {kind}: {self._format_wave_duration((end_frame - start_frame) / track['sample_rate'])}.")
        self._update_audio_edit_buttons()
        return "break"

    def _cut_audio_selection(self, _event=None):
        if self._selected_dubbed_clips():
            self._copy_audio_selection();self._delete_selected_clips();return 'break'
        if not self.audio_edit_mode:
            return None
        kind = self.waveform_selection_kind or self._focused_waveform_kind()
        if kind != "dubbed":
            self._set_audio_edit_status("Por segurança, CORTAR altera somente a faixa DUBLADO. Use COPIAR para ORIGINAL.")
            return "break"
        selected = self._edit_selection_frames(kind)
        if selected is None:
            self._set_audio_edit_status("Selecione um trecho na onda DUBLADO para cortar.")
            return "break"
        track, start_frame, end_frame, frame_bytes = selected
        if end_frame <= start_frame:
            self._set_audio_edit_status("A seleção está vazia; arraste sobre a onda para escolher um trecho.")
            return "break"
        start_byte = start_frame * frame_bytes
        end_byte = end_frame * frame_bytes
        self.audio_clip_buffer = {
            "frames": bytes(track["frames"][start_byte:end_byte]),
            "channels": track["channels"],
            "sample_width": track["sample_width"],
            "sample_rate": track["sample_rate"],
            "source_kind": kind,
        }
        self._publish_audio_clip()
        clips = paste_clip(self._track_clips(track), start_frame, end_frame, b"", frame_bytes)
        self._set_edit_frames(kind, track, track["frames"][:start_byte] + track["frames"][end_byte:], clips=clips)
        self._set_audio_edit_status(f"Trecho cortado de DUBLADO: {self._format_wave_duration((end_frame - start_frame) / track['sample_rate'])}.")
        return "break"

    def _delete_audio_selection(self, _event=None):
        """Remove a seleção do DUBLADO sem colocá-la no buffer de colagem."""
        if not self.audio_edit_mode:
            return None
        kind = self.waveform_selection_kind or self._focused_waveform_kind()
        if kind != "dubbed":
            self._set_audio_edit_status("Por segurança, DELETE altera somente a faixa DUBLADO. ORIGINAL é protegido.")
            return "break"
        if self._delete_selected_clips():return "break"
        selected = self._edit_selection_frames(kind)
        if selected is None:
            self._set_audio_edit_status("Selecione um trecho na onda DUBLADO para excluir.")
            return "break"
        track, start_frame, end_frame, frame_bytes = selected
        if end_frame <= start_frame:
            self._set_audio_edit_status("A seleção está vazia; arraste sobre a onda para escolher um trecho.")
            return "break"
        start_byte = start_frame * frame_bytes
        end_byte = end_frame * frame_bytes
        removed_duration = (end_frame - start_frame) / max(1, int(track["sample_rate"]))
        clips = paste_clip(self._track_clips(track), start_frame, end_frame, b"", frame_bytes)
        self._set_edit_frames(kind, track, track["frames"][:start_byte] + track["frames"][end_byte:], clips=clips)
        self._set_audio_edit_status(f"Trecho excluído do DUBLADO: {self._format_wave_duration(removed_duration)}. Use SALVAR para confirmar.")
        return "break"

    def _paste_audio_clip(self, _event=None):
        if not self.audio_edit_mode:
            return None
        clip = self.audio_clip_buffer
        if not clip:
            self._set_audio_edit_status("Nada foi copiado. Selecione um trecho e use COPIAR ou Ctrl+C.")
            return "break"
        target_kind = self._focused_waveform_kind()
        if target_kind == "original" or target_kind is None:
            target_kind = "dubbed"
        if target_kind != "dubbed":
            self._set_audio_edit_status("COLAR é aplicado na faixa DUBLADO para preservar o áudio ORIGINAL.")
            return "break"
        target = self._load_edit_track("dubbed")
        if target is None:
            self._set_audio_edit_status("Não há WAV DUBLADO editável nesta cena.")
            return "break"
        if (clip.get("channels"), clip.get("sample_width"), clip.get("sample_rate")) != (target.get("channels"), target.get("sample_width"), target.get("sample_rate")):
            self._set_audio_edit_status("O trecho copiado tem características diferentes do DUBLADO e não pode ser colado sem conversão.")
            return "break"
        selected = self._edit_selection_frames("dubbed")
        frame_bytes = self._edit_frame_bytes(target)
        if selected is None:
            self._set_audio_edit_status("Clique ou arraste na onda DUBLADO para escolher onde colar.")
            return "break"
        _track, start_frame, end_frame, _selected_frame_bytes = selected
        start_byte = start_frame * frame_bytes
        end_byte = end_frame * frame_bytes
        selected_clips=self._selected_dubbed_clips()
        if len(selected_clips)>1:
            new_frames=target['frames'];clips=self._track_clips(target)
            for selected_clip in reversed(selected_clips):
                end=selected_clip.end(frame_bytes)
                clips=paste_clip(clips,selected_clip.start,end,b'',frame_bytes)
                new_frames=new_frames[:selected_clip.start*frame_bytes]+new_frames[end*frame_bytes:]
            start_frame=selected_clips[0].start;start_byte=start_frame*frame_bytes
            clips=paste_clip(clips,start_frame,start_frame,clip['frames'],frame_bytes)
            new_frames=new_frames[:start_byte]+clip['frames']+new_frames[start_byte:]
        else:
            new_frames = target["frames"][:start_byte] + clip["frames"] + target["frames"][end_byte:]
            clips = paste_clip(self._track_clips(target), start_frame, end_frame, clip["frames"], frame_bytes)
        self._set_edit_frames("dubbed", target, new_frames, clips=clips)
        self._set_audio_edit_status(f"Trecho colado no DUBLADO: {self._format_wave_duration(len(clip['frames']) / frame_bytes / target['sample_rate'])}.")
        return "break"

    def _process_scene_audio_edit(self, duration_factor=None, volume_db=None, align_original=False, remove_internal_silence=False, exact_original=False):
        if not self.audio_edit_mode or getattr(self, "audio_transform_busy", False):
            return
        track = self.audio_edit_working.get("dubbed")
        if track is None or not track.get("frames"):
            self._set_audio_edit_status("Não há áudio DUBLADO editável nesta cena.")
            return
        self.stop(announce=False)
        self.audio_transform_busy = True
        self._update_audio_edit_buttons()
        self._set_audio_edit_status("Processando DUBLADO…")
        snapshot = dict(track)
        original = self._current_audio_path('original') if align_original or exact_original else None
        original_seconds=(self.waveform_data.get('original') or {}).get('duration',0) if exact_original else 0
        clip_snapshot = self._track_clips(track)
        duration_base=None;duration_ratio=None
        if duration_factor is not None and volume_db is None:
            duration_base=track.get('duration_base')
            if duration_base is None:
                duration_base=dict(snapshot,clips=clip_snapshot)
                duration_base.pop('duration_base',None);duration_base.pop('duration_ratio',None)
            # Add one percentage point of the same base per click; + then - restores it.
            duration_ratio=round(track.get('duration_ratio',1.0)+(duration_factor-1.0),8)
        window = self.window
        outcome = {}
        done = threading.Event()
        def work():
            try:
                if exact_original:
                    outcome['frames'],outcome['clips']=process_exact_original_duration(snapshot,self.project_root,original_seconds)
                elif remove_internal_silence:
                    outcome['frames'] = process_scene_internal_silence(snapshot)
                    outcome['clips'] = (AudioClip(1, 0, outcome['frames']),)
                elif align_original:
                    outcome['frames'] = process_scene_alignment(snapshot, original)
                    outcome['clips'] = (AudioClip(1, 0, outcome['frames']),)
                elif volume_db is not None:
                    outcome["frames"],outcome["clips"],outcome["gain_db"]=process_scene_volume(snapshot,volume_db)
                else:
                    outcome["frames"], outcome["clips"] = process_scene_audio(duration_base if duration_base is not None else snapshot, self.project_root, duration_ratio if duration_ratio is not None else duration_factor, preserve_clips=True)
            except Exception as exc:
                outcome["error"] = str(exc)
            finally:
                done.set()
        def finish():
            if not done.is_set():
                self.parent.after(75, finish)
                return
            self.audio_transform_busy = False
            if self.window is not window or not self.audio_edit_mode or self.audio_edit_working.get("dubbed") is not track:
                self._update_audio_edit_buttons()
                return
            if track["frames"] != snapshot["frames"] or self._track_clips(track) != clip_snapshot:
                self._set_audio_edit_status("O áudio mudou durante o processamento. Repita o ajuste.")
            elif 'warning' in outcome:
                self._set_audio_edit_status(outcome['warning'])
            elif "error" in outcome:
                self._set_audio_edit_status("Falha no ajuste: " + outcome["error"])
                messagebox.showerror("Editar áudio", outcome["error"], parent=self.window)
            else:
                if outcome["frames"] != track["frames"]:
                    self._set_edit_frames("dubbed", track, outcome["frames"], clips=outcome["clips"])
                if duration_base is not None:
                    track['duration_base']=duration_base;track['duration_ratio']=duration_ratio
                if exact_original:
                    label='Duração igualada ao original; áudio menor recebe silêncio somente no final'
                elif remove_internal_silence:
                    label = 'Silêncios do meio removidos; margens da fala e pausas de 60 ms preservadas'
                elif align_original:
                    label = 'Ondas organizadas nos intervalos de fala do original'
                elif volume_db is not None:
                    gain=outcome['gain_db']
                    label=f"Volume do DUBLADO: {gain:+.2f} dB aplicado"
                    if volume_db>0 and gain<volume_db-0.001:
                        label+=" (limite seguro atingido ou áudio silencioso)"
                else:
                    label = "Silêncio das extremidades removido" if duration_factor is None else f"Duração: {duration_ratio*100:.0f}% da base; método da pasta maior, sem reprocessar cliques anteriores"
                self._set_audio_edit_status(label + ('. Divisões recalculadas.' if align_original or remove_internal_silence else '. Divisões preservadas.') + ' Ouça e use SALVAR. DESFAZER reverte o ajuste.')
            self._update_audio_edit_buttons()
        threading.Thread(target=work, daemon=True).start()
        self.parent.after(75, finish)

    def _split_dubbed_clip(self, _event=None):
        if not self.audio_edit_mode or getattr(self, "audio_transform_busy", False):
            return "break"
        track = self.audio_edit_working.get("dubbed")
        selection = self.waveform_selection_ranges.get("dubbed")
        if track is None or selection is None or self.waveform_selection_kind != "dubbed":
            self._set_audio_edit_status("Clique no ponto desejado da onda DUBLADO e use DIVIDIR ou Ctrl+I.")
            return "break"
        try:
            frame = int(round(selection[1] * track["sample_rate"]))
            clips = split_clip(self._track_clips(track), frame, self._edit_frame_bytes(track))
            self._set_edit_frames("dubbed", track, track["frames"], clips=clips)
            self._set_audio_edit_status("Trecho dividido. Arraste uma barrinha acima da onda para mover. Espaços vazios viram silêncio.")
        except ValueError as exc:
            self._set_audio_edit_status(str(exc))
        return "break"

    def _clip_timeline_seconds(self):
        return max(0.1, float(self.waveform_reference_duration or 0.0))

    def _selected_dubbed_clips(self):
        if not self.audio_edit_mode or self.waveform_selection_kind != 'dubbed':return []
        track=self.audio_edit_working.get('dubbed')
        ids=getattr(self,'selected_clip_ids',set())
        return sorted((c for c in self._track_clips(track) if c.id in ids),key=lambda c:c.start) if track else []

    def _select_clip(self,clip,state=0):
        track=self.audio_edit_working['dubbed'];clips=sorted(self._track_clips(track),key=lambda c:c.start)
        ids=set(getattr(self,'selected_clip_ids',set()))
        if state & 1:
            anchor=getattr(self,'clip_selection_anchor',None)
            order=[c.id for c in clips]
            first=order.index(anchor) if anchor in order else order.index(clip.id)
            last=order.index(clip.id)
            chosen=set(order[min(first,last):max(first,last)+1])
            ids=ids|chosen if state & 4 else chosen
            if anchor not in order:self.clip_selection_anchor=clip.id
        elif state & 4:
            ids.symmetric_difference_update({clip.id});self.clip_selection_anchor=clip.id
        else:
            ids={clip.id};self.clip_selection_anchor=clip.id
        self.selected_clip_ids=ids
        self._sync_clip_selection()

    def _sync_clip_selection(self):
        self.waveform_selection_kind='dubbed';self.waveform_selection_ranges['original']=None
        clips=self._selected_dubbed_clips();track=self.audio_edit_working['dubbed']
        self.waveform_selection_ranges['dubbed']=(clips[0].start/track['sample_rate'],clips[-1].end(self._edit_frame_bytes(track))/track['sample_rate']) if clips else None
        self.waveform_drag_kind=None;self.clip_drag=None
        self._draw_waveform('original');self._draw_waveform('dubbed');self._draw_clip_timeline();self._update_audio_edit_buttons()
        self._set_audio_edit_status(f'{len(clips)} trecho(s) selecionado(s). Ctrl+clique alterna; Shift+clique seleciona intervalo.')

    def _select_all_dubbed_clips(self,event=None):
        if not self.audio_edit_mode or getattr(self,'audio_transform_busy',False):return None
        widget=getattr(event,'widget',None)
        if widget is not None:
            try:
                if widget.winfo_class() in {'Text','Entry','TEntry','TCombobox','Spinbox','TSpinbox'}:return None
            except AttributeError:pass
        track=self.audio_edit_working.get('dubbed')
        if track is None:return None
        clips=sorted(self._track_clips(track),key=lambda c:c.start)
        self.selected_clip_ids={c.id for c in clips};self.clip_selection_anchor=clips[0].id if clips else None
        self.stop(announce=False);self._sync_clip_selection()
        return 'break'

    def _delete_selected_clips(self):
        selected=self._selected_dubbed_clips()
        if not selected:return False
        track=self.audio_edit_working['dubbed'];fb=self._edit_frame_bytes(track)
        clips=self._track_clips(track);raw=track['frames']
        for clip in reversed(selected):
            end=clip.end(fb)
            clips=paste_clip(clips,clip.start,end,b'',fb)
            raw=raw[:clip.start*fb]+raw[end*fb:]
        self._set_edit_frames('dubbed',track,raw,clips=clips)
        self._set_audio_edit_status(f'{len(selected)} trecho(s) excluído(s). DESFAZER restaura.')
        return True

    def _clip_is_selected(self, clip, track):
        if getattr(self,'selected_clip_ids',set()):return clip.id in self.selected_clip_ids and self.waveform_selection_kind=='dubbed'
        drag = getattr(self, "clip_drag", None)
        if drag is not None:
            return clip.id == drag["id"]
        selected = self.waveform_selection_ranges.get("dubbed")
        if self.waveform_selection_kind != "dubbed" or selected is None:
            return False
        start, end = sorted(round(t * track["sample_rate"]) for t in selected)
        return start == clip.start and end == clip.end(self._edit_frame_bytes(track))

    @staticmethod
    def _selection_dark_color(color):
        try:
            return "#" + "".join(f"{max(0, int(color[i:i+2], 16) // 2):02x}" for i in (1, 3, 5))
        except (TypeError, ValueError):
            return "#064E3B"

    def _draw_clip_timeline(self, clips=None):
        canvas = getattr(self, "clip_timeline_canvas", None)
        if canvas is None:
            return
        try:
            self._configure_audio_view(canvas)
            canvas.delete("all")
            canvas.configure(bg=self.theme.get("input", "#FFFFFF"))
            track = self.audio_edit_working.get("dubbed") if self.audio_edit_mode else None
            if track is None:
                canvas.create_text(6, 13, text="EDITAR → clique na onda → DIVIDIR (Ctrl+I) → arraste as barras", anchor="w", fill=self.theme.get("muted", "#64748B"), font=("Segoe UI", 8))
                return
            clips = self._track_clips(track) if clips is None else clips
            width = max(180, canvas.winfo_width()) - 4
            scale = width * getattr(self, "waveform_zoom", 1.0) / self._clip_timeline_seconds() / track["sample_rate"]
            colors = button_style(self.theme, "highlight" if getattr(self,'original_reference_editor',False) else "success")
            frame_bytes = self._edit_frame_bytes(track)
            for index, clip in enumerate(clips):
                left, right = 2 + clip.start * scale, 2 + clip.end(frame_bytes) * scale
                tag = "clip_" + str(clip.id)
                canvas.create_rectangle(left, 3, right, 24, fill=self._selection_dark_color(colors["bg"]) if self._clip_is_selected(clip, track) else colors["bg"], outline=self.theme.get("text", "#1F2937"), width=1, tags=(tag,))
                if right - left > 40:
                    canvas.create_text((left+right)/2, 13, text=f"↔ {clip.id}", fill="#FFFFFF" if self._clip_is_selected(clip, track) else colors["fg"], font=("Segoe UI", 8, "bold"), tags=(tag,))
        except Exception:
            pass

    def _clip_drag_press(self, event):
        self.clip_drag = None
        if not self.audio_edit_mode or getattr(self, "audio_transform_busy", False):
            return
        track = self.audio_edit_working.get("dubbed")
        if track is None:
            return
        canvas = self.clip_timeline_canvas
        canvas.focus_set()
        width = max(180, canvas.winfo_width()) - 4
        frames_per_pixel = self._clip_timeline_seconds() * track["sample_rate"] / (width * getattr(self, "waveform_zoom", 1.0))
        position = (self._audio_canvas_x(canvas, event.x) - 2) * frames_per_pixel
        clips = self._track_clips(track)
        selected = next((c for c in clips if c.start <= position < c.end(self._edit_frame_bytes(track))), None)
        if selected is None:
            self.selected_clip_ids=set();self.clip_selection_anchor=None
            self.waveform_selection_ranges["dubbed"] = None
            self.waveform_selection_kind = None
            self._draw_clip_timeline()
            self._draw_waveform("dubbed")
            self._update_audio_edit_buttons()
            return
        if getattr(event,'state',0) & 5 or selected.id not in getattr(self,'selected_clip_ids',set()):
            self._select_clip(selected,getattr(event,'state',0))
        if getattr(event,'state',0) & 5:return
        self.waveform_selection_ranges["original"] = None
        self._draw_waveform("original")
        self.waveform_selection_ranges["dubbed"] = (selected.start / track["sample_rate"], selected.end(self._edit_frame_bytes(track)) / track["sample_rate"])
        self.waveform_selection_kind = "dubbed"
        self.stop(announce=False)
        self.clip_drag = {"track": track, "clips": clips, "id": selected.id, "ids": set(getattr(self,"selected_clip_ids",set())) or {selected.id}, "x": event.x, "start": selected.start, "scale": frames_per_pixel, "preview": clips, "frames": track["frames"]}
        self._draw_clip_timeline()
        self._draw_waveform("dubbed")
        self._update_audio_edit_buttons()
        self._set_audio_edit_status("Trecho selecionado (escuro). DELETE exclui; COPIAR copia. Arraste para mover.")

    def _clip_drag_motion(self, event):
        drag = getattr(self, "clip_drag", None)
        if drag is None or not self.audio_edit_mode:
            return
        track = drag["track"]
        if self.audio_edit_working.get("dubbed") is not track or track["frames"] != drag["frames"] or self._track_clips(track) != drag["clips"]:
            self.clip_drag = None
            return
        if not drag.get("moving") and abs(event.x - drag["x"]) < 4:
            return
        drag["moving"] = True
        frame_bytes = self._edit_frame_bytes(track)
        position = max(0, round(drag["start"] + (event.x - drag["x"]) * drag["scale"]))
        # Limita a prévia antes de reservar memória para o silêncio.
        max_bytes = max(256*1024*1024, len(track["frames"]) * 4)
        if (position * frame_bytes + len(track["frames"])) > max_bytes:
            self._set_audio_edit_status("Deslocamento muito grande; aproxime o trecho.")
            return
        if len(drag.get('ids',()))>1:
            preview=move_clip_group(drag['clips'],drag['ids'],round((event.x-drag['x'])*drag['scale']),frame_bytes)
        else:
            preview = move_clip(drag["clips"], drag["id"], position, frame_bytes)
        drag["preview"] = preview
        self._draw_clip_timeline(preview)
        selected = next(c for c in preview if c.id == drag["id"])
        self._set_audio_edit_status(f"Trecho em {self._format_wave_duration(selected.start / track['sample_rate'])}. Solte para aplicar; DESFAZER reverte.")

    def _clip_drag_release(self, event):
        self._clip_drag_motion(event)
        drag = getattr(self, "clip_drag", None)
        self.clip_drag = None
        if drag is None or not self.audio_edit_mode:
            return
        track = drag["track"]
        clips = drag["preview"]
        if clips == drag["clips"]:
            self._draw_clip_timeline()
            return
        try:
            frame_bytes = self._edit_frame_bytes(track)
            raw = render_clips(clips, frame_bytes, track["sample_width"], len(track["frames"]) // frame_bytes, max(256*1024*1024, len(track["frames"])*4))
            self._set_edit_frames("dubbed", track, raw, clips=clips)
            self.selected_clip_ids=set(drag.get('ids',{drag['id']}))
            self.clip_selection_anchor=drag['id']
            moved = next(c for c in clips if c.id == drag["id"])
            self.waveform_selection_ranges["dubbed"] = (moved.start / track["sample_rate"], moved.end(frame_bytes) / track["sample_rate"])
            self.waveform_selection_kind = "dubbed"
            self._draw_clip_timeline()
            self._draw_waveform("dubbed")
            self._update_audio_edit_buttons()
            self._sync_clip_selection()
            self._set_audio_edit_status("Trechos reposicionados; espaços vazios são silêncio. Ouça e use SALVAR. DESFAZER reverte.")
        except (ValueError, MemoryError) as exc:
            self._set_audio_edit_status("Não foi possível mover o trecho: " + str(exc))
            self._draw_clip_timeline()

    def _save_trash_preference(self):
        try:
            path=Path(self.project_root)/'Dublaskizon_ouvir_cena.json'
            path.write_text(json.dumps({'confirm_trash':self.trash_confirm_var.get()=='1'}),encoding='utf-8')
        except OSError as error:self._set_audio_edit_status(str(error))

    def _trash_current_scene(self):
        owners=[getattr(self,'translation_controller',None)]+[getattr(callback,'__self__',None) for callback in self.review_actions.values()]
        if self.audio_edit_dirty or getattr(self,'audio_transform_busy',False) or any(getattr(owner,'busy',False) for owner in owners if owner):
            self._set_audio_edit_status('Salve ou desfaça a edição e aguarde a dublagem antes de mover a cena.');return
        if self.scene_text_path and self.scene_text_box is not None:
            try:
                if self.scene_text_box.get('1.0','end-1c').strip()!=self.scene_text_path.read_text(encoding='utf-8-sig').strip():
                    self._set_audio_edit_status('Salve a alteração do TXT antes de mover a cena.');return
            except (OSError,UnicodeError):
                self._set_audio_edit_status('Não foi possível conferir o TXT; cena preservada.');return
        if getattr(self,'is_part_window',False):return
        original=self._current_audio_path('original')
        try:
            from project_trash import scene_files,move_scene
            root=Path(self.project_root)
            key=original.relative_to(root/'WAV ORIGINAIS').with_suffix('').as_posix() if original is not None and original.is_relative_to(root/'WAV ORIGINAIS') else self.current_context_key
            if not key:raise ValueError('Nenhuma cena do projeto selecionada.')
            files=scene_files(root,key)
            if not files:raise ValueError('Nenhum arquivo da cena encontrado.')
            if self.trash_confirm_var.get()=='1' and not messagebox.askyesno('Lixeira do projeto',f'Mover {len(files)} arquivos da cena {key} para lixeira do projeto?\nÁudios e TXT manterão nomes e pastas. Nenhum arquivo será apagado permanentemente.',parent=self.window):return
            self.stop(announce=False)
            moved=move_scene(root,key)
            self.emit_status(f'Cena {key}: {len(moved)} arquivos movidos para lixeira do projeto.')
            previous=self.current_index
            self.navigate(1 if self.current_index+1<len(self.navigation_paths) else -1)
            if self.current_index==previous:self.close_window()
        except (OSError,ValueError,RuntimeError) as error:self._set_audio_edit_status(str(error))

    def _switch_dubbed_version(self, latest=False):
        if getattr(self,'original_reference_editor',False):
            self._set_audio_edit_status('A recuperação é somente para o áudio dublado, não para o recorte original.')
            return
        owners=[getattr(self,'translation_controller',None)]+[getattr(callback,'__self__',None) for callback in self.review_actions.values()]
        if self.audio_edit_dirty or getattr(self,'audio_transform_busy',False) or any(getattr(owner,'busy',False) for owner in owners if owner):
            self._set_audio_edit_status('Salve ou desfaça a edição e aguarde o processamento antes de recuperar uma versão.')
            return
        target=self._current_audio_path('dubbed')
        if target is None:return
        try:
            from audio_versions import switch
            self.stop(announce=False)
            switch(target,self.project_root or target.parent,latest=latest)
            self.audio_edit_working.clear()
            self.audio_edit_undo_stack.clear()
            self.audio_edit_redo_stack.clear()
            self.refresh_current_scene()
            self._set_audio_edit_status(('Dublagem mais atual restaurada' if latest else 'Dublagem anterior recuperada')+': '+str(target))
        except (OSError,ValueError,wave.Error,EOFError) as error:
            self._set_audio_edit_status(str(error))

    def _reflow_audio_versions(self, bar, heading, row):
        try:
            required=bar.winfo_reqwidth()+12
            for widget in heading.pack_slaves():
                if widget is bar:continue
                padding=widget.pack_info().get('padx',0)
                padding=padding if isinstance(padding,(tuple,list)) else (padding,padding)
                required+=widget.winfo_reqwidth()+sum(int(v) for v in padding)+8
            mode='inline' if heading.winfo_width()>=required else 'wrapped'
            if getattr(bar,'layout_mode',None)==mode:return
            bar.pack_forget()
            if mode=='inline':bar.pack(in_=heading,side='left',padx=(12,0))
            else:bar.pack(in_=row,side='top',anchor='w',before=self.clip_timeline_canvas,padx=(12,0),pady=(3,2))
            bar.layout_mode=mode
        except Exception:
            pass

    def _update_audio_edit_buttons(self) -> None:
        has_selection = any(selection is not None for selection in self.waveform_selection_ranges.values())
        has_nonempty_selection = any(selection is not None and abs(float(selection[1]) - float(selection[0])) > 0.0001 for selection in self.waveform_selection_ranges.values())
        transform_enabled = self.audio_edit_mode and bool(self.audio_edit_working.get("dubbed")) and not getattr(self, "audio_transform_busy", False)
        for button, enabled in (
            (getattr(self,'audio_restore_previous_button',None), self._current_audio_path('dubbed') is not None and not getattr(self,'original_reference_editor',False)),
            (getattr(self,'audio_restore_latest_button',None), self._current_audio_path('dubbed') is not None and not getattr(self,'original_reference_editor',False)),
            (getattr(self,'audio_exact_duration_button',None), transform_enabled and self._current_audio_path('original') is not None),
            (getattr(self, 'audio_auto_align_button', None), transform_enabled and self._current_audio_path('original') is not None),
            (getattr(self, "audio_volume_minus_button", None), transform_enabled),
            (getattr(self, "audio_volume_plus_button", None), transform_enabled),
            (getattr(self, "audio_split_button", None), transform_enabled),
            (getattr(self, "audio_duration_minus_button", None), transform_enabled),
            (getattr(self, "audio_duration_plus_button", None), transform_enabled),
            (getattr(self, "audio_trim_silence_button", None), transform_enabled),
            (getattr(self, 'audio_internal_silence_button', None), transform_enabled),
            (self.audio_undo_button, self.audio_edit_mode and bool(self.audio_edit_undo_stack)),
            (self.audio_redo_button, self.audio_edit_mode and bool(self.audio_edit_redo_stack)),
            (self.audio_cut_button, self.audio_edit_mode and self.waveform_selection_kind == "dubbed" and has_nonempty_selection),
            (self.audio_delete_button, self.audio_edit_mode and self.waveform_selection_kind == "dubbed" and has_nonempty_selection),
            (self.audio_copy_button, self.audio_edit_mode and self.waveform_selection_kind in self.waveform_canvases and has_nonempty_selection),
            (self.audio_paste_button, self.audio_edit_mode and self.audio_clip_buffer is not None and has_selection),
            (self.audio_save_button, self.audio_edit_mode and self.audio_edit_dirty),
        ):
            if button is not None:
                try:
                    button.configure(state="normal" if enabled else "disabled")
                except Exception:
                    pass

    def _toggle_audio_edit(self) -> None:
        if not self.audio_edit_mode:
            loaded = []
            for kind in ("original", "dubbed"):
                if self._load_edit_track(kind) is not None:
                    loaded.append(kind)
            if not loaded:
                self._set_audio_edit_status("EDITAR requer pelo menos um WAV PCM legível na cena atual.")
                return
            self.stop(announce=False)
            self.audio_edit_mode = True
            self.selected_clip_ids=set();self.clip_selection_anchor=None
            self.audio_edit_undo_stack = []
            self.audio_edit_redo_stack = []
            self.audio_edit_base_frames = {kind: bytes(track.get("frames", b"")) for kind, track in self.audio_edit_working.items()}
            self.waveform_selection_ranges = {"original": None, "dubbed": None}
            self.waveform_selection_kind = None
            self._refresh_waveforms()
            self._set_audio_edit_status("EDITAR: clique no DUBLADO e use DIVIDIR/Ctrl+I. Arraste as barras para mover; arraste a onda para selecionar.")
        else:
            if self.audio_edit_dirty:
                try:
                    discard = messagebox.askyesno("Sair do modo EDITAR", "Há alterações não salvas. Deseja sair e descartar as alterações?", parent=self.window)
                except Exception:
                    discard = False
                if not discard:
                    return
            self.audio_edit_mode = False
            self.audio_edit_dirty = False
            self.audio_edit_working = {}
            self.audio_edit_undo_stack = []
            self.audio_edit_redo_stack = []
            self.audio_edit_base_frames = {}
            self.audio_clip_buffer = None
            self.waveform_selection_ranges = {"original": None, "dubbed": None}
            self.waveform_selection_kind = None
            self._refresh_waveforms()
            self._set_audio_edit_status("Modo EDITAR desativado.")
        if self.audio_edit_button is not None:
            self.audio_edit_button.configure(text=i18n.tr("SAIR DO EDITAR" if self.audio_edit_mode else "EDITAR"))
        self._update_audio_edit_buttons()

    def _prepare_audio_edit_scene_change(self) -> bool:
        """Confirma a saída do modo EDITAR antes de trocar de cena."""
        if not self.audio_edit_mode:
            return True
        if self.audio_edit_dirty:
            try:
                confirmed = messagebox.askyesno("Alterações não salvas", "Há alterações de áudio não salvas. Deseja descartá-las e trocar de cena?", parent=self.window)
            except Exception:
                confirmed = False
            if not confirmed:
                return False
        self.audio_edit_mode = False
        self.audio_edit_dirty = False
        self.audio_edit_working = {}
        self.audio_edit_undo_stack = []
        self.audio_edit_redo_stack = []
        self.audio_edit_base_frames = {}
        self.audio_clip_buffer = None
        self.waveform_selection_ranges = {"original": None, "dubbed": None}
        self.waveform_selection_kind = None
        self.waveform_drag_kind = None
        if self.audio_edit_button is not None:
            try:
                self.audio_edit_button.configure(text=i18n.tr("EDITAR"))
            except Exception:
                pass
        self._update_audio_edit_buttons()
        return True

    def _archive_audio_edit_backup(self, target: Path) -> Path | None:
        if not target.is_file():
            return None
        try:
            root = self.project_root or target.parent
            relative = target.resolve().relative_to((root / "dublado").resolve())
        except (ValueError, OSError):
            relative = Path(target.name)
        backup_dir = (self.project_root or target.parent) / "revisoes" / relative.parent
        backup_dir.mkdir(parents=True, exist_ok=True)
        stem = relative.stem
        version = 1
        while True:
            backup = backup_dir / f"{stem}_edit_v{version:02d}.wav"
            if not backup.exists():
                shutil.copy2(target, backup)
                return backup
            version += 1

    def _materialize_audio_edit_preview(self, kind: str = "dubbed") -> Path | None:
        """Gera uma cópia WAV segura da faixa em memória para o player reproduzir."""
        track = self.audio_edit_working.get(kind) or self._load_edit_track(kind)
        if track is None:
            return None
        old_preview = self.audio_edit_preview_path
        preview = None
        name = None
        try:
            descriptor, name = tempfile.mkstemp(prefix="dublaskizon_edit_preview_", suffix=".wav")
            os.close(descriptor)
            preview = Path(name)
            frames = bytes(track.get("frames", b""))
            channels = int(track["channels"])
            sample_width = int(track["sample_width"])
            sample_rate = int(track["sample_rate"])
            frame_bytes = max(1, channels * sample_width)
            if len(frames) % frame_bytes:
                raise wave.Error("frames PCM incompletos para pré-visualização")
            with wave.open(str(preview), "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.setcomptype("NONE", "not compressed")
                wav_file.writeframes(frames)
            with wave.open(str(preview), "rb") as check_file:
                if check_file.getnchannels() != channels or check_file.getsampwidth() != sample_width or check_file.getframerate() != sample_rate or check_file.getnframes() != len(frames) // frame_bytes:
                    raise wave.Error("WAV de pré-visualização não confere com a edição em memória")
            self.audio_edit_preview_path = preview
            if old_preview is not None and old_preview != preview:
                try:
                    old_preview.unlink(missing_ok=True)
                except OSError:
                    pass
            return preview
        except (OSError, EOFError, wave.Error, ValueError):
            if preview is not None:
                try:
                    preview.unlink(missing_ok=True)
                except OSError:
                    pass
            return None

    def _open_background_editor(self):
        try:
            from background_audio import BackgroundEditor
            existing = getattr(self, 'background_editor', None)
            if existing is not None and existing.window.winfo_exists():
                existing.window.lift()
                return
            self.background_editor = BackgroundEditor(self, self.background_gain_var.get())
        except Exception as exc:
            messagebox.showerror('Som de fundo', str(exc), parent=self.window)

    def _play_edit_preview(self, kind: str, start_seconds: float = 0.0) -> bool:
        # Uma nova reprodução precisa invalidar o processo antigo antes de
        # recriar o preview; caso contrário o FFplay pode continuar lendo a
        # versão anterior logo após COLAR.
        if self.process is not None or self.waveform_active_kind is not None:
            self.stop(announce=False)
        if kind == "dubbed":
            path = self._materialize_audio_edit_preview(kind)
        else:
            path = self._current_audio_path(kind)
        if path is None:
            self._set_audio_edit_status("Não há áudio editável disponível para reproduzir.")
            return False
        self._start_paths([path], kind, start_seconds=max(0.0, float(start_seconds or 0.0)))
        return True

    def _edit_selection_start(self, kind):
        selected = self.waveform_selection_ranges.get(kind)
        if selected is None:
            selected = self.waveform_selection_ranges.get(self.waveform_selection_kind)
        start = max(0.0, min(float(t) for t in selected)) if selected else 0.0
        track = self.audio_edit_working.get(kind)
        if track is not None:
            rate = max(1, track["sample_rate"])
            frames = len(track.get("frames", b"")) // self._edit_frame_bytes(track)
            start = min(start, max(0, frames - 1) / rate)
        return start

    def _toggle_edit_play_pause(self, _event=None):
        if not self.audio_edit_mode:
            return None
        active_kind = self.waveform_active_kind
        if active_kind in self.waveform_canvases and self.waveform_active_path is not None:
            elapsed = max(0.0, time.monotonic() - self.waveform_active_started_at)
            paused_at = min(self.waveform_active_duration, self.waveform_active_offset + elapsed)
            paused_path = self.waveform_active_path
            self.stop(announce=False, clear_pause=False)
            self.audio_paused_kind = active_kind
            self.audio_paused_path = paused_path
            self.audio_paused_seconds = paused_at
            self._set_audio_edit_status(f"Pausado em {self._format_wave_duration(paused_at)}. Pressione Espaço para continuar.")
            return "break"
        kind = self.audio_paused_kind or self.waveform_selection_kind or self._focused_waveform_kind() or "dubbed"
        start_seconds = self.audio_paused_seconds if self.audio_paused_kind == kind else self._edit_selection_start(kind)
        if self._play_edit_preview(kind, start_seconds):
            self.audio_paused_kind = None
            self.audio_paused_path = None
            self.audio_paused_seconds = 0.0
            self._set_audio_edit_status("Reproduzindo edição. Pressione Espaço para pausar.")
        return "break"

    def _save_audio_edit(self) -> None:
        track = self.audio_edit_working.get("dubbed")
        if not self.audio_edit_mode or not self.audio_edit_dirty or track is None:
            self._set_audio_edit_status("Não há edição de DUBLADO para salvar.")
            return
        target = Path(track["path"]).resolve()
        if target.suffix.casefold() not in {".wav", ".wave", ".waw"}:
            self._set_audio_edit_status("SALVAR edição requer um arquivo DUBLADO WAV.")
            return
        temporary = target.with_name(f".{target.stem}.dublaskizon_edit_{os.getpid()}.tmp.wav")
        backup = None
        try:
            self.stop(announce=False)
            temporary.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(temporary), "wb") as wav_file:
                wav_file.setnchannels(int(track["channels"]))
                wav_file.setsampwidth(int(track["sample_width"]))
                wav_file.setframerate(int(track["sample_rate"]))
                wav_file.setcomptype("NONE", "not compressed")
                wav_file.writeframes(track["frames"])
            with wave.open(str(temporary), "rb") as check_file:
                if check_file.getnchannels() != int(track["channels"]) or check_file.getsampwidth() != int(track["sample_width"]) or check_file.getframerate() != int(track["sample_rate"]):
                    raise wave.Error("cabeçalho WAV salvo não confere")
                if check_file.getnframes() != len(track["frames"]) // self._edit_frame_bytes(track):
                    raise wave.Error("quantidade de frames WAV salva não confere")
            if not getattr(self,'original_reference_editor',False):
                from audio_versions import archive
                archive(target,self.project_root or target.parent)
            backup = self._archive_audio_edit_backup(target)
            os.replace(temporary, target)
            layout_warning = ""
            try:
                self._save_clip_layout(track)
            except OSError as exc:
                layout_warning = f" Áudio salvo, mas as divisões não puderam ser registradas: {exc}"
            for item in self.audio_edit_working.values():
                item["saved_clips"] = self._track_clips(item)
            preview_path = self.audio_edit_preview_path
            self.audio_edit_preview_path = None
            if preview_path is not None:
                try:
                    preview_path.unlink(missing_ok=True)
                except OSError:
                    pass
            self.audio_edit_dirty = False
            self.audio_edit_base_frames = {kind: bytes(item.get("frames", b"")) for kind, item in self.audio_edit_working.items()}
            self.audio_edit_undo_stack = []
            self.audio_edit_redo_stack = []
            self.audio_paused_kind = None
            self.audio_paused_path = None
            self.audio_paused_seconds = 0.0
            self._refresh_waveforms()
            self._update_mode_buttons()
            suffix = f" Backup: {backup.name}." if backup is not None else ""
            self._set_audio_edit_status(f"DUBLADO salvo com segurança.{suffix}{layout_warning}")
            self._update_audio_edit_buttons()
        except (OSError, EOFError, wave.Error, ValueError) as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            self._set_audio_edit_status(f"Falha ao salvar edição: {exc}")

    @staticmethod
    def _format_wave_duration(seconds: float) -> str:
        total_hundredths = max(0, int(round(float(seconds) * 100)))
        minutes, remainder = divmod(total_hundredths, 6000)
        seconds_value, hundredths = divmod(remainder, 100)
        return f"{minutes:02d}:{seconds_value:02d}.{hundredths:02d}"

    @staticmethod
    def _audio_canvas_x(canvas, x):
        try:
            return float(canvas.canvasx(x))
        except (AttributeError, TypeError, ValueError):
            return float(x)

    def _audio_view_canvases(self):
        ruler = getattr(self, "waveform_navigation", None)
        return ([ruler.canvas] if ruler is not None else []) + list(self.waveform_canvases.values()) + ([self.clip_timeline_canvas] if getattr(self, "clip_timeline_canvas", None) is not None else [])

    def _configure_audio_view(self, canvas):
        try:
            width = max(180, canvas.winfo_width())
            extent = max(width, (width - 4) * getattr(self, "waveform_zoom", 1.0) + 4)
            canvas.configure(scrollregion=(0, 0, extent, canvas.winfo_height()))
            fraction = min(max(0, getattr(self, "waveform_scroll", 0.0)), max(0, 1 - width / extent))
            canvas.xview_moveto(fraction)
        except (AttributeError, TypeError, ValueError):
            pass

    def _scroll_audio_views(self, *args):
        canvases = self._audio_view_canvases()
        if not canvases:
            return
        canvases[0].xview(*args)
        self.waveform_scroll = canvases[0].xview()[0]
        for canvas in canvases[1:]:
            canvas.xview_moveto(self.waveform_scroll)
        for kind in self.waveform_canvases:
            self._draw_waveform(kind)
        self._draw_clip_timeline()

    def _set_waveform_zoom(self, zoom, anchor_canvas=None, anchor_x=None):
        zoom = min(8.0, max(0.125, float(zoom)))
        old = getattr(self, "waveform_zoom", 1.0)
        if abs(zoom-old) < 0.00001:
            return
        if getattr(self, "clip_drag", None) is not None or self.waveform_drag_kind is not None:
            return
        canvases = self._audio_view_canvases()
        reference = anchor_canvas or (canvases[0] if canvases else None)
        left = 0.0
        if reference is not None:
            width = max(180, reference.winfo_width())
            anchor = width/2 if anchor_x is None else float(anchor_x)
            position = (self._audio_canvas_x(reference, anchor)-2) / ((width-4)*old)
            extent = max(width,(width-4)*zoom+4)
            left = max(0, min(1-width/extent, (2+position*(width-4)*zoom-anchor)/extent))
        self.waveform_zoom = zoom
        self.waveform_scroll = left
        variable = getattr(self, "waveform_zoom_var", None)
        if variable is not None and abs(float(variable.get())-math.log2(zoom)) > 0.001:
            variable.set(math.log2(zoom))
        status = getattr(self, "waveform_zoom_status", None)
        if status is not None:
            status.set(f"{zoom*100:.0f}%")
        for kind in self.waveform_canvases:
            self._draw_waveform(kind)
        self._draw_clip_timeline()
        self._draw_zoom_slider()

    def _zoom_audio_wheel(self, event):
        delta = getattr(event, "delta", 0)
        steps = max(-4, min(4, delta/120)) if delta else (1 if getattr(event, "num", 0)==4 else -1)
        self._set_waveform_zoom(getattr(self, "waveform_zoom", 1.0) * 1.25**steps, event.widget, event.x)
        return "break"

    def _draw_zoom_slider(self):
        canvas = getattr(self, "waveform_zoom_slider", None)
        if canvas is None:
            return
        width = max(80, canvas.winfo_width())
        canvas.delete("all")
        color = button_style(self.theme, "success")["bg"]
        center = width / 2
        x = 14 + (math.log2(getattr(self, "waveform_zoom", 1.0)) + 3) / 6 * (width-28)
        canvas.create_line(14, 13, width-14, 13, fill=self.theme.get("border", "#64748B"), width=4)
        canvas.create_line(center, 7, center, 19, fill=self.theme.get("muted", "#64748B"), width=1)
        canvas.create_oval(x-7, 6, x+7, 20, fill=color, outline=self.theme.get("text", "#FFFFFF"), width=1)

    def _zoom_slider_pointer(self, event):
        event.widget.focus_set()
        width = max(80, event.widget.winfo_width())
        fraction = max(0.0, min(1.0, (event.x-14)/(width-28)))
        self._set_waveform_zoom(2**(-3+6*fraction))
        return "break"

    def _bind_audio_zoom(self, canvas):
        canvas.bind("<Control-MouseWheel>", self._zoom_audio_wheel)
        canvas.bind("<Control-Button-4>", self._zoom_audio_wheel)
        canvas.bind("<Control-Button-5>", self._zoom_audio_wheel)

    def _waveform_plot_width(self, kind: str, width: int) -> float:
        data = self.waveform_data.get(kind) or {}
        duration = max(0.0, float(data.get("duration", 0.0) or 0.0))
        reference_duration = max(duration, float(self.waveform_reference_duration or 0.0))
        duration_ratio = duration / reference_duration if reference_duration > 0 else 1.0
        return max(8.0, (max(180, int(width)) - 4) * getattr(self, "waveform_zoom", 1.0) * min(1.0, duration_ratio))

    def _seek_from_waveform(self, kind: str, event) -> None:
        """Inicia a faixa no instante correspondente ao ponto clicado."""
        if kind not in {"original", "dubbed", "instrumental", "vocals", "suppression"}:
            return
        if self.playback_mode == "windows":
            self.emit_status("A busca por clique nas ondas exige o player FFplay interno.")
            return
        data = self.waveform_data.get(kind) or {}
        path = self._current_audio_path(kind)
        duration = float(data.get("duration", 0.0) or 0.0)
        canvas = self.waveform_canvases.get(kind)
        if canvas is None or path is None or duration <= 0:
            self.emit_status("Não é possível escolher o ponto: onda ou duração indisponível.")
            return
        try:
            width = max(180, int(canvas.winfo_width()))
            plot_width = self._waveform_plot_width(kind, width)
            start_x = 2.0
            end_x = start_x + plot_width
            click_x = max(start_x, min(self._audio_canvas_x(canvas, event.x), end_x))
            start_seconds = duration * (click_x - start_x) / max(1.0, plot_width)
        except (AttributeError, TypeError, ValueError, tk.TclError):
            return
        self._start_paths([path], kind, start_seconds=start_seconds)
        self.emit_status(f"Reprodução {kind} iniciada em {self._format_wave_duration(start_seconds)}")

    def _draw_waveform(self, kind: str) -> None:
        canvas = self.waveform_canvases.get(kind)
        if canvas is None:
            return
        try:
            self._configure_audio_view(canvas)
            canvas.delete("waveform")
            canvas.delete("waveform_selection")
            canvas.delete("waveform_end")
            canvas.delete("clip_boundary")
            canvas.delete("progress")
            width = max(180, int(canvas.winfo_width()))
            height = max(36, int(canvas.winfo_height()))
            data = self.waveform_data.get(kind)
            if not data:
                canvas.create_text(width / 2, height / 2, text=i18n.tr("Onda não disponível para este áudio"), fill=self.theme.get("muted", "#64748B"), tags="waveform")
                return
            samples = data.get("samples") or []
            if not samples:
                canvas.create_text(width / 2, height / 2, text=i18n.tr("Áudio sem amostras"), fill=self.theme.get("muted", "#64748B"), tags="waveform")
                return
            center = height / 2.0
            amplitude = max(8.0, height * 0.42)
            role = "accent" if kind == "original" else "success"
            if kind=='dubbed' and getattr(self,'original_reference_editor',False):role='highlight'
            try:
                color = button_style(self.theme, role)["bg"]
            except Exception:
                color = "#7C3AED" if kind == "original" else "#15803D"
            if kind in {'instrumental','vocals','suppression'}:
                from audacity_scene_ui import COLORS
                color=COLORS[kind]
            plot_width = self._waveform_plot_width(kind, width)
            # Draw only the visible peaks; retain detail at high zoom without thousands of Tk items.
            view_left = self._audio_canvas_x(canvas, 0)
            view_right = view_left + width
            count = max(1, len(samples)-1)
            first = max(0, int((view_left-2) / max(1, plot_width) * count)-1)
            last = min(len(samples), int((view_right-2) / max(1, plot_width) * count)+2)
            stride = max(1, int(len(samples) / max(1, plot_width)))
            for index in range(first, last, stride):
                value = max(samples[index:min(index+stride, len(samples))])
                x = 2 + plot_width * index / count
                canvas.create_line(x, center-value*amplitude, x, center+value*amplitude, fill=color, width=max(1, plot_width*stride/count), tags="waveform")
            end_x = 2 + plot_width
            canvas.create_line(end_x, 3, end_x, height - 3, fill=color, width=4, tags="waveform_end")
            if kind == "dubbed" and self.audio_edit_mode and self.audio_edit_working.get(kind):
                track = self.audio_edit_working[kind]
                for clip in self._track_clips(track):
                    x = 2 + plot_width * (clip.start / track["sample_rate"]) / max(0.0001, data["duration"])
                    canvas.create_line(x, 1, x, height-1, fill=self.theme.get("text", "#1F2937"), dash=(3, 3), tags="clip_boundary")
            selection = self.waveform_selection_ranges.get(kind) if self.audio_edit_mode else None
            selections=[selection] if selection is not None else []
            if kind=='dubbed' and self._selected_dubbed_clips():
                track=self.audio_edit_working[kind]
                selections=[(c.start/track['sample_rate'],c.end(self._edit_frame_bytes(track))/track['sample_rate']) for c in self._selected_dubbed_clips()]
            for selection in selections:
                selection_start, selection_end = sorted((float(selection[0]), float(selection[1])))
                selection_x1 = 2 + plot_width * selection_start / max(0.0001, float(data.get("duration", 0.0) or 0.0))
                selection_x2 = 2 + plot_width * selection_end / max(0.0001, float(data.get("duration", 0.0) or 0.0))
                canvas.create_rectangle(selection_x1, 3, selection_x2, height - 3, fill=self._selection_dark_color(color), outline=color, width=1, tags="waveform_selection")
                canvas.tag_lower("waveform_selection", "waveform")
            if self.waveform_active_kind == kind:
                progress = min(1.0, max(0.0, float(self.waveform_progress.get(kind, 0.0) or 0.0)))
                progress_x = 2 + (plot_width - 2) * progress
                canvas.create_line(2, height - 4, progress_x, height - 4, fill=color, width=4, tags="progress")
                canvas.create_line(progress_x, 4, progress_x, height - 5, fill=color, width=2, tags="progress")
                canvas.create_oval(progress_x - 4, height - 8, progress_x + 4, height, fill=color, outline=color, tags="progress")
            navigation=getattr(self,"waveform_navigation",None)
            if navigation is not None:
                navigation.draw();navigation.mark(kind)
        except Exception:
            pass

    def _refresh_waveforms(self) -> None:
        paths = {
            "original": self._current_audio_path("original"),
            "dubbed": self._current_audio_path("dubbed"),
        }
        treated=getattr(self,'audacity_ui',None)
        if treated is not None:
            treated.refresh()
            paths.update({kind:treated.paths.get(kind) for kind in ('instrumental','vocals','suppression')})
        for kind, path in paths.items():
            working = self.audio_edit_working.get(kind) if self.audio_edit_mode else None
            if working is not None:
                self.waveform_data[kind] = self._waveform_from_pcm(working.get("frames", b""), working.get("channels", 1), working.get("sample_width", 2), working.get("sample_rate", 1), points=5600)
            else:
                self.waveform_data[kind] = self._read_waveform(path, points=5600)
        self.waveform_reference_duration = max(
            (float((data or {}).get("duration", 0.0) or 0.0) for data in self.waveform_data.values()),
            default=0.0,
        )
        if self.audio_edit_mode and self.audio_edit_working.get("dubbed"):
            self.waveform_reference_duration *= 1.25
        self._draw_clip_timeline()
        for kind in paths:
            data = self.waveform_data.get(kind)
            duration_var = self.waveform_duration_vars.get(kind)
            if duration_var is not None:
                if data is None:
                    duration_var.set(i18n.tr("Duração: indisponível"))
                else:
                    channel_label = "mono" if data.get("channels") == 1 else f"{data.get('channels')} {i18n.tr('canais')}"
                    duration_var.set(f"{i18n.tr('Duração:')} {self._format_wave_duration(data.get('duration', 0.0))} | {data.get('sample_rate', 0)} Hz | {channel_label}")
            self._draw_waveform(kind)

    def _scene_text_key(self) -> str | None:
        key = self.current_context_key
        if key:
            return str(key)
        path = self._current_audio_path("dubbed") or self._current_audio_path("original") or self._current_audio_path()
        return path.stem if path is not None else None

    def _refresh_scene_text(self) -> None:
        parts = getattr(self, "scene_parts_ui", None)
        if parts is not None:
            parts.refresh()
        editor_refresh=getattr(self,'scene_editor_refresh',None)
        if callable(editor_refresh):
            editor_refresh()
            return
        if self.scene_text_box is None:
            return
        key = self._scene_text_key()
        title = "Nenhum áudio selecionado"
        text_value = ""
        text_path = None
        if key:
            path = self._current_audio_path("dubbed") or self._current_audio_path("original") or self._current_audio_path()
            title = f"Áudio: {path.name if path is not None else key}"
            loader = self.scene_text_loader
            if callable(loader):
                try:
                    result = loader(key)
                    if isinstance(result, dict):
                        title = str(result.get("title") or title)
                        text_value = str(result.get("text") or "")
                        text_path = result.get("path")
                    elif isinstance(result, (tuple, list)):
                        if len(result) >= 1 and result[0]:
                            text_value = str(result[0])
                        if len(result) >= 2 and result[1]:
                            text_path = result[1]
                        if len(result) >= 3 and result[2]:
                            title = str(result[2])
                    elif result is not None:
                        text_value = str(result)
                except Exception as exc:
                    text_value = ""
                    if self.scene_text_status_var is not None:
                        self.scene_text_status_var.set(f"Não foi possível carregar o texto: {exc}")
            else:
                text_value = ""
        if getattr(self, 'show_original_text', False) and key:
            controller = getattr(self, 'translation_controller', None)
            text_path = getattr(controller, 'original_text_by_stem', {}).get(key)
            try: text_value = Path(text_path).read_text(encoding='utf-8-sig') if text_path else ''
            except (OSError, UnicodeError): text_value = ''
            title = 'TEXTO ORIGINAL — ' + key
        self.scene_text_path = Path(text_path).expanduser().resolve() if text_path else None
        try:
            self.scene_text_title_var.set(title)
            self.scene_text_box.configure(state="normal")
            self.scene_text_box.delete("1.0", END)
            self.scene_text_box.insert("1.0", text_value)
            self.scene_text_box.edit_modified(False)
            self.scene_text_box.configure(state="normal")
            if self.scene_text_status_var is not None:
                self.scene_text_status_var.set("Texto carregado; edite e clique em SALVAR ALTERAÇÃO antes de redublar.") if self.scene_text_path is not None else self.scene_text_status_var.set("TXT da cena não encontrado.")
            if self.scene_text_save_button is not None:
                self.scene_text_save_button.configure(state="normal" if callable(self.scene_text_saver) and self.scene_text_path is not None else "disabled")
            if getattr(self, 'show_original_text', False):
                self.scene_text_box.configure(state='disabled')
                self.scene_text_save_button.configure(state='disabled')
                self.scene_text_status_var.set('Texto original para consulta. A redublagem usa a tradução selecionada.')
            self._refresh_scene_translation_folders()
        except Exception:
            pass

    def _allow_translation_switch(self):
        if getattr(self, 'show_original_text', False): return True
        if self.scene_text_box is None or self.scene_text_path is None:return True
        try:saved=self.scene_text_path.read_text(encoding='utf-8-sig')
        except (OSError,UnicodeError):saved=''
        if self.scene_text_box.get('1.0','end-1c').strip()==saved.strip():return True
        return messagebox.askyesno('Texto não salvo','Descartar as alterações deste texto e trocar a tradução? Para mantê-las, escolha Não e use Salvar alteração.',parent=self.window)

    def _choose_scene_translation(self):
        controller=getattr(self,'translation_controller',None)
        if controller is None or controller.busy or not self._allow_translation_switch():return
        controller.select_other_translation_folder()
        self._refresh_scene_translation_folders()
        self._refresh_scene_text()

    def _select_scene_translation_folder(self,folder):
        controller=getattr(self,'translation_controller',None)
        key=self._scene_text_key()
        if controller is None or not key or controller.busy or not self._allow_translation_switch():return
        self.show_original_text = False
        controller.select_other_translation_subfolder(folder)
        controller.refresh_other_translation_text(key)
        controller.use_other_translation_var.set('1' if controller.selected_other_translation_file else '0')
        self._refresh_scene_translation_folders()
        self._refresh_scene_text()
        if not controller.selected_other_translation_file and self.scene_text_status_var is not None:
            self.scene_text_status_var.set('Esta pasta não tem TXT correspondente à cena. Tradução principal exibida.')

    def _refresh_scene_translation_folders(self):
        bar=getattr(self,'scene_translation_folders_bar',None)
        controller=getattr(self,'translation_controller',None)
        if bar is None or controller is None:return
        try:
            from .review_tab import other_translation_folders
        except ImportError:
            from review_tab import other_translation_folders
        for child in bar.winfo_children():child.destroy()
        root=controller.other_translation_root_dir
        folders=[folder for folder in other_translation_folders(root) if (folder / (str(self._scene_text_key())+'.txt')).is_file()]
        if (root / (str(self._scene_text_key())+'.txt')).is_file():folders.insert(0,root)
        if not folders:
            Label(bar,text='Nenhuma pasta em OUTRAS TRADUÇÕES',bg=self.theme.get('surface','#FFFFFF'),fg=self.theme.get('text','#111827')).grid(row=0,column=0,sticky='w')
        for index,folder in enumerate(folders):
            active=folder==controller.other_translation_dir and controller.use_other_translation_var.get()=='1'
            button=Button(bar,text=folder.name,command=lambda path=folder:self._select_scene_translation_folder(path),relief='flat',font=('Segoe UI',8,'bold'),padx=7,pady=3)
            apply_button_style(button,self.theme,'accent' if active else 'secondary')
            button.grid(row=0,column=index,sticky='w',padx=(0,4),pady=0)
        for col in range(3):bar.grid_columnconfigure(col,weight=0)

    def _toggle_scene_translation(self):
        controller=getattr(self,'translation_controller',None)
        if controller is None:return
        if not self._allow_translation_switch():
            principal=controller.text_by_stem.get(self._scene_text_key())
            controller.use_other_translation_var.set('0' if self.scene_text_path==principal else '1')
            return
        controller.refresh_other_translation_text(self._scene_text_key())
        controller.on_other_translation_toggle()
        self._refresh_scene_translation_folders()
        self._refresh_scene_text()

    def _show_main_scene_translation(self):
        controller=getattr(self,'translation_controller',None)
        if controller is None:return
        if not self._allow_translation_switch():return
        self.show_original_text = False
        controller.use_other_translation_var.set('0')
        self._refresh_scene_translation_folders()
        self._refresh_scene_text()

    def _show_original_scene_text(self):
        if not self._allow_translation_switch(): return
        self.show_original_text = True
        self._refresh_scene_text()

    def _save_scene_text_from_window(self) -> None:
        key = self._scene_text_key()
        saver = self.scene_text_saver
        if not key or not callable(saver) or self.scene_text_box is None:
            self.emit_status("Não há texto português editável para a cena atual.")
            return
        try:
            text_value = self.scene_text_box.get("1.0", "end-1c")
            result = saver(key, text_value)
            success = True
            message = "Texto em português salvo para a cena atual."
            if isinstance(result, (tuple, list)):
                success = bool(result[0]) if result else True
                if len(result) > 1 and result[1]:
                    message = str(result[1])
            elif isinstance(result, dict):
                success = bool(result.get("success", True))
                message = str(result.get("message") or message)
            elif isinstance(result, str):
                message = result
            elif result is False:
                success = False
            if success:
                self._refresh_scene_text()
            if self.scene_text_status_var is not None:
                self.scene_text_status_var.set(message)
            self.emit_status(message)
        except Exception as exc:
            if self.scene_text_status_var is not None:
                self.scene_text_status_var.set(f"Não foi possível salvar o texto: {exc}")
            self.emit_status(f"Não foi possível salvar o texto: {exc}")

    def _build_review_panel(self, parent, surface: str, text_color: str) -> None:
        self.review_panel = Frame(parent, bg=surface, bd=1, relief="solid")
        self.review_panel.pack(fill="both", expand=True)
        self.review_panel_widgets = [self.review_panel]
        input_bg = self.theme.get("input", surface)
        input_fg = self.theme.get("input_text", text_color)
        muted = self.theme.get("muted", "#64748B")
        border = self.theme.get("border", "#CBD5E1")
        title_label = Label(self.review_panel, text=i18n.tr("REVISÃO DA CENA"), bg=surface, fg=text_color, font=("Segoe UI", 9, "bold"), anchor="w")
        title_label.pack(fill="x", padx=8, pady=(5, 2))
        self.review_panel_widgets.append(title_label)
        body = Frame(self.review_panel, bg=surface)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 5))
        self.review_panel_widgets.append(body)
        history_column = Frame(body, bg=surface)
        history_column.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.review_panel_widgets.append(history_column)
        history_label = Label(history_column, text=i18n.tr("HISTÓRICO DA CENA"), bg=surface, fg=text_color, font=("Segoe UI", 8, "bold"), anchor="w")
        history_label.pack(fill="x", pady=(0, 2))
        self.review_panel_widgets.append(history_label)
        history_frame = Frame(history_column, bg=surface)
        history_frame.pack(fill="both", expand=True)
        self.review_panel_widgets.append(history_frame)
        self.review_history_box = Text(history_frame, height=3, width=42, wrap="word", state="disabled", font=("Consolas", 8), bg=input_bg, fg=input_fg, insertbackground=input_fg, relief="solid", bd=1)
        history_scroll = Scrollbar(history_frame, orient="vertical", command=self.review_history_box.yview)
        self.review_history_box.configure(yscrollcommand=history_scroll.set)
        self.review_history_box.pack(side="left", fill="both", expand=True)
        history_scroll.pack(side="right", fill="y")
        progress_column = Frame(body, bg=surface)
        progress_column.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.review_panel_widgets.append(progress_column)
        phase_label = Label(progress_column, text=i18n.tr("REFAZENDO A CENA"), bg=surface, fg=text_color, font=("Segoe UI", 8, "bold"), anchor="w")
        phase_label.pack(fill="x", pady=(0, 2))
        self.review_panel_widgets.append(phase_label)
        style = ttk.Style(self.window)
        clone_color = "#60A5FA" if self.theme.get("mode") != "claro" else "#2563EB"
        dub_color = "#A78BFA" if self.theme.get("mode") != "claro" else "#7C3AED"
        style.configure("AudioReviewClone.Horizontal.TProgressbar", troughcolor=border, background=clone_color, lightcolor=clone_color, darkcolor=clone_color)
        style.configure("AudioReviewDub.Horizontal.TProgressbar", troughcolor=border, background=dub_color, lightcolor=dub_color, darkcolor=dub_color)
        clone_label = Label(progress_column, text=i18n.tr("CLONANDO REFERÊNCIA"), bg=surface, fg=muted, font=("Segoe UI", 7, "bold"), anchor="w")
        clone_label.pack(fill="x")
        self.review_panel_widgets.append(clone_label)
        self.review_clone_var = DoubleVar(value=0.0)
        self.review_clone_bar = ttk.Progressbar(progress_column, orient="horizontal", mode="determinate", maximum=100, variable=self.review_clone_var, style="AudioReviewClone.Horizontal.TProgressbar")
        self.review_clone_bar.pack(fill="x", pady=(1, 3))
        dub_label = Label(progress_column, text=i18n.tr("DUBLANDO CENA"), bg=surface, fg=muted, font=("Segoe UI", 7, "bold"), anchor="w")
        dub_label.pack(fill="x")
        self.review_panel_widgets.append(dub_label)
        self.review_dub_var = DoubleVar(value=0.0)
        self.review_dub_bar = ttk.Progressbar(progress_column, orient="horizontal", mode="determinate", maximum=100, variable=self.review_dub_var, style="AudioReviewDub.Horizontal.TProgressbar")
        self.review_dub_bar.pack(fill="x", pady=(1, 3))
        self.review_phase_var = StringVar(value=i18n.tr("Pronto para refazer a cena"))
        phase_status = Label(progress_column, textvariable=self.review_phase_var, bg=surface, fg=muted, font=("Segoe UI", 7), anchor="w")
        phase_status.pack(fill="x", pady=(0, 2))
        self.review_panel_widgets.append(phase_status)
        regen_label = Label(progress_column, text=i18n.tr("PROCESSOS DE REFAZIMENTO"), bg=surface, fg=text_color, font=("Segoe UI", 8, "bold"), anchor="w")
        regen_label.pack(fill="x", pady=(0, 2))
        self.review_panel_widgets.append(regen_label)
        regen_frame = Frame(progress_column, bg=surface)
        regen_frame.pack(fill="both", expand=True)
        self.review_panel_widgets.append(regen_frame)
        self.review_regen_box = Text(regen_frame, height=3, width=42, wrap="word", state="disabled", font=("Consolas", 8), bg=input_bg, fg=input_fg, insertbackground=input_fg, relief="solid", bd=1)
        regen_scroll = Scrollbar(regen_frame, orient="vertical", command=self.review_regen_box.yview)
        self.review_regen_box.configure(yscrollcommand=regen_scroll.set)
        self.review_regen_box.pack(side="left", fill="both", expand=True)
        regen_scroll.pack(side="right", fill="y")
        self._refresh_review_snapshot()

    def _build_review_progress_controls(self, parent, surface: str, text_color: str) -> None:
        """Cria apenas os indicadores compactos de clonagem e dublagem."""
        input_border = self.theme.get("border", "#CBD5E1")
        muted = self.theme.get("muted", "#64748B")
        frame = Frame(parent, bg=surface, height=64)
        frame.pack(side="left", fill="x", expand=True, padx=4)
        frame.pack_propagate(False)
        self.review_progress_frame = frame
        self.review_progress_widgets = [frame]
        controller = getattr(self, 'translation_controller', None)
        if controller is not None and hasattr(controller, 'control_generation'):
            stop_controls = Frame(frame, bg=surface)
            stop_controls.pack(side='right', padx=(6, 0))
            for label, after_scene, role in [('PARAR APÓS CENA', True, 'warning'), ('CANCELAR', False, 'danger')]:
                button = Button(stop_controls, text=i18n.tr(label),
                                command=lambda after=after_scene: controller.control_generation(after),
                                relief='flat', font=('Segoe UI', 7, 'bold'), padx=5, pady=3)
                apply_button_style(button, self.theme, role)
                button.pack(fill='x', pady=1)
        style = ttk.Style(self.window)
        clone_color = button_style(self.theme, "primary")["bg"] if button_style is not None else "#2563EB"
        dub_color = button_style(self.theme, "success")["bg"] if button_style is not None else "#15803D"
        style.configure("AudioReviewClone.Horizontal.TProgressbar", troughcolor=input_border, background=clone_color, lightcolor=clone_color, darkcolor=clone_color)
        style.configure("AudioReviewDub.Horizontal.TProgressbar", troughcolor=input_border, background=dub_color, lightcolor=dub_color, darkcolor=dub_color)
        clone_column = Frame(frame, bg=surface)
        clone_column.pack(side="top", fill="x", expand=True)
        self.review_progress_widgets.append(clone_column)
        clone_label = Label(clone_column, text=i18n.tr("CLONANDO REFERÊNCIA"), bg=surface, fg=muted, font=("Segoe UI", 7, "bold"), anchor="w")
        clone_label.pack(side='left')
        self.review_progress_widgets.append(clone_label)
        self.review_clone_var = DoubleVar(value=0.0)
        self.review_clone_bar = ttk.Progressbar(clone_column, length=100, orient="horizontal", mode="determinate", maximum=100, variable=self.review_clone_var, style="AudioReviewClone.Horizontal.TProgressbar")
        self.review_clone_bar.pack(side='left', fill="x", expand=True, padx=4)
        dub_column = Frame(frame, bg=surface)
        dub_column.pack(side="top", fill="x", expand=True)
        self.review_progress_widgets.append(dub_column)
        dub_label = Label(dub_column, text=i18n.tr("DUBLANDO CENA"), bg=surface, fg=muted, font=("Segoe UI", 7, "bold"), anchor="w")
        dub_label.pack(side='left')
        self.review_progress_widgets.append(dub_label)
        self.review_dub_var = DoubleVar(value=0.0)
        self.review_dub_bar = ttk.Progressbar(dub_column, length=100, orient="horizontal", mode="determinate", maximum=100, variable=self.review_dub_var, style="AudioReviewDub.Horizontal.TProgressbar")
        self.review_dub_bar.pack(side='left', fill="x", expand=True, padx=4)
        if self.audacity_ui is not None:self.audacity_ui.attach_progress(frame)
        self._refresh_review_snapshot()

    def set_editor_mode(self, mode):
        if mode not in ('simple','advanced'):return
        if mode==getattr(self,'editor_mode','advanced'):return
        if getattr(self,'audio_transform_busy',False) or getattr(getattr(self,'audacity_ui',None),'busy',False) or getattr(getattr(self,'scene_parts_ui',None),'busy',False):
            messagebox.showinfo('Editor','Aguarde o processamento atual antes de trocar de editor.',parent=self.window)
            return
        if not self._allow_translation_switch():return
        if not self._prepare_audio_edit_scene_change():return
        self.editor_mode=mode
        self.show_window(self.pending_title or 'OUVIR CENA','')

    def show_window(self, title: str, initial_text: str):
        if getattr(self,'editor_mode','advanced')=='simple' and not getattr(self,'is_part_window',False):
            from simple_scene_editor import show_simple_window
            return show_simple_window(self,title,initial_text)
        if not TK_AVAILABLE:
            return
        # Preserva pending_paths: play_one/play_all já colocaram os arquivos na fila.
        self._destroy_window(clear_pending=False)
        window = Toplevel(self.parent)
        window.title(i18n.tr(title))
        try:
            screen_width, screen_height = window.winfo_screenwidth(), window.winfo_screenheight()
            available_height = max(360, int(screen_height) - 100)
        except Exception:
            available_height = 760
            screen_width, screen_height = 1920, 1080
        opening_width = min(screen_width-40, max(1100, round(screen_width*.675)))
        opening_height = min(available_height, max(820, round(screen_height*.83)))
        opening_x = min(round(screen_width*.232), screen_width-opening_width-20)
        opening_y = min(round(screen_height*.055), screen_height-opening_height-60)
        opening_geometry = f'{opening_width}x{opening_height}+{max(0,opening_x)}+{max(0,opening_y)}'
        window.geometry(opening_geometry)
        window.minsize(min(900, screen_width-40), min(500, available_height))
        window.resizable(True, True)
        # Mantém a decoração normal do Windows para que o botão nativo de
        # maximizar/restaurar apareça junto de minimizar e X FECHAR.
        try:
            window.wm_attributes("-toolwindow", False)
        except Exception:
            pass
        window.protocol("WM_DELETE_WINDOW", self.close_window)
        window.bind("<space>", self._on_edit_space, add="+")
        window.bind("<Control-a>", self._select_all_dubbed_clips, add="+")
        window.bind("<Control-A>", self._select_all_dubbed_clips, add="+")
        try:
            window.lift()
            window.focus_force()
        except Exception:
            pass
        self.window = window
        previous_audacity=getattr(self,'audacity_ui',None)
        if previous_audacity is not None:previous_audacity.cancel.set()
        from audacity_scene_ui import AudacitySceneUI
        self.audacity_ui=AudacitySceneUI(self) if not getattr(self,'is_part_window',False) else None
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
        controller=getattr(self,'translation_controller',None)
        if not getattr(self,'is_part_window',False) and controller is not None and all(hasattr(controller,name) for name in ('scene_list','scene_sort_var','audio_source_var','review_totals_var')):
            from scene_review_drawer import SceneReviewDrawer
            self.review_drawer=SceneReviewDrawer(self,controller,content)
            content=self.review_drawer.main
        if not getattr(self, "is_part_window", False):
            try:
                from .scene_parts import ScenePartsUI
            except ImportError:
                from scene_parts import ScenePartsUI
            if not hasattr(self, "scene_parts_ui"):
                self.scene_parts_ui = ScenePartsUI(self)
            content = self.scene_parts_ui.attach(content)
        wave_host=content
        if self.audacity_ui is not None:
            wave_outer=Frame(content,bg=surface)
            wave_outer.pack(side='top',fill='x',padx=14,pady=(0,8))
            wave_view=Canvas(wave_outer,bg=surface,highlightthickness=0,height=350)
            from waveform_navigation import scroll_vertical
            wave_scroll=Scrollbar(wave_outer,orient='vertical',command=lambda *args:scroll_vertical(self,*args))
            wave_view.configure(yscrollcommand=wave_scroll.set)
            wave_view.pack(side='left',fill='both',expand=True)
            wave_scroll.pack(side='right',fill='y')
            wave_host=wave_view
            self.waveform_vertical_view=wave_view
        self.waveform_panel = Frame(wave_host, bg=surface, bd=1, relief="solid")
        if self.audacity_ui is None:
            self.waveform_panel.pack(side="top", fill="x", expand=False, padx=14, pady=(0, 8))
        else:
            wave_item=wave_view.create_window(0,0,window=self.waveform_panel,anchor='nw')
            def fit_wave_area(_event=None):
                try:
                    wave_view.itemconfigure(wave_item,width=max(1,wave_view.winfo_width()))
                    other=sum(w.winfo_reqheight()+12 for w in content.pack_slaves() if w not in (wave_outer,text_panel))
                    height=max(100,min(self.waveform_panel.winfo_reqheight(),content.winfo_height()-other-text_panel.winfo_reqheight()-40))
                    if int(wave_view.cget('height'))!=height:wave_view.configure(height=height)
                    wave_view.configure(scrollregion=wave_view.bbox('all'))
                    scroll_vertical(self)
                except (NameError,tk.TclError):pass
            wave_view.bind('<Configure>',fit_wave_area)
            self.waveform_panel.bind('<Configure>',fit_wave_area)
            content.bind('<Configure>',fit_wave_area,add='+')
        self.waveform_widgets = [self.waveform_panel]
        zoom_row = Frame(self.waveform_panel, bg=surface)
        zoom_row.pack(fill="x", padx=10, pady=(4, 4))
        try:confirm=json.loads((Path(self.project_root)/'Dublaskizon_ouvir_cena.json').read_text(encoding='utf-8')).get('confirm_trash',True)
        except (OSError,ValueError,TypeError):confirm=True
        self.trash_confirm_var=StringVar(value='1' if confirm else '0')
        self.trash_confirm_button=ttk.Checkbutton(zoom_row,text='Confirmar ao mover',variable=self.trash_confirm_var,command=self._save_trash_preference)
        self.project_trash_button=Button(zoom_row,text='MOVER ORIGINAL + DUBLADO + TXT PARA LIXEIRA DO PROJETO',wraplength=220,command=self._trash_current_scene,relief='flat',font=('Segoe UI',7,'bold'),padx=4,pady=1)
        apply_button_style(self.project_trash_button,self.theme,'warning')
        self.project_trash_button.pack(side='left',padx=(0,4))
        self.trash_confirm_button.pack(side='left',padx=(0,8))
        from review_memory_ui import mount_scene_controls
        self.scene_memory_controls=mount_scene_controls(self,zoom_row)
        if getattr(self,'is_part_window',False):self.project_trash_button.configure(state='disabled')
        self.waveform_widgets.append(zoom_row)
        zoom_extra = Frame(self.waveform_panel, bg=surface)
        zoom_tools = Frame(self.waveform_panel, bg=surface)
        zoom_tools.pack(in_=zoom_row, side='left', fill='x', expand=True)
        Label(zoom_tools, text="ZOOM HORIZONTAL −", bg=surface, fg=text, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.waveform_zoom_var = DoubleVar(value=0.0)
        self.waveform_zoom_status = StringVar(value="100%")
        self.waveform_zoom_slider = Canvas(zoom_tools, height=24, width=70, bg=surface, highlightthickness=0, cursor="hand2", takefocus=True)
        self.waveform_zoom_slider.bind("<Configure>", lambda _event:self._draw_zoom_slider())
        self.waveform_zoom_slider.bind("<Button-1>", self._zoom_slider_pointer)
        self.waveform_zoom_slider.bind("<B1-Motion>", self._zoom_slider_pointer)
        self.waveform_zoom_slider.bind("<Left>", lambda _event:self._set_waveform_zoom(self.waveform_zoom/1.1))
        self.waveform_zoom_slider.bind("<Right>", lambda _event:self._set_waveform_zoom(self.waveform_zoom*1.1))
        self.waveform_zoom_slider.bind("<Home>", lambda _event:self._set_waveform_zoom(1.0))
        self.waveform_zoom_slider.pack(side="left", fill="x", expand=True, padx=3)
        Label(zoom_tools, text="+", bg=surface, fg=text, font=("Segoe UI", 10, "bold")).pack(side="left")
        Label(zoom_tools, textvariable=self.waveform_zoom_status, bg=surface, fg=text, width=4, font=("Segoe UI", 7)).pack(side="left", padx=3)
        reset_zoom = Button(zoom_tools, text="100%", command=lambda:self._set_waveform_zoom(1.0), relief="flat", padx=7, pady=2)
        apply_button_style(reset_zoom, self.theme, "secondary")
        reset_zoom.pack(side="right")
        zoom_tools.layout_mode='inline'
        def reflow_zoom(_event=None):
            try:
                required=sum(w.winfo_reqwidth()+12 for w in (self.project_trash_button,self.trash_confirm_button,self.scene_memory_controls))+zoom_tools.winfo_reqwidth()+12
                mode='inline' if required<=zoom_row.winfo_width() else 'wrapped'
                if mode==zoom_tools.layout_mode:return
                zoom_tools.pack_forget()
                if mode=='inline':
                    zoom_extra.pack_forget()
                    zoom_tools.pack(in_=zoom_row,side='left',fill='x',expand=True)
                else:
                    zoom_extra.pack(fill='x',padx=10,pady=(0,4),after=zoom_row)
                    zoom_tools.pack(in_=zoom_extra,fill='x')
                zoom_tools.layout_mode=mode
            except tk.TclError:pass
        zoom_row.bind('<Configure>',reflow_zoom,add='+')
        edit_toolbar = Frame(self.waveform_panel, bg=surface)
        edit_toolbar.pack(fill="x", padx=10, pady=(0, 5))
        organize_row=Frame(self.waveform_panel,bg=surface)
        version_controls=Frame(self.waveform_panel,bg=surface)
        for attribute,label,latest in (('audio_restore_previous_button','RECUPERAR DUBLADO ANTERIOR',False),('audio_restore_latest_button','VOLTAR AO DUBLADO MAIS ATUAL',True)):
            outline=Frame(version_controls,bg='#DC2626',padx=2,pady=2)
            outline.pack(side='left',padx=3)
            button=Button(outline,text=label,command=lambda latest=latest:self._switch_dubbed_version(latest),relief='flat',font=('Segoe UI',7,'bold'),padx=5,pady=3)
            apply_button_style(button,self.theme,'success')
            button.pack()
            setattr(self,attribute,button)
        version_controls.pack(in_=edit_toolbar,side='left',padx=(0,12))
        version_controls.layout_mode='inline'
        def reflow_versions(_event=None):
            try:
                required=version_controls.winfo_reqwidth()+28
                for widget in edit_toolbar.pack_slaves():
                    if widget is version_controls or widget.pack_info()['side'] not in ('left','right'):continue
                    required+=widget.winfo_reqwidth()+20
                mode='inline' if required<=edit_toolbar.winfo_width() else 'wrapped'
                if mode==version_controls.layout_mode:return
                version_controls.pack_forget()
                if mode=='inline':
                    organize_row.pack_forget()
                    version_controls.pack(in_=edit_toolbar,side='left',padx=(0,12))
                else:
                    organize_row.pack(fill='x',padx=10,pady=(0,4),before=edit_toolbar)
                    version_controls.pack(in_=organize_row,side='left')
                version_controls.layout_mode=mode
            except Exception:pass
        edit_toolbar.bind('<Configure>',reflow_versions,add='+')
        self.waveform_widgets.append(edit_toolbar)
        self.audio_edit_status_var = StringVar(value=i18n.tr("Clique em EDITAR para selecionar trechos nas ondas."))
        edit_status = Label(edit_toolbar, textvariable=self.audio_edit_status_var, bg=surface, fg=self.theme.get("muted", "#64748B"), font=("Segoe UI", 7), anchor="w")
        edit_status.pack(side="top", fill="x", expand=True)
        self.waveform_widgets.append(edit_status)
        # O modo EDITAR/SAIR DO EDITAR fica separado das ações destrutivas e
        # de edição. As ações permanecem juntas, com SALVAR abrindo o grupo
        # um pouco mais à esquerda, conforme o layout da janela de referência.
        edit_mode_button = Button(edit_toolbar, text=i18n.tr("EDITAR"), command=self._toggle_audio_edit, relief="flat", font=("Segoe UI", 7, "bold"), padx=7, pady=6)
        apply_button_style(edit_mode_button, self.theme, "accent")
        edit_mode_button.pack(side="right", padx=(16, 0))
        self.audio_edit_button = edit_mode_button

        edit_actions = Frame(edit_toolbar, bg=surface)
        edit_actions.pack(side="right")
        edit_buttons = (
            ('audio_auto_align_button','ORGANIZAR ONDAS',lambda:self._process_scene_audio_edit(align_original=True),'success'),
            ("audio_undo_button", "DESFAZER", self._undo_audio_edit, "secondary"),
            ("audio_redo_button", "REFAZER", self._redo_audio_edit, "secondary"),
            ("audio_save_button", "SALVAR", self._save_audio_edit, "primary"),
            ("audio_paste_button", "COLAR", self._paste_audio_clip, "success"),
            ("audio_copy_button", "COPIAR", self._copy_audio_selection, "secondary"),
            ("audio_delete_button", "DELETE", self._delete_audio_selection, "danger"),
            ("audio_cut_button", "RECORTAR", self._cut_audio_selection, "danger"),
        )
        for attribute, label, command, role in edit_buttons:
            if attribute == "audio_duration_plus_button":
                duration_label = Label(edit_actions, text=i18n.tr("DURAÇÃO"), bg=surface, fg=text, font=("Segoe UI", 7, "bold"))
                duration_label.pack(side="left", padx=(1, 1))
                self.waveform_widgets.append(duration_label)
            button = Button(edit_actions, text=i18n.tr(label), command=command, relief="flat", font=("Segoe UI", 7, "bold"), padx=7, pady=2)
            apply_button_style(button, self.theme, role)
            # DESFAZER e REFAZER ficam juntos; o grupo recebe uma lacuna
            # maior antes de SALVAR, e SALVAR também fica afastado de COLAR.
            gap_after_button = 12 if attribute in {"audio_redo_button", "audio_save_button"} else 2
            if attribute == 'audio_auto_align_button':
                gap_after_button = 24
            if attribute in {"audio_trim_silence_button", "audio_duration_plus_button"}:
                gap_after_button = 24
            if attribute == "audio_duration_minus_button":
                gap_after_button = 0
            button.pack(side="left", padx=(0, gap_after_button))
            if attribute == 'audio_save_button':button.configure(pady=6)
            setattr(self, attribute, button)
        self._update_audio_edit_buttons()
        waveform_labels = (
            ("original", i18n.tr("ORIGINAL"), i18n.tr("▶  INICIAR ORIGINAL")),
            ("dubbed", i18n.tr("DUBLADO"), i18n.tr("▶  INICIAR DUBLADO")),
        )
        for kind, label, start_label in waveform_labels:
            if kind=='dubbed' and getattr(self,'original_reference_editor',False):
                label='RECORTE DO ORIGINAL — EDITÁVEL'
                start_label='▶ OUVIR RECORTE'
            row = Frame(self.waveform_panel, bg=surface)
            row.pack(fill="x", padx=10, pady=(0, 4))
            heading = Frame(row, bg=surface)
            heading.pack(fill="x")
            label_widget = Label(heading, text=f"{label}  —  {start_label}", bg=surface, fg=text, font=("Segoe UI", 8, "bold"), anchor="w")
            label_widget.pack(side="left")
            if kind == 'original' and self.audacity_ui is not None:
                self.audacity_ui.attach_heading(heading,row)
            duration_var = StringVar(value=i18n.tr("Duração: calculando..."))
            self.waveform_duration_vars[kind] = duration_var
            duration_label = Label(heading, textvariable=duration_var, bg=surface, fg=self.theme.get("muted", "#64748B"), font=("Segoe UI", 8), anchor="e")
            duration_label.pack(side="right")
            self.waveform_widgets.extend((row, heading, label_widget, duration_label))
            self.waveform_duration_labels[kind] = duration_label
            if kind == "dubbed":
                heading = Frame(row, bg=surface)
                heading.pack(fill='x', pady=(2, 2))
                self.waveform_widgets.append(heading)
                background_bar = Frame(row, bg=surface)
                background_bar.pack(fill='x', before=heading, pady=(2, 2))
                self.background_gain_var = DoubleVar(value=-18.0)
                Label(background_bar, text='FUNDO dB:', bg=surface, fg=text, font=('Segoe UI', 7, 'bold')).pack(side='left')
                ttk.Spinbox(background_bar, from_=-60, to=6, increment=1, width=5, textvariable=self.background_gain_var).pack(side='left', padx=3)
                Button(background_bar, text='COLOCAR COMO SOM DE FUNDO EM CIMA DO DUBLADO', command=self._open_background_editor, bg='#FDBA74', font=('Segoe UI', 7, 'bold'), relief='flat', pady=2).pack(side='left', padx=3)
                self.audio_split_button = Button(heading, text=i18n.tr("DIVIDIR (Ctrl+I)"), command=self._split_dubbed_clip, state="disabled", relief="flat", font=("Segoe UI", 7, "bold"), padx=8, pady=2)
                self.audio_split_button.configure(bg='#B5E61D', activebackground='#A2CF18', fg='#172033', disabledforeground='#52627A')
                self.audio_split_button.pack(side="left", padx=(0,24))
                for attribute,label,db in (("audio_volume_minus_button","− VOLUME",-1.0),("audio_volume_plus_button","VOLUME +",1.0)):
                    button=Button(heading,text=i18n.tr(label),command=lambda gain=db:self._process_scene_audio_edit(volume_db=gain),state="disabled",relief="flat",font=("Segoe UI",7,"bold"),padx=7,pady=2)
                    apply_button_style(button,self.theme,"success")
                    button.pack(side="left",padx=(0,3))
                    setattr(self,attribute,button)
                for attribute, label, command, role in (
                    ('audio_trim_silence_button', 'CORTAR SILÊNCIO INÍCIO/FIM', self._process_scene_audio_edit, 'white'),
                    ('audio_internal_silence_button', 'REMOVER SILÊNCIOS DO MEIO', lambda: self._process_scene_audio_edit(remove_internal_silence=True), 'warning'),
                    ('audio_duration_minus_button', '−', lambda:self._process_scene_audio_edit(.99), 'success'),
                    ('audio_duration_plus_button', '+', lambda:self._process_scene_audio_edit(1.01), 'success')):
                    if attribute == 'audio_duration_plus_button':
                        label_widget=Label(heading,text='DURAÇÃO',bg=surface,fg=text,font=('Segoe UI',7,'bold'))
                        label_widget.pack(side='left',padx=1)
                        self.waveform_widgets.append(label_widget)
                    button=Button(heading,text=label,command=command,relief='flat',font=('Segoe UI',7,'bold'),padx=7,pady=2)
                    apply_button_style(button,self.theme,role)
                    button.pack(side='left',padx=(4,0) if attribute != 'audio_duration_plus_button' else (0,0))
                    setattr(self,attribute,button)
                exact_bar=Frame(row,bg=surface)
                self.audio_exact_duration_button=Button(exact_bar,text='DURAÇÃO EXATA DO ORIGINAL',command=lambda:self._process_scene_audio_edit(exact_original=True),relief='flat',font=('Segoe UI',7,'bold'),padx=7,pady=2)
                apply_button_style(self.audio_exact_duration_button,self.theme,'success')
                self.audio_exact_duration_button.pack()
                exact_bar.pack(in_=heading,side='left',padx=5)
                exact_bar.layout_mode='inline'
                heading.bind('<Configure>',lambda event,bar=exact_bar,head=heading,row=row:self._reflow_audio_versions(bar,head,row),add='+')
                self._update_audio_edit_buttons()
                self.clip_drag = None
                self.clip_timeline_canvas = Canvas(row, height=28, highlightthickness=0, bg=self.theme.get("input", "#FFFFFF"), cursor="hand2", takefocus=True)
                self.clip_timeline_canvas.pack(fill="x", pady=(2, 0))
                self._bind_audio_zoom(self.clip_timeline_canvas)
                self.clip_timeline_canvas.bind("<Configure>", lambda _event: self._draw_clip_timeline())
                self.clip_timeline_canvas.bind("<Button-1>", self._clip_drag_press)
                self.clip_timeline_canvas.bind("<B1-Motion>", self._clip_drag_motion)
                self.clip_timeline_canvas.bind("<ButtonRelease-1>", self._clip_drag_release)
                self.clip_timeline_canvas.bind("<Delete>", self._delete_audio_selection)
                self.clip_timeline_canvas.bind("<BackSpace>", self._delete_audio_selection)
                self.clip_timeline_canvas.bind("<Control-c>", self._copy_audio_selection)
                self.clip_timeline_canvas.bind("<Control-x>", self._cut_audio_selection)
                self.clip_timeline_canvas.bind("<Control-v>", self._paste_audio_clip)
                self.clip_timeline_canvas.bind("<Control-z>", self._undo_audio_edit)
                self.clip_timeline_canvas.bind("<Control-y>", self._redo_audio_edit)
                self.clip_timeline_canvas.bind("<space>", self._toggle_edit_play_pause)
            if kind == 'original':
                from waveform_navigation import WaveformNavigation
                self.waveform_navigation=WaveformNavigation(self,row)
            canvas = Canvas(row, width=900, height=62, highlightthickness=0, bd=1, relief="solid", bg=self.theme.get("input", "#FFFFFF"))
            canvas.pack(fill="x", expand=True, pady=(2, 0))
            self.waveform_canvases[kind] = canvas
            self._bind_audio_zoom(canvas)
            canvas.bind("<Configure>", lambda _event, waveform_kind=kind: self._draw_waveform(waveform_kind))
            canvas.bind("<Button-1>", lambda event, waveform_kind=kind: self._on_waveform_press(waveform_kind, event))
            canvas.bind("<B1-Motion>", lambda event, waveform_kind=kind: self._on_waveform_motion(waveform_kind, event))
            canvas.bind("<ButtonRelease-1>", lambda event, waveform_kind=kind: self._on_waveform_release(waveform_kind, event))
            canvas.bind("<Control-i>", self._split_dubbed_clip)
            canvas.bind("<Control-I>", self._split_dubbed_clip)
            canvas.bind("<Control-c>", self._copy_audio_selection)
            canvas.bind("<Control-x>", self._cut_audio_selection)
            canvas.bind("<Control-v>", self._paste_audio_clip)
            canvas.bind("<Control-z>", self._undo_audio_edit)
            canvas.bind("<Control-y>", self._redo_audio_edit)
            canvas.bind("<Delete>", self._delete_audio_selection)
            canvas.bind("<BackSpace>", self._delete_audio_selection)
            canvas.bind("<space>", self._toggle_edit_play_pause)
            canvas.configure(cursor="hand2", takefocus=True)
        self.waveform_scrollbar = Scrollbar(self.waveform_panel, orient="horizontal", command=self._scroll_audio_views)
        self.waveform_scrollbar.pack(fill="x", padx=10, pady=(0, 5))
        self.waveform_canvases["original"].configure(xscrollcommand=self.waveform_scrollbar.set)
        if self.audacity_ui is not None:self.audacity_ui.attach_tracks(self.waveform_panel)
        from waveform_navigation import bind_wheel
        bind_wheel(self,self.waveform_panel)
        if self.waveform_vertical_view is not None:bind_wheel(self,self.waveform_vertical_view)
        text_panel = Frame(content, bg=surface, bd=1, relief="solid", height=190)
        # Em uma janela maximizada, o painel de texto absorve o espaço livre
        # entre as ondas e os controles inferiores; assim não sobra um vazio
        # central e o rodapé permanece acima da barra de tarefas.
        text_panel.pack(side="top", fill="both", expand=True, padx=14, pady=(0, 8))
        text_panel.pack_propagate(False)
        factory=getattr(self,'scene_editor_factory',None)
        if callable(factory):factory(text_panel)
        else:
            text_header = Frame(text_panel, bg=surface)
            text_header.pack(fill="x", padx=10, pady=(8, 2))
            Label(text_header, text=i18n.tr("TEXTO EM PORTUGUÊS — EDITÁVEL"), bg=surface, fg=text, font=("Segoe UI", 9, "bold"), anchor="w").pack(side="left")
            self.scene_text_title_var = StringVar(value="")
            Label(text_header, textvariable=self.scene_text_title_var, bg=surface, fg=text, font=("Segoe UI", 9), anchor="e").pack(side="right", fill="x", expand=True, padx=(12, 0))
            controller=getattr(self,'translation_controller',None)
            if controller is not None:
                translation_row=Frame(text_panel,bg=surface)
                translation_row.pack(fill='x',padx=10,pady=(3,3))
                ttk.Checkbutton(translation_row,text=i18n.tr('Usar no redublar'),variable=controller.use_other_translation_var,onvalue='1',offvalue='0',command=self._toggle_scene_translation).pack(side='right',anchor='n',padx=(8,0))
                text_switches=Frame(translation_row,bg=surface)
                text_switches.pack(side='left',anchor='n',padx=(0,8))
                for label, command in [('MOSTRAR TEXTO DA TRADUÇÃO PRINCIPAL',self._show_main_scene_translation),('MOSTRAR TEXTO ORIGINAL',self._show_original_scene_text)]:
                    button=Button(text_switches,text=i18n.tr(label),command=command,relief='flat',font=('Segoe UI',8,'bold'),padx=7,pady=1)
                    apply_button_style(button,self.theme,'primary')
                    button.pack(fill='x',pady=(0,1))
                try:
                    from .ui_theme import horizontal_folder_strip
                except ImportError:
                    from ui_theme import horizontal_folder_strip
                folder_strip, self.scene_translation_folders_bar=horizontal_folder_strip(translation_row,self.theme)
                folder_strip.pack(side='left',fill='x',expand=True,anchor='n')
                self._refresh_scene_translation_folders()
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
        controls = Frame(content, bg=surface, height=78)
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
        if getattr(self,'is_part_window',False):
            self.start_button.configure(text='▶ INICIAR PARTE DO RECORTE' if getattr(self, 'original_reference_editor', False) else '▶ INICIAR PARTE DO DUBLADO')
            if getattr(self, 'original_reference_editor', False):
                apply_button_style(self.start_button, self.theme, 'highlight')
        if self.audacity_ui is not None:self.audacity_ui.attach_playback(controls)
        self.stop_button = Button(controls, text=i18n.tr("PARAR"), command=self.stop, relief="flat", padx=12, pady=5)
        apply_button_style(self.stop_button, self.theme, "danger")
        self.stop_button.pack(side="left", padx=3)
        if callable(self.review_snapshot_provider):
            self._build_review_progress_controls(controls, surface, text)
        elif self.audacity_ui is not None:
            self.audacity_ui.attach_progress(controls)
        audio_controls = Frame(content, bg=surface, height=48)
        audio_controls.pack(side="bottom", fill="x", padx=10, pady=(0, 5))
        audio_controls.pack_propagate(False)
        audio_definitions = (
            ("open_dubbed", "ABRIR LOCAL DO ÁUDIO DUBLADO"),
            ("open_original", "ABRIR LOCAL DO ÁUDIO ORIGINAL"),
            ("copy_name", "COPIAR NOME DO ÁUDIO"),
            ("copy_dubbed", "COPIAR LOCAL DO ÁUDIO DUBLADO"),
            ("copy_original", "COPIAR LOCAL DO ÁUDIO ORIGINAL"),
            *((('copy_part_all','COPIAR PARTE INTEIRA'),) if getattr(self,'is_part_window',False) else ()),
        )
        for column in range(3):
            audio_controls.grid_columnconfigure(column, weight=1, uniform="audio_action")
        for index, (action_name, label) in enumerate(audio_definitions):
            row, column = divmod(index, 3)
            container = audio_controls
            if action_name == 'dub_part':
                container = Frame(audio_controls, bg=surface)
                container.grid(row=row,column=column,sticky='nsew',padx=2,pady=2)
            button = Button(
                container,
                text=i18n.tr(label),
                command=lambda name=action_name: self._audio_context_action(name),
                relief="flat",
                font=("Segoe UI", 8, "bold"),
                padx=8,
                pady=0,
                wraplength=280,
                justify="center",
            )
            role = "success" if action_name in {"dub_part", "copy_part_all"} else "neutral"
            apply_button_style(button, self.theme, role)
            if action_name == 'dub_part':
                button.pack(side='left',fill='both',expand=True,padx=1)
                button.configure(text='DUBLAR PARTE\nDO TXT',wraplength=150)
                original_button=Button(container,text='DUBLAR PARTE DO\nÁUDIO ORIGINAL',command=lambda:self._audio_context_action('dub_original_part'),font=('Segoe UI',8,'bold'),relief='flat',bg='#A78BFA',fg='#111827',activebackground='#C4B5FD')
                original_button.pack(side='left',fill='both',expand=True,padx=1)
            else:
                button.grid(row=row, column=column, sticky="nsew", padx=2, pady=2)
            self.audio_action_buttons.append((button, role))
        audio_controls.grid_rowconfigure(0, weight=1)
        audio_controls.grid_rowconfigure(1, weight=1)
        if self.review_actions:
            review_controls = Frame(content, bg=surface)
            review_controls.pack(side="bottom", fill="x", padx=10, pady=(0, 5))
            self.review_preferences_frame = Frame(review_controls, bg=surface)
            self.review_controls_buttons = Frame(review_controls, bg=surface, height=42)
            self.review_controls_buttons.pack_propagate(False)
            self.review_controls_buttons.pack(side="bottom", fill="x")
            definitions = (
                ("open_audacity", "Abrir ORIGINAL + DUBLAGEM no Audacity", "warning"),
                ("approve", "Aprovar", "primary"),
                ("reject", "Rejeitar", "danger"),
                ("redub", "REDUBLAR", "success"),
                ("redub_personalized", "REDUBLAR ÁUDIO PERSONALIZADO", "success"),
                ("redub_other", "REDUBLAR COM OUTRO ÁUDIO", "accent"),
            )
            for action_name, label, role in definitions:
                if getattr(self,'original_reference_editor',False) and action_name == 'redub':
                    label='SALVAR E DUBLAR RECORTE'
                    role='highlight'
                callback = self.review_actions.get(action_name)
                if not callable(callback):
                    continue
                button = Button(self.review_controls_buttons, text=i18n.tr(label), command=lambda name=action_name: self._invoke_review_action(name), relief="flat", font=("Segoe UI", 8, "bold"), padx=6, pady=4, wraplength=150)
                apply_button_style(button, self.theme, role)
                button.pack(side="left", fill="both", expand=True, padx=2)
                self.review_action_buttons.append((button, role))
            self._refresh_review_preferences()
        if not getattr(self,'is_part_window',False):
            parts_bar=self.review_controls_buttons if self.review_actions else Frame(content,bg=surface,height=48)
            if not self.review_actions:
                parts_bar.pack(side='bottom',fill='x',padx=10,pady=(0,4))
                parts_bar.pack_propagate(False)
            self.part_action_buttons=[]
            for label,action,role in [('DUBLAR PARTE\nDO TXT','dub_part','success'),('DUBLAR PARTE DO\nÁUDIO ORIGINAL','dub_original_part','accent')]:
                border=Frame(parts_bar,bg='#FACC15',padx=2,pady=2)
                border.pack(side='left',fill='both',expand=True,padx=2)
                button=Button(border,text=label,command=lambda a=action:self._audio_context_action(a),relief='flat',font=('Segoe UI',7,'bold'),wraplength=100,padx=3,pady=1)
                apply_button_style(button,self.theme,role)
                button.pack(fill='both',expand=True)
                self.part_action_buttons.append(button)
                self.audio_action_buttons.append((button,role))
            for button,role in self.review_action_buttons:button.configure(font=('Segoe UI',7,'bold'),wraplength=90,pady=2)
            def fit_action_height(_event=None):
                try:
                    height=max([b.winfo_reqheight() for b,_ in self.review_action_buttons]+[b.winfo_reqheight()+4 for b in self.part_action_buttons])+2
                    parts_bar.configure(height=max(42,height))
                except tk.TclError:pass
            parts_bar.bind('<Configure>',fit_action_height,add='+')
        self.close_button = Button(controls, text=i18n.tr("X  FECHAR"), command=self.close_window, relief="flat", padx=12, pady=5)
        apply_button_style(self.close_button, self.theme, "secondary")
        self.close_button.pack(side="right", padx=0)
        self._update_original_button()
        self._update_navigation_buttons()
        try:
            window.update_idletasks()
            requested_height = max(560, int(window.winfo_reqheight()))
            fitted_height = min(requested_height, available_height)
            window.geometry(opening_geometry)
            window.update_idletasks()
            if self.audacity_ui is not None:
                fit_wave_area()
                window.update_idletasks()
        except Exception:
            pass
        return window

    def apply_theme(self, theme: dict):
        self._base_theme = {**getattr(self, "_base_theme", self.theme), **theme}
        self.theme = dict(self._base_theme)
        if self.dubbed_folder_name == "dublados personalizados":
            self.theme.update(mode="escuro", surface="#450F18", root="#450F18",
                              text="#FFF1F2", input="#2B0A10", input_text="#FFF1F2",
                              muted="#F3B8C2", border="#883344", select="#8C263B")
        if self.window is None:
            return
        try:
            if self.window.winfo_exists():
                surface = self.theme.get("surface", "#FFFFFF")
                text = self.theme.get("text", "#1F2937")
                def recolor_frames(widget):
                    for child in widget.winfo_children():
                        try:
                            if hasattr(child, 'apply_folder_theme'):
                                child.apply_folder_theme(self.theme)
                            if child.winfo_class() in {"Frame", "Label"}:
                                child.configure(bg=surface)
                                if child.winfo_class() == "Label":
                                    child.configure(fg=text)
                            recolor_frames(child)
                        except Exception:
                            pass
                recolor_frames(self.window)
                border_color = self.window_border_color
                self.window.configure(bg=border_color)
                try:
                    self.window.configure(highlightthickness=2, highlightbackground=border_color, highlightcolor=border_color)
                except Exception:
                    pass
                if self.window_content is not None:
                    self.window_content.configure(bg=surface)
                if self.window_body is not None:
                    self.window_body.configure(bg=surface, fg=text)
                if self.scene_text_box is not None:
                    self.scene_text_box.configure(bg=self.theme.get("input", surface), fg=self.theme.get("input_text", text), insertbackground=self.theme.get("input_text", text))
                if self.scene_text_status_var is not None:
                    self.scene_text_status_var.set(self.scene_text_status_var.get())
                input_bg = self.theme.get("input", surface)
                input_fg = self.theme.get("input_text", text)
                muted = self.theme.get("muted", "#64748B")
                border = self.theme.get("border", "#CBD5E1")
                if self.waveform_split is not None:
                    self.waveform_split.configure(bg=border)
                for review_top_widget in (self.review_top_row, self.review_top_spacer, self.review_top_panel):
                    if review_top_widget is not None:
                        try:
                            review_top_widget.configure(bg=surface)
                        except Exception:
                            pass
                if self.review_panel is not None:
                    def recolor_review(widget):
                        try:
                            widget_class = widget.winfo_class()
                            if widget_class in {"Frame", "Label"}:
                                widget.configure(bg=surface)
                                if widget_class == "Label":
                                    widget.configure(fg=text)
                            elif widget_class == "Text":
                                widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg)
                        except Exception:
                            pass
                        try:
                            for child in widget.winfo_children():
                                recolor_review(child)
                        except Exception:
                            pass
                    recolor_review(self.review_panel)
                    style = ttk.Style(self.window)
                    clone_color = "#60A5FA" if self.theme.get("mode") != "claro" else "#2563EB"
                    dub_color = "#A78BFA" if self.theme.get("mode") != "claro" else "#7C3AED"
                    style.configure("AudioReviewClone.Horizontal.TProgressbar", troughcolor=border, background=clone_color, lightcolor=clone_color, darkcolor=clone_color)
                    style.configure("AudioReviewDub.Horizontal.TProgressbar", troughcolor=border, background=dub_color, lightcolor=dub_color, darkcolor=dub_color)
                if self.review_progress_frame is not None:
                    for widget in self.review_progress_widgets:
                        try:
                            if widget.winfo_class() == "Label":
                                widget.configure(bg=surface, fg=self.theme.get("muted", text))
                            else:
                                widget.configure(bg=surface)
                        except Exception:
                            pass
                    style = ttk.Style(self.window)
                    clone_color = button_style(self.theme, "primary")["bg"] if button_style is not None else "#2563EB"
                    dub_color = button_style(self.theme, "success")["bg"] if button_style is not None else "#15803D"
                    style.configure("AudioReviewClone.Horizontal.TProgressbar", troughcolor=border, background=clone_color, lightcolor=clone_color, darkcolor=clone_color)
                    style.configure("AudioReviewDub.Horizontal.TProgressbar", troughcolor=border, background=dub_color, lightcolor=dub_color, darkcolor=dub_color)
                for widget in self.waveform_widgets:
                    try:
                        widget.configure(bg=surface)
                    except Exception:
                        pass
                for kind, canvas in self.waveform_canvases.items():
                    try:
                        canvas.configure(bg=input_bg, highlightbackground=border, highlightcolor=border)
                    except Exception:
                        pass
                    self._draw_waveform(kind)
                for label in self.waveform_duration_labels.values():
                    try:
                        label.configure(bg=surface, fg=muted)
                    except Exception:
                        pass
                for container in (self.review_preferences_frame, self.review_controls_buttons):
                    if container is not None:
                        container.configure(bg=surface)
                for widget, role in (
                    (self.previous_button, "secondary"),
                    (self.next_button, "secondary"),
                    (self.start_button, "highlight" if getattr(self, "original_reference_editor", False) else "success"),
                    (self.original_button, "accent"),
                    (self.stop_button, "danger"),
                    (self.close_button, "secondary"),
                    (self.scene_text_save_button, "primary"),
                    (getattr(self, "audio_trim_silence_button", None), "white"),
                    (getattr(self, "audio_volume_minus_button", None), "success"),
                    (getattr(self, "audio_volume_plus_button", None), "success"),
                    (getattr(self, "audio_duration_minus_button", None), "success"),
                    (getattr(self, "audio_duration_plus_button", None), "success"),
                    (self.audio_undo_button, "secondary"),
                    (self.audio_redo_button, "secondary"),
                    (self.audio_save_button, "primary"),
                    (self.audio_paste_button, "success"),
                    (self.audio_copy_button, "secondary"),
                    (self.audio_delete_button, "danger"),
                    (self.audio_cut_button, "danger"),
                    *self.review_action_buttons,
                    *self.audio_action_buttons,
                ):
                    if widget is not None:
                        apply_button_style(widget, self.theme, role)
                slider = getattr(self, "waveform_zoom_slider", None)
                if slider is not None:
                    slider.configure(bg=surface)
                    self._draw_zoom_slider()
                self._draw_clip_timeline()
                if hasattr(self, "scene_parts_ui"):
                    self.scene_parts_ui.refresh(force=True)
        except Exception:
            pass

    def _current_audio_path(self, kind: str | None = None) -> Path | None:
        if kind in {'instrumental','vocals','suppression'}:
            return getattr(getattr(self,'audacity_ui',None),'paths',{}).get(kind)
        index = self.current_index
        if index < 0 or index >= len(self.navigation_paths):
            return None
        if kind == "original" and index < len(self.original_navigation_paths):
            path = self.original_navigation_paths[index]
            return Path(path) if path is not None and Path(path).is_file() else None
        if kind == "dubbed" and index < len(self.dubbed_navigation_paths):
            path = self.dubbed_navigation_paths[index]
            return Path(path) if path is not None and Path(path).is_file() else None
        path = self.navigation_paths[index]
        return Path(path) if Path(path).is_file() else None

    def _copy_audio_context_value(self, value: str, message: str) -> None:
        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(value)
            self.parent.update()
            self.emit_status(message)
        except Exception as exc:
            self.emit_status(f"Não foi possível copiar: {exc}")

    def _audio_context_action(self, action: str) -> None:
        if action == 'dub_original_part':
            self.scene_parts_ui.composer_original()
            return
        if action == "dub_part":
            self.scene_parts_ui.composer()
            return
        if action == "copy_part_all":
            self._copy_whole_part()
            return
        if action in {"open_dubbed", "copy_dubbed"}:
            path = self._current_audio_path("dubbed")
            label = "dublado"
        elif action in {"open_original", "copy_original"}:
            path = self._current_audio_path("original")
            label = "original"
        else:
            path = self._current_audio_path() or self._current_audio_path("dubbed") or self._current_audio_path("original")
            label = "áudio"
        if path is None:
            self.emit_status(f"Áudio {label} não encontrado para a cena atual.")
            return
        if action.startswith("open_"):
            if reveal_in_file_manager(path):
                self.emit_status(f"Pasta do áudio {label} aberta: {path.parent}")
            else:
                self.emit_status(f"Não foi possível abrir a pasta do áudio {label}: {path.parent}")
        elif action == "copy_name":
            self._copy_audio_context_value(path.name, f"Nome copiado: {path.name}")
        else:
            self._copy_audio_context_value(str(path.parent), f"Local da pasta {label} copiado: {path.parent}")

    def _update_mode_buttons(self):
        available_original = [path for path in self.original_pending_paths if path is not None and Path(path).is_file()]
        available_dubbed = [path for path in self.dubbed_pending_paths if path is not None and Path(path).is_file()]
        for button, available in ((self.original_button, available_original), (self.start_button, available_dubbed)):
            if button is not None:
                try:
                    button.configure(state="normal" if available else "disabled")
                except Exception:
                    pass

    def _update_original_button(self):
        # Compatibilidade para chamadas antigas que atualizavam apenas o botão original.
        self._update_mode_buttons()

    def _project_audio_index_for(self, folder_name: str, folder: Path) -> dict[str, list[Path]]:
        cache_key = f"{os.path.normcase(str(self.project_root))}:{folder_name.casefold()}"
        cached = self._project_audio_index.get(cache_key)
        if cached is not None:
            return cached
        index: dict[str, list[Path]] = {}
        try:
            candidates = folder.rglob("*")
        except (OSError, PermissionError):
            candidates = ()
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.casefold() not in {".wav", ".wave", ".waw"}:
                continue
            parts = {part.casefold() for part in candidate.parts}
            if "_backup_omnivoice" in parts or candidate.parent.name.casefold() in {"mp3", "ogg", "flac", "m4a", "aac", "aiff", "aif", "wma", "opus"}:
                continue
            index.setdefault(candidate.stem.casefold(), []).append(candidate.resolve())
        self._project_audio_index[cache_key] = index
        return index

    def _find_project_audio_by_stem(self, folder_name: str, path: Path) -> Path | None:
        if self.project_root is None:
            return None
        folder = (self.project_root / folder_name).expanduser().resolve()
        if not folder.is_dir():
            return None
        path = Path(path).expanduser().resolve()
        wav_extensions = {".wav", ".wave", ".waw"}
        # Primeiro tenta a mesma hierarquia relativa. Não faz busca global quando
        # a origem já pertence ao projeto: isso evita uma varredura de milhares de
        # arquivos para cada cena sem dublado correspondente.
        relative_checked = False
        for source_folder_name in ("dublado", "WAV ORIGINAIS", "dublados personalizados"):
            source_folder = (self.project_root / source_folder_name).expanduser().resolve()
            try:
                relative = path.relative_to(source_folder)
            except ValueError:
                continue
            relative_checked = True
            candidate = folder / relative.with_suffix(".wav")
            if candidate.is_file() and candidate.suffix.casefold() in wav_extensions:
                return candidate.resolve()
            candidate = folder / relative
            if candidate.is_file() and candidate.suffix.casefold() in wav_extensions:
                return candidate.resolve()
        if relative_checked:
            return None
        direct = folder / path.name
        if direct.is_file() and direct.suffix.casefold() in wav_extensions:
            return direct.resolve()
        matches = self._project_audio_index_for(folder_name, folder).get(path.stem.casefold(), [])
        return matches[0] if len(matches) == 1 else None

    def set_loaded_audio_pairs(self, pairs):
        """Fixa os pares fornecidos pela aba, sem substituí-los por arquivos do projeto."""
        self.loaded_audio_pairs = {Path(path).resolve(): pair for path, pair in pairs.items()}
        self._resolved_pair_indices.clear()
        custom_root = (self.project_root / "dublados personalizados").resolve() if self.project_root is not None else None
        has_personalized = custom_root is not None and any(
            dubbed is not None and Path(dubbed).resolve().is_relative_to(custom_root)
            for _original, dubbed in self.loaded_audio_pairs.values()
        )
        self.set_dubbed_folder_name("dublados personalizados" if has_personalized else "dublado")

    def _find_original_audio(self, path: Path) -> Path | None:
        """Localiza o WAV de mesmo nome na pasta WAV ORIGINAIS do projeto."""
        drawer=getattr(self,'review_drawer',None)
        if drawer is not None:
            pair=drawer.resolve_pair(path)
            if pair is not None:return pair[0]
        if getattr(self, "loaded_audio_pairs", None) is not None:
            return self.loaded_audio_pairs.get(Path(path).resolve(), (None, None))[0]
        return self._find_project_audio_by_stem("WAV ORIGINAIS", path)

    def _find_dubbed_audio(self, path: Path) -> Path | None:
        drawer=getattr(self,'review_drawer',None)
        if drawer is not None:
            pair=drawer.resolve_pair(path)
            if pair is not None:return pair[1]
        if getattr(self, "loaded_audio_pairs", None) is not None:
            return self.loaded_audio_pairs.get(Path(path).resolve(), (None, None))[1]
        return self._find_project_audio_by_stem(self.dubbed_folder_name, path)

    def _originals_for_navigation(self):
        return [self._find_original_audio(path) for path in self.navigation_paths]

    def _dubbed_for_navigation(self):
        return [self._find_dubbed_audio(path) for path in self.navigation_paths]

    def _resolve_navigation_pair(self, index: int) -> None:
        if index < 0 or index >= len(self.navigation_paths) or index in self._resolved_pair_indices:
            return
        path = self.navigation_paths[index]
        self.original_navigation_paths[index] = self._find_original_audio(path)
        self.dubbed_navigation_paths[index] = self._find_dubbed_audio(path)
        self._resolved_pair_indices.add(index)

    def _set_current_mode_paths(self, index: int, path: Path | None = None):
        if path is None:
            path = self.navigation_paths[index]
        original = self.original_navigation_paths[index] if index < len(self.original_navigation_paths) else None
        dubbed = self.dubbed_navigation_paths[index] if index < len(self.dubbed_navigation_paths) else None
        self.original_pending_paths = [original] if original is not None else []
        self.dubbed_pending_paths = [dubbed] if dubbed is not None else []
        if not self.original_pending_paths and not self.dubbed_pending_paths:
            self.dubbed_pending_paths = [path]
            self.current_source_kind = "unknown"
        elif path.resolve() == (original.resolve() if original is not None else None):
            self.current_source_kind = "original"
        elif path.resolve() == (dubbed.resolve() if dubbed is not None else None):
            self.current_source_kind = "dubbed"
        else:
            self.current_source_kind = "unknown"
        self.pending_paths = [path]
        self._update_mode_buttons()

    def _update_navigation_buttons(self):
        if self.previous_button is not None:
            try:
                self.previous_button.configure(state="normal" if self.current_index > 0 else "disabled")
            except Exception:
                pass
        if self.next_button is not None:
            try:
                self.next_button.configure(state="normal" if 0 <= self.current_index < len(self.navigation_paths) - 1 else "disabled")
            except Exception:
                pass

    def navigate(self, offset: int):
        if not self.navigation_paths:
            return
        target_index = self.current_index + offset
        if target_index < 0 or target_index >= len(self.navigation_paths):
            return
        if not self._prepare_audio_edit_scene_change():
            return
        path = self.navigation_paths[target_index]
        if not path.is_file():
            # Playlists grandes podem conter os caminhos esperados de dublado sem
            # consultar 3000 arquivos na abertura. Só neste avanço resolvemos o
            # original correspondente como fallback.
            fallback = self._find_original_audio(path) or self._find_dubbed_audio(path)
            if fallback is None:
                self.emit_status(f"Arquivo de áudio não encontrado: {path}")
                return
            path = fallback
            self.navigation_paths[target_index] = path
        self.stop(announce=False)
        self.current_index = target_index
        self.current_context_key = self.navigation_context_keys[target_index] if target_index < len(self.navigation_context_keys) else None
        self._resolved_pair_indices.discard(target_index)
        self._resolve_navigation_pair(target_index)
        self._set_current_mode_paths(target_index, path)
        self.stop_event.clear()
        self._update_navigation_buttons()
        if self.window_status is not None:
            original = self.original_pending_paths[0] if self.original_pending_paths else None
            dubbed = self.dubbed_pending_paths[0] if self.dubbed_pending_paths else None
            self.window_status.set(i18n.tr(self._scene_status_text(target_index + 1, len(self.navigation_paths), path, original, dubbed)))
        self._refresh_scene_text()
        self._refresh_waveforms()
        self.emit_status(f"Áudio carregado: {path.name}")
        self._notify_scene_selection()

    def play_one(self, path: Path, title: str = "OUVIR ÁUDIO", playlist: list[Path] | None = None, index: int | None = None, scene_key: str | None = None, scene_keys: list[str] | None = None, force_editor: bool = False):
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            self.emit_status(f"Arquivo de áudio não encontrado: {path}")
            return
        if self.playback_mode == "windows" and not force_editor:
            self._start_paths([path], "original" if "WAV ORIGINAIS" in path.parts else "dubbed")
            return
        if self.playback_mode == "windows":
            # O modo Windows não precisa da janela de controles do FFplay:
            # entrega o arquivo diretamente ao aplicativo padrão do sistema.
            self._destroy_window(clear_pending=True)
        else:
            self.stop(announce=False)
        candidates = playlist if playlist is not None else [path]
        # O item selecionado já foi validado; os demais caminhos da playlist são
        # mantidos sem is_file/rglob para abrir a janela imediatamente. A validade
        # dos itens seguintes é conferida somente quando o usuário navega até eles.
        self.navigation_paths = [Path(os.path.abspath(os.path.expanduser(str(item)))) for item in candidates]
        if scene_keys is not None:
            self.navigation_context_keys = [str(key) for key in scene_keys]
        else:
            self.navigation_context_keys = [None] * len(self.navigation_paths)
        if scene_key is not None and 0 <= (int(index) if index is not None else 0) < len(self.navigation_context_keys):
            self.navigation_context_keys[int(index) if index is not None else 0] = str(scene_key)
        if not self.navigation_paths:
            self.navigation_paths = [path]
        if index is not None and 0 <= int(index) < len(self.navigation_paths):
            self.current_index = int(index)
            # O chamador pode fornecer o caminho real somente para o item atual,
            # enquanto os itens vizinhos ficam como caminhos esperados e são
            # resolvidos sob demanda ao usar ANTERIOR/PRÓXIMO.
            self.navigation_paths[self.current_index] = path
        elif path in self.navigation_paths:
            self.current_index = self.navigation_paths.index(path)
        else:
            self.navigation_paths.insert(0, path)
            self.current_index = 0
        path = self.navigation_paths[self.current_index]
        if len(self.navigation_context_keys) < len(self.navigation_paths):
            self.navigation_context_keys.extend([None] * (len(self.navigation_paths) - len(self.navigation_context_keys)))
        self.current_context_key = self.navigation_context_keys[self.current_index] if self.current_index < len(self.navigation_context_keys) else None
        self.original_navigation_paths = [None] * len(self.navigation_paths)
        self.dubbed_navigation_paths = [None] * len(self.navigation_paths)
        self._resolved_pair_indices.clear()
        self._resolve_navigation_pair(self.current_index)
        self._set_current_mode_paths(self.current_index, path)
        self.pending_title = title
        self.stop_event.clear()
        original = self.original_pending_paths[0] if self.original_pending_paths else None
        dubbed = self.dubbed_pending_paths[0] if self.dubbed_pending_paths else None
        # A janela é somente o painel de escolha/navegação; no modo Windows ela
        # não inicia FFplay. Os botões ORIGINAL/DUBLADO chamam o player escolhido
        # quando pressionados, mantendo o áudio original acessível.
        self.show_window(title, self._scene_status_text(self.current_index + 1, len(self.navigation_paths), path, original, dubbed))
        self._notify_scene_selection()

    def play_all(self, paths: list[Path], title: str = "OUVIR TODOS", scene_keys: list[str] | None = None):
        valid_paths = [Path(path).expanduser().resolve() for path in paths if Path(path).expanduser().is_file()]
        if not valid_paths:
            self.emit_status("Nenhum áudio disponível para reprodução")
            return
        if self.playback_mode == "windows":
            self._start_paths(valid_paths,"dubbed");return
        self.stop(announce=False)
        self.navigation_paths = valid_paths
        self.navigation_context_keys = [str(key) for key in scene_keys] if scene_keys is not None else [None] * len(valid_paths)
        # OUVIR TODOS é uma ação explícita de sequência; aqui mantemos o
        # pareamento completo para que ORIGINAL/DUBLADO reproduzam toda a fila.
        self.original_navigation_paths = self._originals_for_navigation()
        self.dubbed_navigation_paths = self._dubbed_for_navigation()
        self._resolved_pair_indices = set(range(len(valid_paths)))
        self.current_index = 0
        self.current_context_key = self.navigation_context_keys[0] if self.navigation_context_keys else None
        self.pending_paths = valid_paths
        self.original_pending_paths = [path for path in self.original_navigation_paths if path is not None]
        dubbed_paths = [path for path in self.dubbed_navigation_paths if path is not None]
        self.dubbed_pending_paths = dubbed_paths if dubbed_paths else list(valid_paths) if not self.original_pending_paths else []
        self.current_source_kind = "original" if self.original_pending_paths and not self.dubbed_pending_paths else "dubbed"
        self.pending_title = title
        self.stop_event.clear()
        first_path = valid_paths[0]
        first_original = self.original_navigation_paths[0] if self.original_navigation_paths and self.original_navigation_paths[0] is not None else None
        first_dubbed = self.dubbed_navigation_paths[0] if self.dubbed_navigation_paths and self.dubbed_navigation_paths[0] is not None else None
        self.show_window(title, f"{len(valid_paths)} áudio(s) carregado(s).\n\n{self._scene_status_text(1, len(valid_paths), first_path, first_original, first_dubbed)}")
        self._notify_scene_selection()

    def _start_paths(self, paths: list[Path], kind: str, start_seconds: float = 0.0):
        kind = {"dublada": "dubbed", "dublado": "dubbed"}.get(kind, kind)
        if start_seconds == 0 and kind in self.waveform_canvases:
            self._scroll_audio_views("moveto", 0.0)
        # Copia e valida novamente a fila no momento do clique, sem depender do texto da janela.
        valid_paths = [Path(path).expanduser().resolve() for path in paths if Path(path).expanduser().is_file()]
        if not valid_paths:
            self.emit_status("Nenhum áudio disponível para reprodução. Use OUVIR CENA ou dê duplo clique em um item da lista.")
            return
        if self.playback_mode == "windows":
            if not sys.platform.startswith("win"):
                self.emit_status("O player do Windows só está disponível no Windows; selecione FFplay.")
                return
            path = valid_paths[0]
            try:
                os.startfile(str(path))  # type: ignore[attr-defined]
                message = f"Áudio aberto no player do Windows: {path.name}"
                if len(valid_paths) > 1:
                    message += " — para ouvir uma sequência, selecione FFplay."
                self.emit_status(message)
            except OSError as exc:
                self.emit_status(f"Não foi possível abrir {path.name} no player do Windows: {exc}")
            self._update_original_button()
            return
        self.stop_event.clear()
        for button in (self.start_button, self.original_button):
            if button is not None:
                try:
                    button.configure(state="disabled")
                except Exception:
                    pass
        self.emit_status(f"Iniciando reprodução {kind} de {len(valid_paths)} áudio(s)...")
        self.playback_id += 1
        playback_id = self.playback_id
        self.thread = threading.Thread(target=self._play_thread, args=(valid_paths, playback_id, kind, max(0.0, float(start_seconds or 0.0))), daemon=True)
        self.thread.start()

    def start_pending(self):
        self.audio_paused_kind = None
        self.audio_paused_path = None
        self.audio_paused_seconds = 0.0
        if self.audio_edit_mode and self.audio_edit_working.get("dubbed") is not None:
            self._play_edit_preview("dubbed", self._edit_selection_start("dubbed"))
            return
        paths = self.dubbed_pending_paths or self.pending_paths
        self._start_paths(paths, "dubbed")

    def start_original_pending(self):
        self.audio_paused_kind = None
        self.audio_paused_path = None
        self.audio_paused_seconds = 0.0
        if self.audio_edit_mode and self.audio_edit_working.get("original") is not None:
            self._play_edit_preview("original", self._edit_selection_start("original"))
            return
        self._start_paths(self.original_pending_paths, "original")

    def _play_thread(self, paths: list[Path], playback_id: int, waveform_kind: str, start_seconds: float = 0.0):
        mode = self.playback_mode
        ffplay = None if mode == "windows" else (self._ffplay_path or find_ffplay(self.project_root))
        if ffplay:
            self._ffplay_path = ffplay
        for index, path in enumerate(paths, start=1):
            if self.stop_event.is_set() or playback_id != self.playback_id:
                return
            self.emit_status(f"Reproduzindo {index}/{len(paths)}: {path.name}")
            try:
                if mode == "windows":
                    if not sys.platform.startswith("win"):
                        self.emit_status("O player do Windows só está disponível no Windows; selecione FFplay.")
                        return
                    # O modo Windows delega todos os formatos ao aplicativo
                    # padrão associado ao arquivo (Media Player, VLC ou outro).
                    os.startfile(str(path))  # type: ignore[attr-defined]
                    message = f"Áudio aberto no player do Windows: {path.name}"
                    if len(paths) > 1:
                        message += " — para ouvir uma sequência, selecione FFplay."
                    self.emit_status(message)
                    break
                elif ffplay:
                    # Algumas versões portáteis antigas interpretam -nostdin como uma
                    # opção com valor e acabam consumindo -hide_banner. O player não
                    # precisa de stdin: usamos somente opções compatíveis do FFplay.
                    seek_seconds = max(0.0, float(start_seconds or 0.0)) if index == 1 else 0.0
                    command = [ffplay, "-nodisp", "-autoexit", "-loglevel", "error", "-vn", "-ss", f"{seek_seconds:.3f}", str(path)]
                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        **hidden_process_kwargs(),
                    )
                    self.process = process
                    if index == 1 or len(paths) == 1:
                        try:
                            self.parent.after(0, lambda current_path=path, offset=seek_seconds: self._begin_waveform_progress(waveform_kind, current_path, playback_id, offset))
                        except Exception:
                            pass
                    while process.poll() is None:
                        if playback_id != self.playback_id or self.stop_event.wait(0.1):
                            try:
                                process.terminate()
                            except Exception:
                                pass
                            return
                    error_output = ""
                    if process.stderr is not None:
                        try:
                            error_output = process.stderr.read().decode("utf-8", errors="replace").strip()
                        except Exception:
                            error_output = ""
                    if self.process is process:
                        self.process = None
                    if process.returncode not in (0, None):
                        detail = error_output[-500:] if error_output else "FFplay terminou sem reproduzir o arquivo."
                        self.emit_status(f"FFplay não conseguiu reproduzir {path.name}: {detail}")
                        return
                else:
                    self.emit_status("FFplay não encontrado. Clique em BAIXAR / PREPARAR FERRAMENTAS; nenhum reprodutor externo será aberto.")
                    return
            except Exception as exc:
                self.emit_status(f"Erro ao reproduzir {path.name}: {exc}")
                return
        if playback_id != self.playback_id or self.stop_event.is_set():
            return
        try:
            self.parent.after(0, lambda: self._finish_waveform_progress(playback_id))
        except Exception:
            pass
        self.emit_status("Reprodução concluída")
        try:
            def restore_buttons():
                for button in (self.start_button, self.original_button):
                    if button is not None:
                        button.configure(state="normal")
                self._update_original_button()
            self.parent.after(0, restore_buttons)
        except Exception:
            pass


def apply_dubbed_finishing(path,project_root,trim=False,max_volume=False,backup=True):
    """Reuse scene editor DSP on one WAV, atomically; preserve previous version."""
    path=Path(path).resolve()
    if any(part.casefold()=='wav originais' for part in path.parts):raise ValueError('Este ajuste é somente para áudio dublado.')
    initial=path.stat();signature=(initial.st_size,initial.st_mtime_ns)
    with wave.open(str(path),'rb') as source:
        if source.getcomptype()!='NONE':raise ValueError('O áudio precisa ser WAV PCM.')
        track={'frames':source.readframes(source.getnframes()),'sample_rate':source.getframerate(),'channels':source.getnchannels(),'sample_width':source.getsampwidth()}
        expected=source.getnframes()*source.getnchannels()*source.getsampwidth()
    if not track['frames'] or len(track['frames'])!=expected:raise ValueError('Áudio vazio ou incompleto; arquivo preservado.')
    previous=track['frames'];gain=0.0
    if trim:track['frames'],_clips=process_scene_audio(track,project_root,preserve_clips=True)
    if max_volume:
        # Each call is the exact scene editor gain with its -1 dBFS ceiling.
        for _ in range(8):
            track['frames'],_clips,applied=process_scene_volume(track,24)
            gain+=applied
            if applied<23.999:break
    if track['frames']==previous:return {'changed':False,'gain_db':gain,'removed_seconds':0.0}
    removed=(len(previous)-len(track['frames']))/(track['sample_rate']*track['channels']*track['sample_width'])
    descriptor,tempname=tempfile.mkstemp(prefix='.__acabamento_',suffix='.wav',dir=path.parent);os.close(descriptor);temp=Path(tempname)
    try:
        with wave.open(str(temp),'wb') as output:
            output.setnchannels(track['channels']);output.setsampwidth(track['sample_width']);output.setframerate(track['sample_rate']);output.writeframes(track['frames'])
        current=path.stat()
        if (current.st_size,current.st_mtime_ns)!=signature:raise ValueError('O áudio mudou durante o ajuste; arquivo atual preservado.')
        if backup:
            from audio_versions import archive
            archive(path,project_root)
        os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)
    return {'changed':True,'gain_db':gain,'removed_seconds':removed}
