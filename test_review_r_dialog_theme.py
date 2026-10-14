import tkinter as tk
from tkinter import ttk

import review_tab
from review_tab import ReviewApp


root = tk.Tk()
root.withdraw()
review = ReviewApp.__new__(ReviewApp)
review.root = root
review.request_r_var = tk.StringVar(root, value="1")
review.theme = {
    "mode": "escuro",
    "surface": "#2A3546",
    "input": "#35445A",
    "input_text": "#FFFFFF",
    "text": "#F8FAFC",
    "muted": "#CBD5E1",
    "border": "#52627A",
    "select": "#2563EB",
}

original_askyesno = review_tab.messagebox.askyesno
review_tab.messagebox.askyesno = lambda *args, **kwargs: True
observed = {}


def inspect_and_confirm():
    dialogs = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]
    assert len(dialogs) == 1
    dialog = dialogs[0]
    observed["dialog_bg"] = dialog.cget("bg")
    expected_x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
    expected_y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
    assert abs(dialog.winfo_rootx() - expected_x) <= 2
    assert abs(dialog.winfo_rooty() - expected_y) <= 2
    labels = [child for child in dialog.winfo_children() if child.winfo_class() == "Label"]
    assert labels and labels[0].cget("bg") == "#2A3546"
    combo = next(child for child in dialog.winfo_children() if isinstance(child, ttk.Combobox))
    observed["combo_style"] = combo.cget("style")
    assert observed["combo_style"] == "PronunciationR.TCombobox"
    assert dialog.nametowidget(combo.winfo_name()).cget("style") == "PronunciationR.TCombobox"
    button_frame = next(child for child in dialog.winfo_children() if child.winfo_class() == "Frame")
    buttons = [child for child in button_frame.winfo_children() if child.winfo_class() == "Button"]
    assert {button.cget("text") for button in buttons} == {"OK", "CANCELAR"}
    assert all(button.cget("bg") != "#FFFFFF" for button in buttons)
    combo.current(1)
    next(button for button in buttons if button.cget("text") == "OK").invoke()


try:
    root.after(50, inspect_and_confirm)
    selected = review._choose_r_override(root)
finally:
    review_tab.messagebox.askyesno = original_askyesno
    root.destroy()

assert selected == "soft"
assert observed["dialog_bg"] == "#2A3546"
print("review_r_dialog_theme_ok")
