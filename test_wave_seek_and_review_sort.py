from pathlib import Path
from types import SimpleNamespace
import struct
import tempfile
import tkinter as tk
import wave

import audio_player
import review_tab
from review_tab import ReviewApp


def make_wav(path: Path, seconds: float = 4.0, rate: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(seconds * rate)
    frames = b"".join(struct.pack("<h", 10000 if index % 40 < 20 else -10000) for index in range(count))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(frames)


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    stem = "CAP01/cena_seek"
    original = project / "WAV ORIGINAIS" / f"{stem}.wav"
    dubbed = project / "dublado" / f"{stem}.wav"
    make_wav(original)
    make_wav(dubbed)

    root = tk.Tk()
    root.geometry("1100x800")
    manager = audio_player.AudioPlayerManager(root, project)
    manager.play_one(dubbed, "OUVIR CENA", playlist=[dubbed], index=0, scene_key=stem, scene_keys=[stem])
    root.update_idletasks()
    root.update()

    calls = []
    manager._start_paths = lambda paths, kind, start_seconds=0.0: calls.append((paths, kind, start_seconds))
    original_canvas = manager.waveform_canvases["original"]
    dubbed_canvas = manager.waveform_canvases["dubbed"]
    original_canvas.update_idletasks()
    dubbed_canvas.update_idletasks()

    manager._seek_from_waveform("original", SimpleNamespace(x=original_canvas.winfo_width() // 2))
    assert calls and calls[-1][0] == [original.resolve()]
    assert calls[-1][1] == "original"
    assert 1.5 < calls[-1][2] < 2.5

    manager._seek_from_waveform("dubbed", SimpleNamespace(x=dubbed_canvas.winfo_width() - 3))
    assert calls[-1][0] == [dubbed.resolve()]
    assert calls[-1][1] == "dubbed"
    assert calls[-1][2] > 3.5

    manager.playback_mode = "windows"
    before = len(calls)
    manager._seek_from_waveform("original", SimpleNamespace(x=original_canvas.winfo_width() // 2))
    assert len(calls) == before
    manager.close_window()
    root.destroy()

with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    stem_approved = "CAP01/aprovada"
    stem_pending = "CAP01/pendente"
    stem_rejected = "CAP01/rejeitada"
    for stem in (stem_approved, stem_pending, stem_rejected):
        make_wav(project / "WAV ORIGINAIS" / f"{stem}.wav", seconds=1.0)
        text_path = project / "TXT TEXTO PORTUGUES" / f"{stem}.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text("Texto", encoding="utf-8")

    old_askyesno = review_tab.messagebox.askyesno
    review_tab.messagebox.askyesno = lambda *args, **kwargs: False
    root = tk.Tk()
    root.geometry("1000x700")
    review_tab.configure_project_root(project)
    try:
        review = ReviewApp(root, embedded=True)
        review.state = {
            stem_approved: {"status": "aprovada"},
            stem_pending: {"status": "pendente"},
            stem_rejected: {"status": "rejeitada"},
        }
        review.default_stems = [stem_pending, stem_approved, stem_rejected]
        review.stems = list(review.default_stems)
        review.current_index = 0
        review.scene_sort_var.set("Aprovadas primeiro")
        review._on_scene_sort_selected()
        root.update_idletasks()
        assert review.stems[0] == stem_approved
        assert review.stems[1] == stem_pending
        assert review.stems[2] == stem_rejected
        assert review.scene_list.get(0).startswith("[OK]")
        review.scene_sort_var.set("Rejeitadas primeiro")
        review._on_scene_sort_selected()
        assert review.stems[0] == stem_rejected
        assert review.scene_list.get(0).startswith("[REFAZER]")
        review.root.destroy()
    finally:
        review_tab.messagebox.askyesno = old_askyesno
        try:
            root.destroy()
        except tk.TclError:
            pass

print("wave_seek_and_review_sort_ok")
