from pathlib import Path
import struct
import tempfile
import time
import tkinter as tk
import wave

import audio_player
import review_tab
from ui_theme import button_style
from review_tab import ReviewApp


def make_wav(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"".join(struct.pack("<h", value) for value in (0, 12000, -12000, 0) * 2000))


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    stem = "CAP01/cena_001"
    dubbed = project / "dublado" / f"{stem}.wav"
    original = project / "WAV ORIGINAIS" / f"{stem}.wav"
    text_file = project / "TXT TEXTO PORTUGUES" / f"{stem}.txt"
    make_wav(dubbed)
    make_wav(original)
    text_file.parent.mkdir(parents=True, exist_ok=True)
    text_file.write_text("Texto inicial.\n", encoding="utf-8")

    root = tk.Tk()
    root.geometry("1200x900")
    root.update_idletasks()
    manager = audio_player.AudioPlayerManager(root, project)
    saved = []

    def loader(key):
        assert key == stem
        return {"text": text_file.read_text(encoding="utf-8"), "path": text_file, "title": "Áudio: cena_001.wav"}

    def saver(key, text):
        saved.append((key, text))
        text_file.write_text(text + "\n", encoding="utf-8")
        return True, "Texto salvo."

    manager.set_scene_text_integration(loader, saver)
    manager.set_scene_integration(lambda *_args: None, {name: (lambda *_args: None) for name in ("open_audacity", "approve", "reject", "redub", "redub_other")})
    manager.set_review_snapshot_provider(lambda _key=None: {"history": "HISTÓRICO DE TESTE", "regen": "REFAZENDO TESTE", "clone_progress": 35, "dub_progress": 72, "phase": "DUBLANDO CENA"})
    manager.play_one(dubbed, "OUVIR CENA", playlist=[dubbed], index=0, scene_key=stem, scene_keys=[stem])
    root.update_idletasks()
    assert manager.scene_text_title_var.get() == "Áudio: cena_001.wav"
    assert manager.scene_text_box.get("1.0", "end-1c").strip() == "Texto inicial."
    assert manager.waveform_data["original"] is not None
    assert manager.waveform_data["dubbed"] is not None
    assert manager.waveform_split is None
    assert manager.window_body is None
    assert manager.window_content is not None
    assert manager.window.cget("bg") == manager.window_border_color
    assert manager.window_border_color == "#FACC15"
    assert manager.window_content.cget("bg") == manager.theme.get("surface")
    assert manager.review_top_row is None
    assert manager.review_top_panel is None
    assert manager.review_panel is None
    assert manager.review_progress_frame is not None
    assert manager.review_clone_bar is not None
    assert manager.review_dub_bar is not None
    root.update()
    assert manager.scene_text_box.winfo_height() < 170
    assert manager.stop_button.winfo_rootx() >= manager.start_button.winfo_rootx() + manager.start_button.winfo_width()
    # Ações de edição ficam unidas; EDITAR/SAIR DO EDITAR fica separado à direita.
    edit_group = [manager.audio_undo_button, manager.audio_redo_button, manager.audio_save_button, manager.audio_paste_button, manager.audio_copy_button, manager.audio_delete_button, manager.audio_cut_button]
    assert all(left.winfo_rootx() < right.winfo_rootx() for left, right in zip(edit_group, edit_group[1:]))
    assert manager.audio_undo_button.winfo_rootx() < manager.audio_redo_button.winfo_rootx() < manager.audio_save_button.winfo_rootx()
    assert manager.audio_redo_button.winfo_rootx() + manager.audio_redo_button.winfo_width() + 10 <= manager.audio_save_button.winfo_rootx()
    assert manager.audio_cut_button.winfo_rootx() + manager.audio_cut_button.winfo_width() + 10 <= manager.audio_edit_button.winfo_rootx()
    assert manager.review_history_box is None
    assert manager.review_regen_box is None
    assert float(manager.review_clone_var.get()) == 35.0
    assert float(manager.review_dub_var.get()) == 72.0
    assert manager.waveform_canvases["original"].find_withtag("waveform")
    assert manager.waveform_canvases["dubbed"].find_withtag("waveform")
    assert manager.waveform_canvases["original"].find_withtag("waveform_end")
    assert len(manager.waveform_canvases["original"].find_withtag("waveform_end")) == 1
    assert len(manager.waveform_canvases["dubbed"].find_withtag("waveform_end")) == 1
    assert not manager.waveform_canvases["original"].find_withtag("waveform_center")
    assert not manager.waveform_canvases["dubbed"].find_withtag("waveform_center")
    assert button_style(manager.theme, "accent")["bg"] in {manager.waveform_canvases["original"].itemcget(item, "fill") for item in manager.waveform_canvases["original"].find_withtag("waveform")}
    assert button_style(manager.theme, "success")["bg"] in {manager.waveform_canvases["dubbed"].itemcget(item, "fill") for item in manager.waveform_canvases["dubbed"].find_withtag("waveform")}
    assert manager.close_button is not None
    assert manager.window.resizable()[0] in (0, 1, "0", "1")
    assert manager.window.resizable()[1] in (0, 1, "0", "1")
    # O maximizar/restaurar é o controle nativo da barra de título do Windows.
    # Em uma janela alta, o painel de texto absorve o espaço livre e o rodapé não some.
    manager.window.geometry("1200x900+0+0")
    root.update_idletasks()
    assert manager.scene_text_box.winfo_height() > 190
    window_bottom = manager.window.winfo_rooty() + manager.window.winfo_height()
    visible_buttons = [manager.previous_button, manager.next_button, manager.original_button, manager.start_button, manager.stop_button, manager.close_button]
    visible_buttons.extend(button for button, _role in manager.review_action_buttons)
    visible_buttons.extend(button for button, _role in manager.audio_action_buttons)
    assert all(button.winfo_rooty() + button.winfo_height() <= window_bottom for button in visible_buttons)
    assert manager.waveform_duration_vars["original"].get().startswith("Duração: 00:01.00")
    assert manager.waveform_duration_vars["dubbed"].get().startswith("Duração: 00:01.00")
    manager.waveform_data["original"]["duration"] = 2.0
    manager.waveform_data["dubbed"]["duration"] = 1.0
    manager.waveform_reference_duration = 2.0
    manager.apply_theme({"mode": "escuro", "surface": "#1F2937", "text": "#F8FAFC"})
    root.update()
    assert manager.window.cget("bg") == "#FACC15"
    assert manager.window_content.cget("bg") == "#1F2937"
    assert manager._waveform_plot_width("dubbed", 700) < manager._waveform_plot_width("original", 700)
    manager.playback_id = 41
    manager.stop_event.clear()
    manager._begin_waveform_progress("dubbed", dubbed, 41)
    manager.waveform_active_started_at = time.monotonic() - 0.5
    manager._poll_waveform_progress()
    assert 0.2 < manager.waveform_progress["dubbed"] < 0.8
    manager._finish_waveform_progress(41)
    assert manager.waveform_progress["dubbed"] == 1.0
    manager.stop()
    manager.scene_text_box.delete("1.0", "end")
    manager.scene_text_box.insert("1.0", "Texto alterado para redublar.")
    manager._save_scene_text_from_window()
    assert saved == [(stem, "Texto alterado para redublar.")]
    assert text_file.read_text(encoding="utf-8").strip() == "Texto alterado para redublar."
    manager.close_window()
    root.destroy()

with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    review_tab.configure_project_root(project)
    stem = "CAP01/cena_001"
    text_file = project / "TXT TEXTO PORTUGUES" / f"{stem}.txt"
    text_file.parent.mkdir(parents=True, exist_ok=True)
    text_file.write_text("Antes.\n", encoding="utf-8")
    review = ReviewApp.__new__(ReviewApp)
    review.text_by_stem = {stem: text_file}
    review.audio_by_stem = {}
    review.state = {}
    review.current_stem = lambda: stem
    review.update_history = lambda _stem: None
    review.save_scene_text_from_player(stem, "Depois.")
    assert text_file.read_text(encoding="utf-8").strip() == "Depois."

print("audio_player_scene_text_ok")
