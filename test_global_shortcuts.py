from types import SimpleNamespace

import tkinter as tk

import Dublaskizon


root = tk.Tk()
root.withdraw()
app = object.__new__(Dublaskizon.DublaskizonApp)
app.root = root
app._install_global_shortcuts()
assert root.bind_all("<Control-KeyPress-a>")
assert root.bind_all("<Control-KeyPress-f>")

entry = tk.Entry(root)
entry.insert(0, "texto selecionÃ¡vel")
app._shortcut_select_all(SimpleNamespace(widget=entry))
assert entry.selection_get() == "texto selecionÃ¡vel"

text = tk.Text(root, height=3, width=40)
text.insert("1.0", "primeiro trecho\nsegundo trecho")
app._shortcut_select_all(SimpleNamespace(widget=text))
assert text.get("sel.first", "sel.last") == "primeiro trecho\nsegundo trecho"

listbox = tk.Listbox(root)
listbox.insert("end", "cena_001.wav", "cena_002.wav", "cena_003.wav")
app._shortcut_select_all(SimpleNamespace(widget=listbox))
assert listbox.curselection() == (0, 1, 2)

entry.pack();text.pack();listbox.pack();root.deiconify();root.update()
app.current_theme = lambda: {}
try:
    app._shortcut_find(SimpleNamespace(widget=text))
    app.find_panel.query.set("segundo")
    app.find_panel.move(1)
    assert text.get("ctrl_f_match.first", "ctrl_f_match.last") == "segundo"
    app._shortcut_find(SimpleNamespace(widget=listbox))
    app.find_panel.query.set("002")
    app.find_panel.move(1)
    assert listbox.curselection() == (1,)
finally:
    app.find_panel.close()
    root.destroy()
print("global_shortcuts_ok")
