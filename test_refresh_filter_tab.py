import tempfile
from pathlib import Path
import tkinter as tk

from Dublaskizon import DublaskizonApp

root = tk.Tk()
root.geometry("1500x950")
app = DublaskizonApp(root)
root.update_idletasks()
with tempfile.TemporaryDirectory() as folder:
    source = Path(folder)
    first = source / "fala (123).wem"
    second = source / "evento#456.dat"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    app.select_tab(app.wem_filter_scroll)
    filter_app = app.wem_filter_app
    filter_app.set_files([first, second], str(source))
    app.refresh_screen()
    root.update_idletasks()
    assert app.current_tab_key() == "wem_filter"
    assert app.active_scroll is app.wem_filter_scroll
    assert app.wem_filter_app is filter_app
    assert [path.name for path in filter_app.files] == ["evento#456.dat", "fala (123).wem"]
    assert filter_app.preview_tree.get_children()
    assert app.clone_scroll is not app.active_scroll
root.destroy()
print("refresh_filter_tab_ok")
