import os
import tempfile
from pathlib import Path
import tkinter as tk

import Dublaskizon

root = tk.Tk()
root.geometry("1500x950")
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder) / "PROJETO_EXISTENTE"
    (project / "WAV ORIGINAIS" / "CAPITULO 01").mkdir(parents=True)
    (project / "TXT TEXTO PORTUGUES" / "CAPITULO 01").mkdir(parents=True)
    (project / "WAV ORIGINAIS" / "CAPITULO 01" / "cena_001.wav").write_bytes(b"wav")
    (project / "TXT TEXTO PORTUGUES" / "CAPITULO 01" / "cena_001.txt").write_text("Texto da cena", encoding="utf-8")
    (project / "WAV ORIGINAIS" / "cena_002.waw").write_bytes(b"waw")
    (project / "TXT TEXTO PORTUGUES" / "cena_002.txt").write_text("Outro texto", encoding="utf-8")
    old_app_dir = Dublaskizon.APP_DIR
    old_config = Dublaskizon.INTERFACE_CONFIG_PATH
    old_env = os.environ.pop("DUBLASKIZON_PROJECT_ROOT", None)
    try:
        Dublaskizon.APP_DIR = project
        Dublaskizon.INTERFACE_CONFIG_PATH = project / "Dublaskizon_interface.json"
        app = Dublaskizon.DublaskizonApp(root)
        root.update_idletasks()
        assert app.project_root == project.resolve()
        assert sorted(app.batch_app.stems) == ["CAPITULO 01/cena_001", "cena_002"]
        assert app.batch_app.queue_list.size() == 2
        assert "Nenhum par de wav + txt" not in app.batch_app.queue_list.get(0)
        assert app.batch_app.audio_by_stem["CAPITULO 01/cena_001"].parent.name == "CAPITULO 01"
    finally:
        Dublaskizon.APP_DIR = old_app_dir
        Dublaskizon.INTERFACE_CONFIG_PATH = old_config
        if old_env is not None:
            os.environ["DUBLASKIZON_PROJECT_ROOT"] = old_env
root.destroy()
print("batch_initial_discovery_ok")
