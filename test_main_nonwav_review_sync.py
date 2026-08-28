import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
import tkinter as tk

import Dublaskizon
import batch_tab


if shutil.which("ffmpeg") is None:
    raise SystemExit("ffmpeg_not_available")

root = tk.Tk()
root.withdraw()
old_ask = batch_tab.messagebox.askyesno
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    audio_dir = project / "WAV ORIGINAIS"
    text_dir = project / "TXT TEXTO PORTUGUES"
    audio_dir.mkdir()
    text_dir.mkdir()
    source = audio_dir / "cena_revisao.mp3"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=0.15", str(source)], check=True)
    (text_dir / "cena_revisao.txt").write_text("Texto", encoding="utf-8")
    old_app_dir = Dublaskizon.APP_DIR
    old_config = Dublaskizon.INTERFACE_CONFIG_PATH
    old_env = os.environ.pop("DUBLASKIZON_PROJECT_ROOT", None)
    try:
        batch_tab.messagebox.askyesno = lambda *args, **kwargs: True
        Dublaskizon.APP_DIR = project
        Dublaskizon.INTERFACE_CONFIG_PATH = project / "Dublaskizon_interface.json"
        app = Dublaskizon.DublaskizonApp(root)
        for _ in range(150):
            root.update()
            if (audio_dir / "cena_revisao.wav").is_file():
                break
            time.sleep(0.01)
        root.update_idletasks()
        assert (audio_dir / "cena_revisao.wav").is_file()
        assert (audio_dir / "mp3" / "cena_revisao.mp3").is_file()
        assert app.batch_app.stems == ["cena_revisao"]
        assert sorted(app.review_app.audio_by_stem) == ["cena_revisao"]
        assert app.review_app.audio_by_stem["cena_revisao"].name == "cena_revisao.wav"
    finally:
        Dublaskizon.APP_DIR = old_app_dir
        Dublaskizon.INTERFACE_CONFIG_PATH = old_config
        if old_env is not None:
            os.environ["DUBLASKIZON_PROJECT_ROOT"] = old_env
        batch_tab.messagebox.askyesno = old_ask
root.destroy()
print("main_nonwav_review_sync_ok")
