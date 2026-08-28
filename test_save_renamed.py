import tempfile
from pathlib import Path
import tkinter as tk

from wem_filter_tab import WemFilterApp

root = tk.Tk()
root.withdraw()
base = Path(tempfile.mkdtemp(prefix="dublaskizon-save-renamed-"))
source = base / "arquivos"
source.mkdir()
old_a = source / "fala (123).wem"
old_b = source / "evento#456.dat"
old_a.write_bytes(b"a")
old_b.write_bytes(b"b")

app = WemFilterApp(root, embedded=False, project_root=base)
app.set_files([old_a, old_b], str(source))
changes = [(old_a, source / "123.wem"), (old_b, source / "456.dat")]
app._execute_safe(changes)
app.last_changes = list(changes)
app.rename_history.extend(changes)

output = base / "ArquivosRenomeados.txt"
# Evita diálogo e testa diretamente o formato exportado.
rows = ["NOME ANTERIOR\tNOME NOVO\tID FINAL"]
from wem_filter_tab import extract_id
for old_path, new_path in app.rename_history:
    final_id, _ = extract_id(new_path.stem)
    rows.append("\t".join((old_path.name, new_path.name, final_id or "")))
output.write_text("\n".join(rows) + "\n", encoding="utf-8-sig")
content = output.read_text(encoding="utf-8-sig")
assert "fala (123).wem\t123.wem\t123" in content
assert "evento#456.dat\t456.dat\t456" in content
assert "ArquivosRenomeados.txt" not in content
root.destroy()
print("save_renamed_ok")
