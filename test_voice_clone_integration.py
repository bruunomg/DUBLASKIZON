import os
import tempfile
from pathlib import Path
import tkinter as tk

import Dublaskizon

root = tk.Tk()
root.geometry('1600x1000')
root.deiconify()
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder) / 'projeto'
    project.mkdir()
    old_app_dir = Dublaskizon.APP_DIR
    old_config = Dublaskizon.INTERFACE_CONFIG_PATH
    old_env = os.environ.get('DUBLASKIZON_PROJECT_ROOT')
    try:
        Dublaskizon.APP_DIR = project
        Dublaskizon.INTERFACE_CONFIG_PATH = project / 'Dublaskizon_interface.json'
        os.environ['DUBLASKIZON_PROJECT_ROOT'] = str(project)
        app = Dublaskizon.DublaskizonApp(root)
        root.update_idletasks()
        assert app.voice_clone_scroll is not None
        assert app.voice_clone_app is not None
        assert app.voice_clone_tab_button.winfo_exists()
        assert app.voice_clone_app.output_dir_var.get() == str(project / 'REDIMENSIONAR ÁUDIO PARA CLONAR')
        assert app.voice_clone_app.output_dir_var.get().lower().endswith('redimensionar áudio para clonar')
        tab_buttons = [app.clone_tab_button, app.review_tab_button, app.converter_tab_button, app.voice_clone_tab_button]
        heights = [button.winfo_height() for button in tab_buttons]
        widths = [button.winfo_width() for button in tab_buttons]
        assert len(set(heights)) == 1, heights
        assert len(set(widths)) == 1, widths
        assert app.voice_clone_tab_button.cget('height') == 2
        assert int(app.voice_clone_tab_button.cget('wraplength')) > 0
        assert '8' in str(app.voice_clone_tab_button.cget('font'))
        app.apply_scale(80, resize_window=False, save=False)
        root.update_idletasks()
        scaled_buttons = [app.clone_tab_button, app.review_tab_button, app.converter_tab_button, app.voice_clone_tab_button]
        assert len({button.winfo_width() for button in scaled_buttons}) == 1
        assert len({button.winfo_height() for button in scaled_buttons}) == 1
        assert app.voice_clone_tab_button.cget('height') == 2
        app.apply_scale(100, resize_window=False, save=False)
        app.select_tab(app.voice_clone_scroll)
        assert app.current_tab_key() == 'voice_clone'
        assert app.active_scroll is app.voice_clone_scroll
        app.apply_language('en', save=False)
        assert app.voice_clone_tab_button.cget('text') == 'RESIZE AUDIO FOR CLONING'
        app.apply_theme()
        app.select_tab(app.clone_scroll)
        assert app.current_tab_key() == 'clone'
    finally:
        Dublaskizon.APP_DIR = old_app_dir
        Dublaskizon.INTERFACE_CONFIG_PATH = old_config
        if old_env is None:
            os.environ.pop('DUBLASKIZON_PROJECT_ROOT', None)
        else:
            os.environ['DUBLASKIZON_PROJECT_ROOT'] = old_env
root.destroy()
print('voice_clone_integration_ok')
