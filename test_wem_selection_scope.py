import tempfile
from pathlib import Path
import tkinter as tk

import wem_filter_tab
from wem_filter_tab import WemFilterApp

root = tk.Tk()
root.withdraw()
with tempfile.TemporaryDirectory() as folder:
    source = Path(folder)
    selected = source / "fala (100).wem"
    untouched_a = source / "fala (200).wem"
    untouched_b = source / "outro#300.dat"
    for path in (selected, untouched_a, untouched_b):
        path.write_text(path.name, encoding="utf-8")

    app = WemFilterApp(root, embedded=False, project_root=source)
    app.set_files([selected], str(source))
    app.apply_id_offset(1)
    assert [item.source.name for item in app.plan] == [selected.name]
    assert [item.target.name for item in app.plan] == ["101.wem"]

    old_ask = wem_filter_tab.messagebox.askyesno
    old_info = wem_filter_tab.messagebox.showinfo
    try:
        wem_filter_tab.messagebox.askyesno = lambda *args, **kwargs: True
        wem_filter_tab.messagebox.showinfo = lambda *args, **kwargs: None
        app.rename_files()
        assert (source / "101.wem").exists()
        assert untouched_a.exists() and untouched_b.exists()
        assert len(app.last_changes) == 1
        app.undo_last()
        assert selected.exists()
        assert not (source / "101.wem").exists()
        assert untouched_a.exists() and untouched_b.exists()
        assert app.last_changes == []
    finally:
        wem_filter_tab.messagebox.askyesno = old_ask
        wem_filter_tab.messagebox.showinfo = old_info
root.destroy()
print("wem_selection_scope_ok")
