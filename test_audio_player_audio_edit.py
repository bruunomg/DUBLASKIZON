from pathlib import Path
from types import SimpleNamespace
import struct
import time
import tempfile
import tkinter as tk
import wave

import audio_player


def make_wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 8000
    frames = b"".join(struct.pack("<h", 12000 if index % 80 < 40 else -12000) for index in range(int(seconds * rate)))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(frames)


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    stem = "CAP01/cena_edit"
    original = project / "WAV ORIGINAIS" / f"{stem}.wav"
    dubbed = project / "dublado" / f"{stem}.wav"
    make_wav(original, 4.0)
    make_wav(dubbed, 3.0)

    root = tk.Tk()
    root.geometry("1100x800")
    manager = audio_player.AudioPlayerManager(root, project)
    manager.play_one(dubbed, "OUVIR CENA", playlist=[dubbed], index=0, scene_key=stem, scene_keys=[stem])
    root.update_idletasks()
    root.update()

    assert manager.audio_edit_button is not None
    assert manager.audio_undo_button is not None
    assert manager.audio_redo_button is not None
    assert manager.audio_cut_button is not None
    assert manager.audio_copy_button is not None
    assert manager.audio_paste_button is not None
    assert manager.audio_save_button is not None
    assert manager.audio_undo_button.cget("text") == "DESFAZER"
    assert manager.audio_redo_button.cget("text") == "REFAZER"
    assert manager.audio_cut_button.cget("text") == "RECORTAR"
    assert manager.audio_delete_button.cget("text") == "DELETE"
    manager.audio_edit_button.invoke()
    assert manager.audio_edit_mode is True

    original_canvas = manager.waveform_canvases["original"]
    original_canvas.update_idletasks()
    original_canvas.focus_set()
    width = original_canvas.winfo_width()
    plot_width = manager._waveform_plot_width("original", width)
    x1 = 2 + plot_width * 1.0 / 4.0
    x2 = 2 + plot_width * 2.0 / 4.0
    manager._on_waveform_press("original", SimpleNamespace(x=x1))
    manager._on_waveform_release("original", SimpleNamespace(x=x2))
    assert manager.waveform_selection_kind == "original"
    original_canvas.focus_set()
    original_canvas.event_generate("<Control-c>")
    root.update_idletasks()
    assert manager.audio_clip_buffer is not None
    assert manager.audio_clip_buffer["source_kind"] == "original"
    assert len(manager.audio_clip_buffer["frames"]) == 8000 * 2

    dubbed_canvas = manager.waveform_canvases["dubbed"]
    dubbed_canvas.update_idletasks()
    dubbed_width = dubbed_canvas.winfo_width()
    dubbed_plot = manager._waveform_plot_width("dubbed", dubbed_width)
    insertion_x = 2 + dubbed_plot * 1.0 / 3.0
    manager._on_waveform_press("dubbed", SimpleNamespace(x=insertion_x))
    manager._on_waveform_release("dubbed", SimpleNamespace(x=insertion_x))
    before_duration = manager.waveform_data["dubbed"]["duration"]
    before_frames = bytes(manager.audio_edit_working["dubbed"]["frames"])
    dubbed_canvas.focus_set()
    dubbed_canvas.event_generate("<Control-v>")
    root.update_idletasks()
    after_duration = manager.waveform_data["dubbed"]["duration"]
    assert after_duration > before_duration
    assert "ORIGINAL" in manager.audio_edit_status_var.get().upper() or "DUBLADO" in manager.audio_edit_status_var.get().upper()
    assert manager.audio_edit_dirty is True

    # O histórico deve desfazer e refazer a colagem pelos atalhos pedidos.
    pasted_frames = bytes(manager.audio_edit_working["dubbed"]["frames"])
    assert pasted_frames != before_frames
    dubbed_canvas.focus_set()
    dubbed_canvas.event_generate("<Control-z>")
    root.update_idletasks()
    assert manager.audio_edit_working["dubbed"]["frames"] == before_frames
    assert manager.audio_edit_dirty is False
    dubbed_canvas.event_generate("<Control-y>")
    root.update_idletasks()
    assert manager.audio_edit_working["dubbed"]["frames"] == pasted_frames
    assert manager.audio_edit_dirty is True

    # O preview deve ser um WAV real com exatamente a edição atual em memória.
    preview_path = manager._materialize_audio_edit_preview("dubbed")
    assert preview_path is not None and preview_path.is_file()
    with wave.open(str(preview_path), "rb") as preview_wav:
        assert preview_wav.readframes(preview_wav.getnframes()) == pasted_frames

    # A tecla Espaço deve iniciar o preview, pausar e retomar do mesmo preview.
    start_calls = []
    original_start_paths = manager._start_paths
    manager._start_paths = lambda paths, kind, start_seconds=0.0: start_calls.append((Path(paths[0]), kind, start_seconds))
    dubbed_canvas.focus_set()
    dubbed_canvas.event_generate("<space>")
    root.update_idletasks()
    assert start_calls and start_calls[-1][1] == "dubbed"
    assert start_calls[-1][0] == manager.audio_edit_preview_path
    active_preview = manager.audio_edit_preview_path
    manager.waveform_active_kind = "dubbed"
    manager.waveform_active_path = active_preview
    manager.waveform_active_playback_id = manager.playback_id
    manager.waveform_active_started_at = time.monotonic() - 0.25
    manager.waveform_active_duration = manager.waveform_data["dubbed"]["duration"]
    dubbed_canvas.event_generate("<space>")
    root.update_idletasks()
    assert manager.audio_paused_kind == "dubbed"
    assert manager.audio_paused_seconds > 0.0
    start_calls.clear()
    dubbed_canvas.event_generate("<space>")
    root.update_idletasks()
    assert start_calls and start_calls[-1][1] == "dubbed"
    assert start_calls[-1][0] == manager.audio_edit_preview_path
    assert start_calls[-1][2] > 0.0
    manager._start_paths = original_start_paths

    manager._save_audio_edit()
    assert manager.audio_edit_dirty is False
    assert dubbed.stat().st_size > 0
    backups = list((project / "revisoes" / "CAP01").glob("cena_edit_edit_v*.wav"))
    assert backups, "O salvamento deve criar backup em revisoes"

    # A seleção real continua disponível para CORTAR e o comando é restrito ao DUBLADO.
    manager.audio_edit_mode = True
    dubbed_duration = manager.waveform_data["dubbed"]["duration"]
    dubbed_width = dubbed_canvas.winfo_width()
    dubbed_plot = manager._waveform_plot_width("dubbed", dubbed_width)
    cut_x1 = 2 + dubbed_plot * 0.5 / dubbed_duration
    cut_x2 = 2 + dubbed_plot * 0.75 / dubbed_duration
    manager._on_waveform_press("dubbed", SimpleNamespace(x=cut_x1))
    manager._on_waveform_release("dubbed", SimpleNamespace(x=cut_x2))
    duration_before_cut = manager.waveform_data["dubbed"]["duration"]
    dubbed_canvas.focus_set()
    dubbed_canvas.event_generate("<Control-x>")
    root.update_idletasks()
    duration_after_cut = manager.waveform_data["dubbed"]["duration"]
    assert duration_after_cut < duration_before_cut
    assert manager.audio_clip_buffer is not None

    dubbed_duration = manager.waveform_data["dubbed"]["duration"]
    dubbed_plot = manager._waveform_plot_width("dubbed", dubbed_width)
    delete_x1 = 2 + dubbed_plot * 0.25 / dubbed_duration
    delete_x2 = 2 + dubbed_plot * 0.50 / dubbed_duration
    manager._on_waveform_press("dubbed", SimpleNamespace(x=delete_x1))
    manager._on_waveform_release("dubbed", SimpleNamespace(x=delete_x2))
    buffer_before_delete = manager.audio_clip_buffer["frames"]
    dubbed_canvas.focus_set()
    dubbed_canvas.event_generate("<BackSpace>")
    root.update_idletasks()
    assert manager.waveform_data["dubbed"]["duration"] < dubbed_duration
    assert manager.audio_clip_buffer["frames"] == buffer_before_delete

    manager.close_window()
    root.destroy()

print("audio_player_audio_edit_ok")
