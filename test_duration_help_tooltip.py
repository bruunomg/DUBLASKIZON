import tempfile
from pathlib import Path
import tkinter as tk

import duration_converter_tab
import i18n

root = tk.Tk()
root.geometry('1500x900')
root.deiconify()
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    duration_converter_tab.configure_project_root(project)
    app = duration_converter_tab.DurationConverterApp(root, embedded=False, project_root=project)
    root.update_idletasks()
    assert app.duration_help_button.winfo_exists()
    assert app.duration_help_button.cget('text') == '?'
    assert app.convert_button.winfo_exists()
    assert abs(app.duration_help_button.winfo_rootx() - (app.convert_button.winfo_rootx() - app.duration_help_button.winfo_width() - 6)) <= 12
    event = type('Event', (), {'x_root': app.duration_help_button.winfo_rootx() + 4, 'y_root': app.duration_help_button.winfo_rooty() + 4})()
    app.duration_help_tooltip.show(event)
    root.update_idletasks()
    assert app.duration_help_tooltip.window is not None
    tooltip = app.duration_help_tooltip.window
    assert int(tooltip.winfo_rootx()) < event.x_root
    assert int(tooltip.winfo_rooty()) < event.y_root
    assert 'AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO' in tooltip.winfo_children()[0].cget('text')
    app.duration_help_tooltip.hide()
    assert app.duration_help_tooltip.window is None
    for language in ('en', 'ru', 'es'):
        translated = i18n.tr(duration_converter_tab.DURATION_FOLDERS_HELP_TEXT, language)
        assert translated != duration_converter_tab.DURATION_FOLDERS_HELP_TEXT
        assert 'AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO' in translated
root.destroy()
print('duration_help_tooltip_ok')
