import tempfile
from pathlib import Path
import tkinter as tk

from wem_filter_tab import WemFilterApp, RULE_CHOICES

root = tk.Tk()
root.geometry("1200x800")
root.update_idletasks()
with tempfile.TemporaryDirectory() as folder:
    app = WemFilterApp(root, embedded=False, project_root=Path(folder))
    app.name_id_map = {"falateste": "900"}
    app.pcvr_to_standalone = {"100": "200"}
    app.loaded_map_files = [Path(folder) / "map.txt"]
    app.use_map_var.set("1")
    app.rule_var.set(RULE_CHOICES[1])
    app.clear_mapping()
    assert app.name_id_map == {}
    assert app.pcvr_to_standalone == {}
    assert app.loaded_map_files == []
    assert app.use_map_var.get() == "0"
    assert "apenas regras internas" in app.map_var.get()
    assert "Mapa Wwise limpo" in app.status_var.get()
root.destroy()
print("clear_mapping_ok")
