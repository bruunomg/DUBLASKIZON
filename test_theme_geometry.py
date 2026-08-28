import os
import tempfile
import tkinter as tk
from pathlib import Path

project = Path(tempfile.mkdtemp(prefix="dublaskizon-theme-geometry-"))
os.environ["DUBLASKIZON_PROJECT_ROOT"] = str(project)

import Dublaskizon

root = tk.Tk()
root.withdraw()
app = Dublaskizon.DublaskizonApp(root)
app.select_tab(app.wem_filter_scroll)
root.update_idletasks()

tracked = [
    app.wem_filter_scroll,
    app.wem_filter_frame,
    app.wem_filter_app.process_all_button,
    app.wem_filter_app.file_list,
    app.wem_filter_app.preview_tree,
]
initial_geometry = {str(widget): widget.winfo_geometry() for widget in tracked}
assert app.current_tab_key() == "wem_filter"

# A ajuda é o caso mais sensível: seus marcadores não podem ser destruídos/recriados.
app.help_manager.activate()
root.update_idletasks()
marker_ids = tuple(id(marker) for marker in app.help_manager.markers)
center_geometry = app.help_manager.center_window.winfo_geometry()

for expected_theme in ("medio", "claro", "escuro"):
    app.theme_mode = expected_theme
    app.apply_theme()
    root.update_idletasks()
    assert app.current_tab_key() == "wem_filter"
    current_geometry = {str(widget): widget.winfo_geometry() for widget in tracked}
    if current_geometry != initial_geometry:
        print("geometry_delta", expected_theme, {key: (initial_geometry[key], value) for key, value in current_geometry.items() if initial_geometry[key] != value})
    assert current_geometry == initial_geometry
    assert app.help_manager.center_window.winfo_geometry() == center_geometry
    assert tuple(id(marker) for marker in app.help_manager.markers) == marker_ids

app.help_manager.close()
root.destroy()
print("theme_geometry_stable_ok")
