import os
import tempfile
from pathlib import Path
import tkinter as tk

project = Path(tempfile.mkdtemp(prefix="dublaskizon-wem-filter-"))
os.environ["DUBLASKIZON_PROJECT_ROOT"] = str(project)

import Dublaskizon
from wem_filter_tab import WemFilterApp, RULE_CHOICES, parse_wwise_name_id_map


source = project / "arquivos"
source.mkdir()
files = [
    source / "fala (123).wem",
    source / "evento#456.dat",
    source / "789_convertido_A1B2C3.bin",
    source / "pacote.created.bnk",
]
for path in files:
    path.write_bytes(b"dados")

root = tk.Tk()
root.withdraw()
filter_app = WemFilterApp(root, embedded=False, project_root=project)
filter_app.set_files(files, str(source))
filter_app.generate_preview()
assert len(filter_app.plan) == 4
preview_by_source = {item.source.name: item for item in filter_app.plan}
assert preview_by_source["fala (123).wem"].target.name == "123.wem"
assert preview_by_source["evento#456.dat"].target.name == "456.dat"
assert preview_by_source["789_convertido_A1B2C3.bin"].target.name == "789.bin"
assert preview_by_source["pacote.created.bnk"].target.name == "pacote.bnk"
assert all(item.status == "OK" for item in filter_app.plan)

# Verifica mapa Name -> ID derivado do padrão Wwise.
map_path = project / "Dialog_Narration.txt"
map_path.write_text("Streamed Audio\nID\tName\n\t900\tMinha fala\n", encoding="utf-8")
assert parse_wwise_name_id_map(map_path)["minhafala"] == "900"

# Verifica conflitos sem tocar nos arquivos.
conflict_a = source / "alpha (1).wem"
conflict_b = source / "beta (1).wem"
conflict_a.write_bytes(b"a")
conflict_b.write_bytes(b"b")
filter_app.set_files([conflict_a, conflict_b], str(source))
assert sum(item.status == "CONFLITO" for item in filter_app.plan) == 2
assert conflict_a.exists() and conflict_b.exists()

# Verifica renomeação segura e reversível, sem confirmação modal.
filter_app.set_files(files[:2], str(source))
filter_app.generate_preview()
changes = [(item.source, item.target) for item in filter_app.plan if item.status == "OK"]
filter_app._execute_safe(changes)
assert (source / "123.wem").exists() and (source / "456.dat").exists()
filter_app._execute_safe([(target, original) for original, target in changes])
assert files[0].exists() and files[1].exists()

# Verifica a integração da aba na aplicação principal.
main_app = Dublaskizon.DublaskizonApp(root)
root.update_idletasks()
assert main_app.wem_filter_app is not None
assert main_app.wem_filter_scroll is not None
assert "FILTRO" in main_app.wem_filter_tab_button.cget("text")
main_app.theme_mode = "escuro"
main_app.apply_theme()
root.update_idletasks()
assert main_app.wem_filter_app.rename_button.cget("bg")

root.destroy()
print("wem_filter_integration_ok")
