import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import tkinter as tk

import batch_tab
import review_tab
from audio_player import AudioPlayerManager


def make_wav(path: Path, sample_rate: int = 24000, channels: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * channels * int(sample_rate * 0.03))


class FakePopen:
    commands = []

    def __init__(self, command, **_kwargs):
        self.command = list(command)
        self.commands.append(self.command)
        output = Path(self.command[self.command.index("--output") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake wav")
        self.stdout = []

    def wait(self):
        return 0


root = tk.Tk()
root.withdraw()
old_ask = batch_tab.messagebox.askyesno
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    audio_dir = project / "WAV ORIGINAIS"
    text_dir = project / "TXT TEXTO PORTUGUES"
    for relative in (Path("grupo_a") / "cena.wav", Path("grupo_b") / "cena.wav"):
        make_wav(audio_dir / relative)
        text = text_dir / relative.with_suffix(".txt")
        text.parent.mkdir(parents=True, exist_ok=True)
        text.write_text(f"Texto de {relative.parent.name}", encoding="utf-8")

    try:
        batch_tab.messagebox.askyesno = lambda *args, **kwargs: True
        batch_tab.configure_project_root(project)
        review_tab.configure_project_root(project)
        app = batch_tab.BatchApp(root, embedded=False)
        for _ in range(30):
            root.update()
            time.sleep(0.01)

        expected = ["grupo_a/cena", "grupo_b/cena"]
        assert app.stems == expected, app.stems
        assert sorted(app.audio_by_stem) == expected
        assert sorted(app.text_by_stem) == expected
        assert batch_tab.relative_scene_key(audio_dir / "grupo_a" / "cena.wav", audio_dir) == "grupo_a/cena"
        assert app.scene_playback_path("grupo_a/cena") == audio_dir / "grupo_a" / "cena.wav"
        assert app.scene_playback_path("grupo_b/cena") == audio_dir / "grupo_b" / "cena.wav"
        batch_rows = list(app.queue_list.get(0, "end"))
        assert batch_rows == ["[ ] cena.wav", "[ ] cena.wav"], batch_rows
        assert len(app.main_pane.panes()) == 2

        output_a = batch_tab.OUTPUT_DIR / "grupo_a" / "cena.wav"
        output_b = batch_tab.OUTPUT_DIR / "grupo_b" / "cena.wav"
        assert output_a.parent != output_b.parent
        app.infer_prefix = ["omnivoice-infer"]
        app.selected_model = "edwixx/omnivoice-brpt-v15"
        app.selected_mode = "clone"
        command = app.build_infer_command("grupo_a/cena", "Texto", output_a)
        assert str(audio_dir / "grupo_a" / "cena.wav") in command
        assert str(output_a) in command

        review_audio = review_tab.scene_audio_files()
        review_text = review_tab.scene_text_files()
        assert sorted(review_audio) == expected
        assert sorted(review_text) == expected
        review = review_tab.ReviewApp(root, embedded=False)
        assert review.stems == expected
        assert review.current_output("grupo_a/cena") == project / "dublado" / "grupo_a" / "cena.wav"
        assert review.current_output("grupo_b/cena") == project / "dublado" / "grupo_b" / "cena.wav"
        review_rows = list(review.scene_list.get(0, "end"))
        assert review_rows == ["[ ] cena.wav", "[ ] cena.wav"], review_rows
        assert len(review.main_pane.panes()) == 2
        assert review.review_audio("grupo_a/cena") == audio_dir / "grupo_a" / "cena.wav"
        review.original_unlocked = True
        review.original_text_box.delete("1.0", "end")
        review.original_text_box.insert("1.0", "Texto original do grupo A")
        assert review.save_original_text()
        assert (project / "TXT TEXTO ORIGINAL" / "grupo_a" / "cena.txt").is_file()
        review.transcribed_unlocked = True
        review.transcribed_text_box.delete("1.0", "end")
        review.transcribed_text_box.insert("1.0", "Texto transcrito do grupo A")
        assert review.save_transcribed_text()
        assert (project / "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO" / "grupo_a" / "cena.txt").is_file()
        dubbed_a = project / "dublado" / "grupo_a" / "cena.wav"
        dubbed_a.parent.mkdir(parents=True, exist_ok=True)
        make_wav(dubbed_a)
        player = AudioPlayerManager(root, project)
        assert player._find_original_audio(dubbed_a) == audio_dir / "grupo_a" / "cena.wav"
        assert player._find_dubbed_audio(audio_dir / "grupo_a" / "cena.wav") == dubbed_a

        old_popen = batch_tab.subprocess.Popen
        try:
            batch_tab.subprocess.Popen = FakePopen
            app.run_stems = expected
            app.force_overwrite = True
            app.cancel_requested = False
            app.stop_after_current = False
            app.pause_event.set()
            app.infer_prefix = ["omnivoice-infer"]
            app.selected_model = "edwixx/omnivoice-brpt-v15"
            app.selected_mode = "clone"
            app.worker()
        finally:
            batch_tab.subprocess.Popen = old_popen
        output_a = project / "dublado" / "grupo_a" / "cena.wav"
        output_b = project / "dublado" / "grupo_b" / "cena.wav"
        assert output_a.is_file() and output_b.is_file()
        assert len(FakePopen.commands) == 2
        command_outputs = {Path(command[command.index("--output") + 1]) for command in FakePopen.commands}
        assert len(command_outputs) == 2
        assert {path.parent for path in command_outputs} == {output_a.parent, output_b.parent}
        assert all(path.name.startswith(".cena.__dublaskizon_tmp_") and path.suffix == ".wav" for path in command_outputs)
        root.update()
    finally:
        batch_tab.messagebox.askyesno = old_ask
        root.destroy()

print("nested_project_hierarchy_ok")
