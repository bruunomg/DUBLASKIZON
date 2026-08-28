import tempfile
from pathlib import Path
import tkinter as tk

from wem_filter_tab import WemFilterApp

root = tk.Tk()
root.withdraw()
with tempfile.TemporaryDirectory() as folder:
    source = Path(folder)
    path = source / '6232255.wem'
    path.write_bytes(b'wem')
    app = WemFilterApp(root, embedded=False, project_root=source)
    app.set_files([path], str(source))
    for amount, target in ((1, '6232256.wem'), (10, '6232266.wem'), (-1, '6232265.wem'), (-10, '6232255.wem'), (1, '6232256.wem')):
        app.apply_id_offset(amount)
        rows = app.preview_tree.get_children()
        assert len(rows) == 1
        values = app.preview_tree.item(rows[0], 'values')
        assert values[1] == '6232255.wem'
        assert values[2] == target
        assert app.preview_tree.selection() == (rows[0],)
        root.update_idletasks()
root.destroy()
print('wem_preview_incremental_ok')
