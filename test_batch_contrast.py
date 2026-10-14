import tempfile
from pathlib import Path
import tkinter as tk

import batch_tab
from Dublaskizon import THEMES

root = tk.Tk()
root.geometry("1400x900")
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    (project / "WAV ORIGINAIS").mkdir()
    (project / "TXT TEXTO PORTUGUES").mkdir()
    (project / "WAV ORIGINAIS" / "cena_001.wav").write_bytes(b"wav")
    (project / "TXT TEXTO PORTUGUES" / "cena_001.txt").write_text("texto", encoding="utf-8")
    batch_tab.configure_project_root(project)
    app = batch_tab.BatchApp(root, embedded=False)
    old_executable_path = batch_tab.executable_path
    try:
        batch_tab.executable_path = lambda name, project_root: None
        app.start_tool_alert()
        root.update_idletasks()
        assert app.dependencies_button.cget("state") == "normal"
        assert "Faltam ferramentas" in app.status_var.get()
        assert app.tool_alert_after_id is not None
    finally:
        batch_tab.executable_path = old_executable_path
        app.stop_tool_alert()
    for mode in ("medio", "escuro"):
        app.apply_theme(THEMES[mode])
        root.update_idletasks()
        assert app.queue_list.cget("fg").lower() == "#ffffff"
        assert app.queue_list.itemcget(0, "foreground").lower() == "#ffffff"
        assert app.queue_list.cget("selectforeground").lower() == "#ffffff"
        assert app.log_box.cget("fg").lower() == "#ffffff"
        assert app.log_box.tag_cget("normal", "foreground").lower() == "#ffffff"
        assert app.log_box.tag_cget("info", "foreground").lower() == "#93c5fd"
        assert app.log_box.tag_cget("error", "foreground").lower() == "#fca5a5"
root.destroy()
print("batch_contrast_ok")
