import shutil
from pathlib import Path
import tkinter as tk

import wem_filter_tab
from wem_filter_tab import WemFilterApp

source = Path('/tmp/wem_drag_single_scope')
if source.exists():
    shutil.rmtree(source)
source.mkdir(parents=True)
paths = [source / '6232255.wem', source / '6538337.wem', source / '6075292.wem']
for path in paths:
    path.write_bytes(path.name.encode('ascii'))
original = {path.name: path.read_bytes() for path in paths}
root = tk.Tk()
root.withdraw()
app = WemFilterApp(root, embedded=False, project_root=source)
app.handle_drop(str(paths[0]))
assert [path.name for path in app.files] == ['6232255.wem']
assert app.selected_only_var.get() == '1'
assert tuple(app.file_list.curselection()) == (0,)
for amount in (1, 10, -1, -10, 10):
    app.apply_id_offset(amount)
    assert len(app.plan) == 1
    assert app.plan[0].source.name == '6232255.wem'
old_ask = wem_filter_tab.messagebox.askyesno
old_info = wem_filter_tab.messagebox.showinfo
try:
    wem_filter_tab.messagebox.askyesno = lambda *args, **kwargs: True
    wem_filter_tab.messagebox.showinfo = lambda *args, **kwargs: None
    app.rename_files()
finally:
    wem_filter_tab.messagebox.askyesno = old_ask
    wem_filter_tab.messagebox.showinfo = old_info
assert (source / '6232265.wem').exists()
for other in paths[1:]:
    assert other.exists() and other.read_bytes() == original[other.name]
root.destroy()
print('wem_drag_single_scope_ok')
