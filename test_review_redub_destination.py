from pathlib import Path
from types import SimpleNamespace
import tempfile

import review_tab


class Root:
    def __init__(self):
        self.callbacks = []

    def after(self, _delay, callback):
        self.callbacks.append(callback)
        return None


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    review_tab.configure_project_root(project)
    target = project / "dublado" / "CAP01" / "cena.wav"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old-dubbed")
    reference = project / "WAV ORIGINAIS" / "CAP01" / "cena.wav"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"reference")

    root = Root()
    app = review_tab.ReviewApp.__new__(review_tab.ReviewApp)
    app.root = root
    app.config = {"model": "model", "language": "pt", "instruct": "portuguese accent"}
    old_find = review_tab.find_omnivoice_command
    old_run = review_tab.subprocess.run
    review_tab.find_omnivoice_command = lambda: ["omnivoice"]

    def fake_run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        output.write_bytes(b"new-dubbed")
        return SimpleNamespace(returncode=0, stdout="ok")

    review_tab.subprocess.run = fake_run
    try:
        review_tab.ReviewApp._run_generation(app, "CAP01/cena", "texto", target, target, reference, "unchanged")
    finally:
        review_tab.find_omnivoice_command = old_find
        review_tab.subprocess.run = old_run

    backup = project / "revisoes" / "CAP01" / "cena_v01.wav"
    assert target.read_bytes() == b"new-dubbed"
    assert backup.read_bytes() == b"old-dubbed"
    assert not any(path.name.startswith(".cena.__dublaskizon_tmp_") for path in target.parent.iterdir())
    assert len(root.callbacks) == 1

    fresh_target = project / "dublado" / "CAP01" / "nova.wav"
    fresh_reference = project / "WAV ORIGINAIS" / "CAP01" / "nova.wav"
    fresh_reference.write_bytes(b"reference")
    root = Root()
    app.root = root
    review_tab.find_omnivoice_command = lambda: ["omnivoice"]
    review_tab.subprocess.run = fake_run
    try:
        review_tab.ReviewApp._run_generation(app, "CAP01/nova", "texto", fresh_target, fresh_target, fresh_reference, "unchanged")
    finally:
        review_tab.find_omnivoice_command = old_find
        review_tab.subprocess.run = old_run
    assert fresh_target.read_bytes() == b"new-dubbed"
    assert not (project / "revisoes" / "CAP01" / "nova_v01.wav").exists()

print("review_redub_destination_ok")
