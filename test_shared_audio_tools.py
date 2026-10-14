import os
import tempfile
from pathlib import Path
import tkinter as tk

import Dublaskizon

root = tk.Tk()
root.withdraw()
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    (project / "WAV ORIGINAIS").mkdir()
    (project / "TXT TEXTO PORTUGUES").mkdir()
    (project / "WAV ORIGINAIS" / "cena.wav").write_bytes(b"wav")
    (project / "TXT TEXTO PORTUGUES" / "cena.txt").write_text("Texto", encoding="utf-8")
    old_app_dir = Dublaskizon.APP_DIR
    old_config = Dublaskizon.INTERFACE_CONFIG_PATH
    old_env = os.environ.pop("DUBLASKIZON_PROJECT_ROOT", None)
    try:
        Dublaskizon.APP_DIR = project
        Dublaskizon.INTERFACE_CONFIG_PATH = project / "Dublaskizon_interface.json"
        app = Dublaskizon.DublaskizonApp(root)
        duration = app.converter_app
        duration.missing_tools = lambda: []
        original_start = duration.start_dependency_setup
        def fake_start():
            duration.dependencies_running = True
            duration.download_progress.configure(value=37)
        duration.start_dependency_setup = fake_start
        app.prepare_shared_audio_tools()
        assert app.batch_app.dependencies_running is True
        assert float(app.batch_app.download_progress.cget("value")) == 37.0
        duration.dependencies_running = False
        app.sync_shared_tool_progress()
        assert app.batch_app.dependencies_running is False
        assert float(app.batch_app.download_progress.cget("value")) == 100.0
        assert app.batch_app.dependencies_button.cget("state") == "normal"
        duration.start_dependency_setup = original_start
    finally:
        Dublaskizon.APP_DIR = old_app_dir
        Dublaskizon.INTERFACE_CONFIG_PATH = old_config
        if old_env is not None:
            os.environ["DUBLASKIZON_PROJECT_ROOT"] = old_env
root.destroy()
print("shared_audio_tools_ok")
