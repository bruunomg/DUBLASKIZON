import queue
import time
import tkinter as tk

import batch_tab
import duration_converter_tab
import format_converter_tab
import review_tab
import voice_clone_tab
import wem_filter_tab
from Dublaskizon import DublaskizonApp, TerminalApp


received = []
callback = lambda source, text, tag="normal": received.append((source, text, tag))

for cls, source in (
    (batch_tab.BatchApp, "CLONAGEM + DUBLAGEM"),
    (review_tab.ReviewApp, "REVISÃO"),
    (duration_converter_tab.DurationConverterApp, "CONVERTER DURAÇÃO"),
    (format_converter_tab.FormatConverterApp, "CONVERTER FORMATOS"),
    (voice_clone_tab.VoiceClonePreprocessorApp, "REDIMENSIONAR PARA CLONAR"),
    (wem_filter_tab.WemFilterApp, "FILTRO RENOMEAR .WEM"),
):
    app = cls.__new__(cls)
    app.central_log_callback = callback
    app._log_central("processo de teste", "info")
    assert received[-1] == (source, "processo de teste", "info")

app = DublaskizonApp.__new__(DublaskizonApp)
app.central_log_queue = queue.Queue()
app.central_log("CONVERTER FORMATOS", "evento global", "ok")
assert app.central_log_queue.get_nowait() == ("CONVERTER FORMATOS", "evento global", "ok")

root = tk.Tk()
root.withdraw()
parent = tk.Frame(root)
parent.pack()
terminal = TerminalApp(
    parent,
    root,
    {
        "root": "#F5F6FA",
        "surface": "#FFFFFF",
        "text": "#1F2937",
        "muted": "#64748B",
        "input": "#FFFFFF",
        "input_text": "#1F2937",
        "select": "#DBEAFE",
    },
    global_log_queue=queue.Queue(),
)
terminal.global_log_queue.put(("REVISÃO", "Cena aprovada: CAP01/cena", "ok"))
terminal.poll_output()
root.update()
assert "[REVISÃO] Cena aprovada: CAP01/cena" in terminal.global_log_box.get("1.0", "end")
root.destroy()

print("global_process_log_ok")
