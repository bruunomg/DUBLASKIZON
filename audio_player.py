"""Reprodução de áudio portátil para o Dublaskizon.

Usa FFplay, distribuído com o FFmpeg, ou o reprodutor padrão do Windows, conforme a preferência global do aplicativo. O modo FFplay não abre janela de terminal.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

try:
    from tkinter import Button, Canvas, DoubleVar, END, Frame, Label, Menu, Scrollbar, StringVar, Text, Toplevel, messagebox, ttk
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
    names = ("ffplay.exe", "ffplay")
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    module_dir = Path(__file__).resolve().parent
    app_dir = Path(os.environ.get("DUBLASKIZON_APP_DIR", module_dir)).expanduser()
    # Diretórios amplos (APP_DIR e a raiz do projeto) são consultados somente
    # diretamente. A busca recursiva fica restrita às pastas portáteis de
    # ferramentas, evitando percorrer milhares de WAVs ao abrir OUVIR CENA.
    direct_roots = [app_dir, module_dir]
    tool_roots = [
        app_dir / "ferramentas_audio",
        app_dir / "tools",
        module_dir / "ferramentas_audio",
        module_dir / "tools",
    ]
    if project_root is not None:
        project = Path(project_root).expanduser()
        direct_roots.append(project)
        tool_roots.extend([project / "ferramentas_audio", project / "tools"])
    seen: set[str] = set()
    for root in direct_roots:
        key = os.path.normcase(os.path.abspath(str(root)))
        if key in seen:
            continue
        seen.add(key)
        for candidate_name in names:
            candidate = root / candidate_name
            if candidate.is_file():
                return str(candidate)
    for root in tool_roots:
        key = os.path.normcase(os.path.abspath(str(root)))
        if key in seen:
            continue
        seen.add(key)
        for candidate_name in names:
            candidate = root / candidate_name
            if candidate.is_file():
                return str(candidate)
        try:
            for candidate in root.rglob("*"):
                if candidate.is_file() and candidate.name.casefold() in {name.casefold() for name in names}:
                    return str(candidate)
        except (OSError, PermissionError):
            pass
    return None


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
        self.current_source_kind = "unknown"
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
        self.waveform_progress = {"original": 0.0, "dubbed": 0.0}
        self.waveform_active_kind: str | None = None
        self.waveform_active_path: Path | None = None
        self.waveform_active_playback_id: int | None = None
        self.waveform_active_started_at = 0.0
        self.waveform_active_duration = 0.0
        self.waveform_active_offset = 0.0
        self.waveform_progress_after_id = None
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
        self.audio_undo_button = None
        self.audio_redo_button = None
        self.audio_cut_button = None
        self.audio_delete_button = None
        self.audio_copy_button = None
        self.audio_paste_button = None
        self.audio_save_button = None
        self.audio_edit_undo_stack: list[tuple[str, bytes]] = []
        self.audio_edit_redo_stack: list[tuple[str, bytes]] = []
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
        self._refresh_waveforms()
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
        if auto_var is None and request_r_var is None:
            return
        try:
            if auto_var is not None:
                widget = ttk.Checkbutton(container, text=i18n.tr("Abrir Audacity após redublar"), variable=auto_var, command=auto_command)
                widget.pack(side="left", anchor="w", padx=(0, 14))
                self.review_preference_widgets.append(widget)
            if request_r_var is not None:
                widget = ttk.Checkbutton(container, text=i18n.tr("Pedido de alterar pronúncia do R"), variable=request_r_var, command=request_r_command)
                widget.pack(side="left", anchor="w")
                self.review_preference_widgets.append(widget)
            container.pack(fill="x", pady=(0, 4), before=controls)
        except Exception:
            pass

    def _notify_scene_selection(self) -> None:
        if not callable(self.selection_callback):
            return
        try:
            self.selection_callback(self.current_context_key, self.current_index)
        except Exception:
            pass

    def _invoke_review_action(self, action_name: str) -> None:
        callback = self.review_actions.get(action_name)
        if not callable(callback):
            return
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
                    frame_bytes = sample_width * channels
                    peaks = []
                    for offset in range(0, len(raw) - frame_bytes + 1, frame_bytes):
                        frame = raw[offset:offset + frame_bytes]
                        values = []
                        for channel in range(channels):
                            chunk = frame[channel * sample_width:(channel + 1) * sample_width]
                            if sample_width == 1:
                                value = int(chunk[0]) - 128
                                channel_scale = 128.0
                            elif sample_width == 2:
                                value = int.from_bytes(chunk, "little", signed=True)
                                channel_scale = scale
                            elif sample_width == 3:
                                value = int.from_bytes(chunk + (b"\xff" if chunk[-1] & 0x80 else b"\x00"), "little", signed=True)
                                channel_scale = 1 << 23
                            else:
                                value = int.from_bytes(chunk, "little", signed=True)
                                channel_scale = scale
                            values.append(abs(value) / channel_scale)
                        peaks.append(max(values) if values else 0.0)
                    samples.append(min(1.0, max(peaks) if peaks else 0.0))
                return {"samples": samples, "duration": duration, "sample_rate": sample_rate, "channels": channels}
        except (OSError, EOFError, wave.Error, ValueError):
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
            peak = 0.0
            for offset in range(0, len(block) - frame_bytes + 1, frame_bytes):
                frame = block[offset:offset + frame_bytes]
                frame_peak = 0.0
                for channel in range(channels):
                    chunk = frame[channel * sample_width:(channel + 1) * sample_width]
                    if sample_width == 1:
                        value = int(chunk[0]) - 128
                        channel_scale = 128.0
                    elif sample_width == 2:
                        value = int.from_bytes(chunk, "little", signed=True)
                        channel_scale = scale
                    elif sample_width == 3:
                        value = int.from_bytes(chunk + (bytes((255,)) if chunk[-1] & 0x80 else bytes((0,))), "little", signed=True)
                        channel_scale = 1 << 23
                    else:
                        value = int.from_bytes(chunk, "little", signed=True)
                        channel_scale = scale
                    frame_peak = max(frame_peak, abs(value) / channel_scale)
                peak = max(peak, frame_peak)
            samples.append(min(1.0, peak))
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
            self.audio_edit_working[kind] = track
            return track
        except (OSError, EOFError, wave.Error, ValueError):
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
            for kind, track in self.audio_edit_working.items()
        )

    def _set_edit_frames(self, kind: str, track: dict, raw: bytes, record_history: bool = True) -> None:
        current = bytes(track.get("frames", b""))
        updated = bytes(raw)
        if current == updated:
            return
        # Nunca deixamos um preview antigo continuar tocando enquanto a faixa
        # editável muda; isso evita ouvir o WAV anterior depois de uma colagem.
        self.stop(announce=False)
        self._remove_audio_edit_preview()
        if record_history:
            self.audio_edit_undo_stack.append((kind, current))
            self.audio_edit_redo_stack.clear()
        track["frames"] = updated
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
        self.audio_edit_redo_stack.append((kind, bytes(track.get("frames", b""))))
        self._set_edit_frames(kind, track, previous, record_history=False)
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
        self.audio_edit_undo_stack.append((kind, bytes(track.get("frames", b""))))
        self._set_edit_frames(kind, track, next_frames, record_history=False)
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
        click_x = max(2.0, min(float(x), 2.0 + plot_width))
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
        self.waveform_drag_kind = kind
        self.waveform_drag_start_x = float(getattr(event, "x", 0.0))
        start_seconds = self._waveform_x_to_seconds(kind, self.waveform_drag_start_x)
        self.waveform_selection_ranges[kind] = (start_seconds, start_seconds)
        self.waveform_selection_kind = kind
        self._draw_waveform(kind)
        self._update_audio_edit_buttons()

    def _on_waveform_motion(self, kind: str, event) -> None:
        if not self.audio_edit_mode or self.waveform_drag_kind != kind:
            return
        end_seconds = self._waveform_x_to_seconds(kind, float(getattr(event, "x", 0.0)))
        start_seconds = self._waveform_x_to_seconds(kind, self.waveform_drag_start_x)
        self.waveform_selection_ranges[kind] = (start_seconds, end_seconds)
        self.waveform_selection_kind = kind
        self._draw_waveform(kind)

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


    def _copy_audio_selection(self, _event=None):
        if not self.audio_edit_mode:
            return None
        kind = self.waveform_selection_kind or self._focused_waveform_kind()
        selected = self._edit_selection_frames(kind) if kind else None
        if selected is None:
            self._set_audio_edit_status("Selecione um trecho em ORIGINAL ou DUBLADO para copiar.")
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
        self._set_audio_edit_status(f"Trecho copiado de {kind}: {self._format_wave_duration((end_frame - start_frame) / track['sample_rate'])}.")
        self._update_audio_edit_buttons()
        return "break"

    def _cut_audio_selection(self, _event=None):
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
        self._set_edit_frames(kind, track, track["frames"][:start_byte] + track["frames"][end_byte:])
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
        self._set_edit_frames(kind, track, track["frames"][:start_byte] + track["frames"][end_byte:])
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
        new_frames = target["frames"][:start_byte] + clip["frames"] + target["frames"][end_byte:]
        self._set_edit_frames("dubbed", target, new_frames)
        self._set_audio_edit_status(f"Trecho colado no DUBLADO: {self._format_wave_duration(len(clip['frames']) / frame_bytes / target['sample_rate'])}.")
        return "break"

    def _update_audio_edit_buttons(self) -> None:
        has_selection = any(selection is not None for selection in self.waveform_selection_ranges.values())
        has_nonempty_selection = any(selection is not None and abs(float(selection[1]) - float(selection[0])) > 0.0001 for selection in self.waveform_selection_ranges.values())
        for button, enabled in (
            (self.audio_undo_button, self.audio_edit_mode and bool(self.audio_edit_undo_stack)),
            (self.audio_redo_button, self.audio_edit_mode and bool(self.audio_edit_redo_stack)),
            (self.audio_cut_button, self.audio_edit_mode and self.waveform_selection_kind == "dubbed" and has_nonempty_selection),
            (self.audio_delete_button, self.audio_edit_mode and self.waveform_selection_kind == "dubbed" and has_nonempty_selection),
            (self.audio_copy_button, self.audio_edit_mode and self.waveform_selection_kind in {"original", "dubbed"} and has_nonempty_selection),
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
            self.audio_edit_undo_stack = []
            self.audio_edit_redo_stack = []
            self.audio_edit_base_frames = {kind: bytes(track.get("frames", b"")) for kind, track in self.audio_edit_working.items()}
            self.waveform_selection_ranges = {"original": None, "dubbed": None}
            self.waveform_selection_kind = None
            self._refresh_waveforms()
            self._set_audio_edit_status("Modo EDITAR ativo. Arraste sobre uma onda; ORIGINAL é somente leitura e COLAR aplica no DUBLADO.")
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

    def _toggle_edit_play_pause(self, _event=None):
        if not self.audio_edit_mode:
            return None
        active_kind = self.waveform_active_kind
        if active_kind in {"original", "dubbed"} and self.waveform_active_path is not None:
            elapsed = max(0.0, time.monotonic() - self.waveform_active_started_at)
            paused_at = min(self.waveform_active_duration, self.waveform_active_offset + elapsed)
            self.stop(announce=False, clear_pause=False)
            self.audio_paused_kind = active_kind
            self.audio_paused_path = self.waveform_active_path
            self.audio_paused_seconds = paused_at
            self._set_audio_edit_status(f"Pausado em {self._format_wave_duration(paused_at)}. Pressione Espaço para continuar.")
            return "break"
        kind = self.audio_paused_kind or self._focused_waveform_kind() or "dubbed"
        start_seconds = self.audio_paused_seconds if self.audio_paused_kind == kind else 0.0
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
            backup = self._archive_audio_edit_backup(target)
            os.replace(temporary, target)
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
            self._set_audio_edit_status(f"DUBLADO salvo com segurança.{suffix}")
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

    def _waveform_plot_width(self, kind: str, width: int) -> float:
        data = self.waveform_data.get(kind) or {}
        duration = max(0.0, float(data.get("duration", 0.0) or 0.0))
        reference_duration = max(duration, float(self.waveform_reference_duration or 0.0))
        duration_ratio = duration / reference_duration if reference_duration > 0 else 1.0
        return max(8.0, (max(180, int(width)) - 4) * min(1.0, duration_ratio))

    def _seek_from_waveform(self, kind: str, event) -> None:
        """Inicia a faixa no instante correspondente ao ponto clicado."""
        if kind not in {"original", "dubbed"}:
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
            click_x = max(start_x, min(float(event.x), end_x))
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
            canvas.delete("waveform")
            canvas.delete("waveform_selection")
            canvas.delete("waveform_end")
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
            try:
                color = button_style(self.theme, role)["bg"]
            except Exception:
                color = "#7C3AED" if kind == "original" else "#15803D"
            plot_width = self._waveform_plot_width(kind, width)
            coords = []
            for index, value in enumerate(samples):
                x = 2 + plot_width * index / max(1, len(samples) - 1)
                coords.extend((x, center - value * amplitude, x, center + value * amplitude))
            for index in range(0, len(coords), 4):
                canvas.create_line(coords[index], coords[index + 1], coords[index + 2], coords[index + 3], fill=color, width=1, tags="waveform")
            end_x = min(width - 2, 2 + plot_width)
            canvas.create_line(end_x, 3, end_x, height - 3, fill=color, width=4, tags="waveform_end")
            selection = self.waveform_selection_ranges.get(kind) if self.audio_edit_mode else None
            if selection is not None:
                selection_start, selection_end = sorted((float(selection[0]), float(selection[1])))
                selection_x1 = 2 + plot_width * selection_start / max(0.0001, float(data.get("duration", 0.0) or 0.0))
                selection_x2 = 2 + plot_width * selection_end / max(0.0001, float(data.get("duration", 0.0) or 0.0))
                canvas.create_rectangle(selection_x1, 3, selection_x2, height - 3, fill=color, stipple="gray25", outline=color, width=1, tags="waveform_selection")
                canvas.tag_lower("waveform_selection", "waveform")
            if self.waveform_active_kind == kind:
                progress = min(1.0, max(0.0, float(self.waveform_progress.get(kind, 0.0) or 0.0)))
                progress_x = 2 + (plot_width - 2) * progress
                canvas.create_line(2, height - 4, progress_x, height - 4, fill=color, width=4, tags="progress")
                canvas.create_line(progress_x, 4, progress_x, height - 5, fill=color, width=2, tags="progress")
                canvas.create_oval(progress_x - 4, height - 8, progress_x + 4, height, fill=color, outline=color, tags="progress")
        except Exception:
            pass

    def _refresh_waveforms(self) -> None:
        paths = {
            "original": self._current_audio_path("original"),
            "dubbed": self._current_audio_path("dubbed"),
        }
        for kind, path in paths.items():
            working = self.audio_edit_working.get(kind) if self.audio_edit_mode else None
            if working is not None:
                self.waveform_data[kind] = self._waveform_from_pcm(working.get("frames", b""), working.get("channels", 1), working.get("sample_width", 2), working.get("sample_rate", 1))
            else:
                self.waveform_data[kind] = self._read_waveform(path)
        self.waveform_reference_duration = max(
            (float((data or {}).get("duration", 0.0) or 0.0) for data in self.waveform_data.values()),
            default=0.0,
        )
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
        except Exception:
            pass

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
        frame = Frame(parent, bg=surface, height=54)
        frame.pack(side="left", fill="x", expand=True, padx=4)
        frame.pack_propagate(False)
        self.review_progress_frame = frame
        self.review_progress_widgets = [frame]
        style = ttk.Style(self.window)
        clone_color = button_style(self.theme, "primary")["bg"] if button_style is not None else "#2563EB"
        dub_color = button_style(self.theme, "success")["bg"] if button_style is not None else "#15803D"
        style.configure("AudioReviewClone.Horizontal.TProgressbar", troughcolor=input_border, background=clone_color, lightcolor=clone_color, darkcolor=clone_color)
        style.configure("AudioReviewDub.Horizontal.TProgressbar", troughcolor=input_border, background=dub_color, lightcolor=dub_color, darkcolor=dub_color)
        clone_column = Frame(frame, bg=surface)
        clone_column.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.review_progress_widgets.append(clone_column)
        clone_label = Label(clone_column, text=i18n.tr("CLONANDO REFERÊNCIA"), bg=surface, fg=muted, font=("Segoe UI", 7, "bold"), anchor="w")
        clone_label.pack(fill="x")
        self.review_progress_widgets.append(clone_label)
        self.review_clone_var = DoubleVar(value=0.0)
        self.review_clone_bar = ttk.Progressbar(clone_column, orient="horizontal", mode="determinate", maximum=100, variable=self.review_clone_var, style="AudioReviewClone.Horizontal.TProgressbar")
        self.review_clone_bar.pack(fill="x", pady=(2, 0))
        dub_column = Frame(frame, bg=surface)
        dub_column.pack(side="left", fill="both", expand=True, padx=(4, 0))
        self.review_progress_widgets.append(dub_column)
        dub_label = Label(dub_column, text=i18n.tr("DUBLANDO CENA"), bg=surface, fg=muted, font=("Segoe UI", 7, "bold"), anchor="w")
        dub_label.pack(fill="x")
        self.review_progress_widgets.append(dub_label)
        self.review_dub_var = DoubleVar(value=0.0)
        self.review_dub_bar = ttk.Progressbar(dub_column, orient="horizontal", mode="determinate", maximum=100, variable=self.review_dub_var, style="AudioReviewDub.Horizontal.TProgressbar")
        self.review_dub_bar.pack(fill="x", pady=(2, 0))
        self._refresh_review_snapshot()

    def show_window(self, title: str, initial_text: str):
        if not TK_AVAILABLE:
            return
        # Preserva pending_paths: play_one/play_all já colocaram os arquivos na fila.
        self._destroy_window(clear_pending=False)
        window = Toplevel(self.parent)
        window.title(i18n.tr(title))
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

    def apply_theme(self, theme: dict):
        self.theme = {**self.theme, **theme}
        if self.window is None:
            return
        try:
            if self.window.winfo_exists():
                surface = self.theme.get("surface", "#FFFFFF")
                text = self.theme.get("text", "#1F2937")
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
                    (self.start_button, "success"),
                    (self.original_button, "accent"),
                    (self.stop_button, "danger"),
                    (self.close_button, "secondary"),
                    (self.scene_text_save_button, "primary"),
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
        except Exception:
            pass

    def _current_audio_path(self, kind: str | None = None) -> Path | None:
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
        for source_folder_name in ("dublado", "WAV ORIGINAIS"):
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

    def _find_original_audio(self, path: Path) -> Path | None:
        """Localiza o WAV de mesmo nome na pasta WAV ORIGINAIS do projeto."""
        return self._find_project_audio_by_stem("WAV ORIGINAIS", path)

    def _find_dubbed_audio(self, path: Path) -> Path | None:
        return self._find_project_audio_by_stem("dublado", path)

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

    def play_one(self, path: Path, title: str = "OUVIR ÁUDIO", playlist: list[Path] | None = None, index: int | None = None, scene_key: str | None = None, scene_keys: list[str] | None = None):
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            self.emit_status(f"Arquivo de áudio não encontrado: {path}")
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
        self.navigation_paths = [Path(item).expanduser().resolve() for item in candidates]
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
        self.thread = threading.Thread(target=self._play_thread, args=(valid_paths, playback_id, "original" if kind == "original" else "dubbed", max(0.0, float(start_seconds or 0.0))), daemon=True)
        self.thread.start()

    def start_pending(self):
        self.audio_paused_kind = None
        self.audio_paused_path = None
        self.audio_paused_seconds = 0.0
        if self.audio_edit_mode and self.audio_edit_working.get("dubbed") is not None:
            self._play_edit_preview("dubbed", 0.0)
            return
        paths = self.dubbed_pending_paths or self.pending_paths
        self._start_paths(paths, "dublada")

    def start_original_pending(self):
        self.audio_paused_kind = None
        self.audio_paused_path = None
        self.audio_paused_seconds = 0.0
        if self.audio_edit_mode and self.audio_edit_working.get("original") is not None:
            self._play_edit_preview("original", 0.0)
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
