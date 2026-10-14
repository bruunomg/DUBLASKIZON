import tempfile
from pathlib import Path
import tkinter as tk

import wem_filter_tab
from wem_filter_tab import WemFilterApp

root = tk.Tk()
root.withdraw()
base = Path(tempfile.mkdtemp(prefix="dublaskizon-source-folder-"))
source = base / "pasta_dos_jsons"
source.mkdir()
files = [source / "evento (123).json", source / "fala#456.bnk"]
for path in files:
    path.write_text("{}", encoding="utf-8")

app = WemFilterApp(root, embedded=False, project_root=base)
# Simula arrasto de itens: o rótulo textual não pode virar caminho.
app.set_files(files, "Itens arrastados")
assert app.source_dir == source.resolve()
assert Path(app.source_var.get()) == source.resolve()

wem_filter_tab.messagebox.showinfo = lambda *args, **kwargs: None
assert app.generate_conversion_map_txt() is True
output = source / "ConversionMap.txt"
assert output.exists()
assert output.read_text(encoding="utf-8") == "123\n456\n"
assert app.source_dir.is_dir()
root.destroy()
print("source_folder_resolution_ok")
