from pathlib import Path
import tkinter as tk

import review_tab


def main():
    root = tk.Tk()
    root.withdraw()
    audio_window = tk.Toplevel(root)
    audio_window.title("OUVIR CENA")
    audio_window.update_idletasks()

    app = review_tab.ReviewApp.__new__(review_tab.ReviewApp)
    app.root = root
    app.status_var = tk.StringVar(master=root)
    app.current_stem = lambda: "CAP01/cena_001"
    records = []
    app.update_record = lambda *args: records.append(args)
    captured = {}
    original_askstring = review_tab.simpledialog.askstring

    def fake_askstring(title, prompt, parent=None):
        captured.update(title=title, prompt=prompt, parent=parent)
        return "motivo de teste"

    review_tab.simpledialog.askstring = fake_askstring
    try:
        app.reject_scene(dialog_parent=audio_window)
        assert captured["parent"] is audio_window
        assert records == [("CAP01/cena_001", "rejeitada", "motivo de teste")]
        assert audio_window.winfo_exists()
    finally:
        review_tab.simpledialog.askstring = original_askstring
        audio_window.destroy()
        root.destroy()

    print("audio_player_reject_focus_ok")


if __name__ == "__main__":
    main()
