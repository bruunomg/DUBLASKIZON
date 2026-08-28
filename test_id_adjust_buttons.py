import tempfile
from pathlib import Path
import tkinter as tk

from wem_filter_tab import WemFilterApp, RULE_CHOICES

root = tk.Tk()
root.geometry("1400x900")
root.update_idletasks()
with tempfile.TemporaryDirectory() as folder:
    app = WemFilterApp(root, embedded=False, project_root=Path(folder))
    source = Path(folder)
    files = [source / "fala (123456).json", source / "evento#200.dat"]
    for path in files:
        path.write_text("x", encoding="utf-8")
    app.set_files(files, str(source))
    assert len(RULE_CHOICES) == 5
    assert all("PCVR" not in value and "Standalone" not in value for value in RULE_CHOICES)
    app.apply_id_offset(1)
    assert app.id_offset == 1
    assert [item.target.name for item in app.plan] == ["201.dat", "123457.json"]
    app.apply_id_offset(10)
    assert app.id_offset == 11
    assert [item.target.name for item in app.plan] == ["211.dat", "123467.json"]
    app.apply_id_offset(-1)
    assert app.id_offset == 10
    assert [item.target.name for item in app.plan] == ["210.dat", "123466.json"]
    app.apply_id_offset(-10)
    assert app.id_offset == 0
    assert [item.target.name for item in app.plan] == ["200.dat", "123456.json"]
    assert [app.id_minus_ten_button.cget("text"), app.id_minus_one_button.cget("text"), app.id_plus_one_button.cget("text"), app.id_plus_ten_button.cget("text")] == ["−10", "−1", "+1", "+10"]
    assert app.id_minus_ten_button.cget("bg") == app.id_minus_one_button.cget("bg")
    assert app.id_plus_one_button.cget("bg") == app.id_plus_ten_button.cget("bg")
    assert app.id_minus_ten_button.cget("bg") != app.id_plus_one_button.cget("bg")
    app.clear_files()
root.destroy()
print("id_adjust_buttons_ok")
