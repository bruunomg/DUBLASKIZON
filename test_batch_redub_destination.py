from pathlib import Path
import os
import queue
import tempfile
import threading

import batch_tab


class FakeProcess:
    def __init__(self, *_args, **_kwargs):
        self.stdout = iter(())
        self.returncode = 0

    def wait(self):
        output_arg = fake_command_output[0]
        Path(output_arg).write_bytes(b"new-from-batch")
        return 0


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    batch_tab.configure_project_root(project)
    output = project / "dublado" / "CAP01" / "cena.wav"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"old-from-batch")
    reference = project / "WAV ORIGINAIS" / "CAP01" / "cena.wav"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"reference")
    text = project / "TXT TEXTO PORTUGUES" / "CAP01" / "cena.txt"
    text.parent.mkdir(parents=True)
    text.write_text("texto", encoding="utf-8")

    fake_command_output = [""]
    old_popen = batch_tab.subprocess.Popen
    batch_tab.subprocess.Popen = lambda *args, **kwargs: FakeProcess(*args, **kwargs)
    try:
        app = batch_tab.BatchApp.__new__(batch_tab.BatchApp)
        app.run_stems = ["CAP01/cena"]
        app.stems = ["CAP01/cena"]
        app.audio_by_stem = {"CAP01/cena": reference}
        app.text_by_stem = {"CAP01/cena": text}
        app.pause_event = threading.Event()
        app.pause_event.set()
        app.cancel_requested = False
        app.stop_after_current = False
        app.force_overwrite = True
        app.selected_mode = "clone"
        app.current_process = None
        app.message_queue = queue.Queue()
        app.logs = []
        app.emit_log = lambda value, tag="normal": app.logs.append((value, tag))
        app.build_infer_command = lambda _stem, _text, output_path: (fake_command_output.__setitem__(0, str(output_path)) or ["omnivoice", "--output", str(output_path)])
        app.omnivoice_environment = lambda: os.environ.copy()
        batch_tab.BatchApp.worker(app)
    finally:
        batch_tab.subprocess.Popen = old_popen

    backup = project / "revisoes" / "CAP01" / "cena_v01.wav"
    assert output.read_bytes() == b"new-from-batch"
    assert backup.read_bytes() == b"old-from-batch"
    assert any("Versão anterior preservada" in value for value, _tag in app.logs)
    assert not any(path.name.startswith(".cena.__dublaskizon_tmp_") for path in output.parent.iterdir())

print("batch_redub_destination_ok")
