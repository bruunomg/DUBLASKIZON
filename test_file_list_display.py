import tempfile
from pathlib import Path
import tkinter as tk

from wem_filter_tab import WemFilterApp

root = tk.Tk()
root.geometry("1200x800")
root.update_idletasks()
base = Path(tempfile.mkdtemp(prefix="dublaskizon-file-list-"))
source = base / "origem"
source.mkdir()
files = [source / "subpasta" / "fala (123).json", source / "evento#456.bnk"]
files[0].parent.mkdir()
for path in files:
    path.write_text("x", encoding="utf-8")

app = WemFilterApp(root, embedded=False, project_root=base)
app.set_files(files, "Itens arrastados")
shown = [app.file_list.get(index) for index in range(app.file_list.size())]
assert shown == ["evento#456.bnk", "fala (123).json"]
assert Path(app.source_var.get()) == source.resolve()
assert all("/" not in value and "\\" not in value for value in shown)
root.destroy()
print("file_list_display_ok")
