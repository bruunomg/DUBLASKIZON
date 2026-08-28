import tempfile
from pathlib import Path
import tkinter as tk

import wem_filter_tab
from wem_filter_tab import WemFilterApp

root = tk.Tk()
root.withdraw()
base = Path(tempfile.mkdtemp(prefix="dublaskizon-conversion-map-treated-"))
source = base / "arquivos"
source.mkdir()
files = [
    source / "fala (123).wem",
    source / "evento#456.dat",
    source / "789_convertido_A1B2.bin",
]
for path in files:
    path.write_bytes(b"x")

app = WemFilterApp(root, embedded=False, project_root=base)
app.set_files(files, str(source))
messages = []
wem_filter_tab.messagebox.showinfo = lambda *args, **kwargs: messages.append(args)
assert app.generate_conversion_map_txt() is True
output = source / "ConversionMap.txt"
assert output.exists()
assert output.read_text(encoding="utf-8") == "789\n456\n123\n"
assert not (source / "ConversionMap_sem_tratado.txt").exists()
assert any("ID(s) tratados" in str(args) for args in messages)
root.destroy()
print("conversion_map_treated_ok")
