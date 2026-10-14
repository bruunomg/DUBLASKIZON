import tkinter as tk
from pathlib import Path
from tempfile import TemporaryDirectory

import i18n
from wem_filter_tab import WemFilterApp

assert i18n.tr("DUBLADOS", "en") == "DUBBED"
assert i18n.tr("REDUBLAR", "ru") == "ПЕРЕДЕЛАТЬ ДУБЛЯЖ"
assert i18n.tr("REDUBLAR COM OUTRO ÁUDIO", "es") == "REDOBLAR CON OTRO AUDIO"
root = tk.Tk()
root.geometry("1400x900")
root.update_idletasks()
with TemporaryDirectory() as folder:
    app = WemFilterApp(root, embedded=False, project_root=Path(folder))
    i18n.set_current_language("en")
    i18n.translate_widget_tree(root, "en")
    app.apply_language("en")
    assert app.process_all_button.cget("text") == "GENERATE ConversionMap.txt"
    assert app.rename_button.cget("text") == "RENAME SAFELY"
    assert not hasattr(app, "preview_button")
    assert i18n.tr("Prévia automática atualizada. Os novos nomes piscam em verde; revise antes de confirmar.", "en").startswith("Automatic preview")
    assert "ConversionMap.txt" in app.process_all_button.cget("text")
    assert app.rule_combo.cget("values")[0].startswith("Smart")
    assert app.preview_tree.heading("status", "text") == "Status"
    i18n.set_current_language("ru")
    i18n.translate_widget_tree(root, "ru")
    app.apply_language("ru")
    assert "ConversionMap.txt" in app.process_all_button.cget("text")
    assert app.rename_button.cget("text") == "БЕЗОПАСНО ПЕРЕИМЕНОВАТЬ"
    assert app.preview_tree.heading("status", "text") == "Состояние"
    i18n.set_current_language("es")
    i18n.translate_widget_tree(root, "es")
    app.apply_language("es")
    assert "ConversionMap.txt" in app.process_all_button.cget("text")
    assert app.rename_button.cget("text") == "RENOMBRAR CON SEGURIDAD"
    assert app.preview_tree.heading("status", "text") == "Estado"

# Verifica que os comandos também têm traduções no catálogo.
assert i18n.tr("COMANDOS DO TERMINAL", "en") == "TERMINAL COMMANDS"
assert i18n.tr("EXECUTAR", "ru") == "ЗАПУСТИТЬ"
assert i18n.tr("LIMPAR", "es") == "LIMPIAR"
root.destroy()
print("i18n_filter_commands_ok")
