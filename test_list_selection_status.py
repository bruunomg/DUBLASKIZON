import tkinter as tk
from tkinter import ttk
import unittest
from list_selection_status import install_selection_status


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        footer = tk.Frame(self.root)
        footer.pack()
        self.label = install_selection_status(self.root, footer)

    def tearDown(self):
        self.root.update_idletasks()
        self.root.destroy()

    def test_list_multiple_selection_and_clear(self):
        widget = tk.Listbox(self.root)
        widget.pack()
        widget.insert('end', 'a', 'b', 'c')
        self.root.update()
        self.assertEqual(widget.cget('selectmode'), 'extended')
        widget.selection_set(0, 1)
        widget.event_generate('<<ListboxSelect>>')
        self.root.update()
        self.assertEqual(self.label.cget('text'), 'Selecionados nesta lista: 2')
        widget.selection_clear(0, 'end')
        widget.event_generate('<<ListboxSelect>>')
        self.root.update()
        self.assertEqual(self.label.cget('text'), 'Selecionados nesta lista: 0')

    def test_tree_selection_count(self):
        widget = ttk.Treeview(self.root)
        widget.pack()
        for key in ('a', 'b', 'c'):
            widget.insert('', 'end', iid=key)
        self.root.update()
        widget.selection_set('a', 'c')
        self.root.update()
        self.assertEqual(self.label.cget('text'), 'Selecionados nesta lista: 2')
