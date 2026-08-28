import shutil
import subprocess
import tempfile
import time
from pathlib import Path
import tkinter as tk

import batch_tab


if shutil.which("ffmpeg") is None:
    raise SystemExit("ffmpeg_not_available")

root = tk.Tk()
root.withdraw()
old_ask = batch_tab.messagebox.askyesno
old_warning = batch_tab.messagebox.showwarning
old_executable_path = batch_tab.executable_path
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    audio_dir = project / "WAV ORIGINAIS"
    text_dir = project / "TXT TEXTO PORTUGUES"
    audio_dir.mkdir()
    text_dir.mkdir()
    source = audio_dir / "cena_portatil.mp3"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=250:duration=0.15", str(source)], check=True)
    (text_dir / "cena_portatil.txt").write_text("Texto", encoding="utf-8")
    prompts = []
    warnings = []
    ready = False

    def fake_ask(*args, **kwargs):
        prompts.append(args[0] if args else "")
        return True

    def fake_warning(*args, **kwargs):
        warnings.append(args[0] if args else "")

    def fake_executable_path(name, project_root):
        if name == "ffmpeg" and not ready:
            return None
        return old_executable_path(name, project_root)

    try:
        batch_tab.messagebox.askyesno = fake_ask
        batch_tab.messagebox.showwarning = fake_warning
        batch_tab.executable_path = fake_executable_path
        batch_tab.configure_project_root(project)
        app = batch_tab.BatchApp(root, embedded=False)
        for _ in range(100):
            root.update()
            time.sleep(0.01)
        assert prompts == [], "não deve haver confirmação antes de o FFmpeg estar preparado"
        assert app.pending_non_wav_audio and source.is_file()
        assert not (audio_dir / "cena_portatil.wav").exists()
        app.start_run()
        assert warnings and "Converter áudios para WAV" in warnings[-1]

        ready = True
        app.retry_pending_audio_conversion()
        for _ in range(150):
            root.update()
            if (audio_dir / "cena_portatil.wav").is_file():
                break
            time.sleep(0.01)
        assert prompts == ["Converter áudios para WAV"]
        assert (audio_dir / "cena_portatil.wav").is_file()
        assert (audio_dir / "mp3" / "cena_portatil.mp3").is_file()
        assert float(app.audio_conversion_progress.cget("value")) == 100.0
        assert "concluída" in app.audio_conversion_status_var.get().lower()
    finally:
        batch_tab.messagebox.askyesno = old_ask
        batch_tab.messagebox.showwarning = old_warning
        batch_tab.executable_path = old_executable_path
        root.destroy()
print("batch_deferred_conversion_ok")
