"""One selection counter shared by all application lists, without polling files."""
from __future__ import annotations
import tkinter as tk


def install_selection_status(root, parent):
    label = tk.Label(parent, text='Selecionados: 0', font=('Segoe UI', 9, 'bold'),
                     bg='#334155', fg='#FFFFFF', padx=10)
    label.pack(side='right', padx=6)

    def refresh(widget):
        try:
            kind = widget.winfo_class()
            if kind == 'Listbox':
                count = len(widget.curselection())
            elif kind == 'Treeview':
                count = len(widget.selection())
            else:
                return
            label.configure(text=f'Selecionados nesta lista: {count}')
        except (tk.TclError, AttributeError):
            pass  # A dialog may have closed before the deferred update.

    def selected(event):
        root.after_idle(lambda: refresh(event.widget))

    def mapped(event):
        widget = event.widget
        try:
            if widget.winfo_class() == 'Listbox':
                widget.configure(selectmode='extended', exportselection=False)
            elif widget.winfo_class() == 'Treeview':
                widget.configure(selectmode='extended')
        except (tk.TclError, AttributeError):
            pass

    root.bind_all('<Map>', mapped, add='+')
    for sequence in ('<<ListboxSelect>>', '<<TreeviewSelect>>', '<ButtonRelease-1>',
                     '<KeyRelease>', '<FocusIn>'):
        root.bind_all(sequence, selected, add='+')
    return label
