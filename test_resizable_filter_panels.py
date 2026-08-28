import tkinter as tk
from pathlib import Path
from tempfile import TemporaryDirectory

from wem_filter_tab import WemFilterApp

with TemporaryDirectory() as folder:
    root = tk.Tk()
    root.geometry("1200x800")
    root.update_idletasks()
    app = WemFilterApp(root, embedded=False, project_root=Path(folder))
    root.update_idletasks()
    assert len(app.panel_split.panes()) == 2
    before = app.panel_split.sashpos(0)
    app.panel_split.sashpos(0, max(20, before + 80))
    root.update_idletasks()
    after = app.panel_split.sashpos(0)
    assert after != before, (before, after)
    root.destroy()

print("resizable_filter_panels_ok")
