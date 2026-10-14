from pathlib import Path
import shutil
import tkinter as tk
import wem_filter_tab
from wem_filter_tab import WemFilterApp

root = tk.Tk()
root.withdraw()
source = Path('/tmp/wem_scope_repro')
if source.exists():
    shutil.rmtree(source)
source.mkdir(parents=True)
for filename in ('6232255.wem', '6538337.wem', '6075292.wem'):
    shutil.copy2(Path('/home/ubuntu/upload') / filename, source / filename)
paths = [source / '6232255.wem', source / '6538337.wem', source / '6075292.wem']
original_bytes = {path.name: path.read_bytes() for path in paths}
original_names = {path.name for path in paths}
app = WemFilterApp(root, embedded=False, project_root=source)
app.set_files([paths[0]], str(source))
for amount in (1, 10, -1, -10, 10):
    app.apply_id_offset(amount)
    assert {item.source.name for item in app.plan} == {'6232255.wem'}
    assert len(app.plan) == 1
old_ask = wem_filter_tab.messagebox.askyesno
old_info = wem_filter_tab.messagebox.showinfo
try:
    wem_filter_tab.messagebox.askyesno = lambda *args, **kwargs: True
    wem_filter_tab.messagebox.showinfo = lambda *args, **kwargs: None
    app.rename_files()
finally:
    wem_filter_tab.messagebox.askyesno = old_ask
    wem_filter_tab.messagebox.showinfo = old_info
renamed = source / '6232265.wem'
assert renamed.exists(), sorted(path.name for path in source.iterdir())
assert (source / '6538337.wem').exists()
assert (source / '6075292.wem').exists()
assert (source / '6538337.wem').read_bytes() == original_bytes['6538337.wem']
assert (source / '6075292.wem').read_bytes() == original_bytes['6075292.wem']
root.destroy()
print('wem_attached_scope_ok')
