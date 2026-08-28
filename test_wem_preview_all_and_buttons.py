import tempfile
from pathlib import Path
import tkinter as tk

from wem_filter_tab import WemFilterApp

root = tk.Tk()
root.withdraw()
with tempfile.TemporaryDirectory() as folder:
    source = Path(folder)
    first = source / '6232255.wem'
    second = source / '6538337.wem'
    third = source / '6075292.wem'
    for path in (first, second, third):
        path.write_bytes(b'wem')
    app = WemFilterApp(root, embedded=False, project_root=source)
    app.set_files([first, second, third], str(source))
    app.file_list.selection_clear(0, 'end')
    selected_index = app.files.index(second)
    app.file_list.selection_set(selected_index)
    app.generate_preview()
    rows = app.preview_tree.get_children()
    assert len(rows) == 3
    preview_old_names = [app.preview_tree.item(row, 'values')[1] for row in rows]
    assert preview_old_names == sorted([first.name, second.name, third.name])
    row_by_name = {app.preview_tree.item(row, 'values')[1]: row for row in rows}
    assert app.preview_tree.item(row_by_name[first.name], 'values')[2] == first.name
    assert app.preview_tree.item(row_by_name[third.name], 'values')[2] == third.name
    assert app.preview_tree.item(row_by_name[second.name], 'values')[2] == second.name
    assert app.id_minus_ten_button.cget('text') == '−10'
    assert app.id_minus_one_button.cget('text') == '−1'
    assert app.id_plus_one_button.cget('text') == '+1'
    assert app.id_plus_ten_button.cget('text') == '+10'
    app.id_minus_ten_button.invoke()
    assert len(app.preview_tree.get_children()) == 3
    row = lambda: {app.preview_tree.item(item, 'values')[1]: item for item in app.preview_tree.get_children()}[second.name]
    assert app.preview_tree.item(row(), 'values')[2] == '6538327.wem'
    app.id_minus_one_button.invoke()
    assert len(app.preview_tree.get_children()) == 3
    assert app.preview_tree.item(row(), 'values')[2] == '6538326.wem'
    app.id_plus_one_button.invoke()
    assert len(app.preview_tree.get_children()) == 3
    assert app.preview_tree.item(row(), 'values')[2] == '6538327.wem'
    app.id_plus_ten_button.invoke()
    assert len(app.preview_tree.get_children()) == 3
    assert app.preview_tree.item(row(), 'values')[2] == '6538337.wem'
    assert app.preview_title_label.cget('text').startswith('PRÉ-VISUALIZAÇÃO')
root.destroy()
print('wem_preview_all_buttons_ok')
