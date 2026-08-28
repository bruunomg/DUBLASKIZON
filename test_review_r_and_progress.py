from pathlib import Path
import tempfile

import batch_tab
import review_tab
from batch_tab import BatchApp
from review_tab import ReviewApp


class TextBox:
    def __init__(self):
        self.content = ""

    def configure(self, **_kwargs):
        pass

    def delete(self, *_args):
        self.content = ""

    def tag_configure(self, *_args, **_kwargs):
        pass

    def insert(self, _index, text, *_args):
        self.content += str(text)

    def see(self, *_args):
        pass


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Progress:
    def __init__(self):
        self.value = 0.0

    def set(self, value):
        self.value = float(value)


review = ReviewApp.__new__(ReviewApp)
review.busy = False
review.regen_r_override = None
review._choose_r_override = lambda parent=None: "soft"
redub_calls = []
review.regenerate_scene = lambda: redub_calls.append(review.regen_r_override)
review._redub_with_r_request(object())
assert redub_calls == ["soft"]
assert review.regen_r_override == "soft"
review.regen_r_override = None
review._choose_r_override = lambda parent=None: None
review.regenerate_with_other_audio = lambda: None
review._redub_other_with_r_request(object())
assert redub_calls == ["soft"]
assert review.regen_r_override is None

batch = BatchApp.__new__(BatchApp)
batch.running = False
batch.stems = ["CAP01/cena", "CAP02/cena"]
batch.review_regen_marker_state = None
batch.current_var = Var()
batch.status_var = Var()
batch.clone_progress = Progress()
batch.dub_progress = Progress()
queue_updates = []
batch.update_queue_item = lambda stem, marker, color: queue_updates.append((stem, marker, color))
batch._sync_review_regeneration_progress("CAP01/cena", 25, 10, "CLONANDO REFERÊNCIA...")
assert batch.current_stem == "CAP01/cena"
assert batch.clone_progress.value == 0.25
assert batch.dub_progress.value == 0.10
assert queue_updates[-1][1] == "[REFAZENDO]"
batch._sync_review_regeneration_progress("CAP01/cena", 100, 100, "REFAZER CENA concluído.", done=True, success=True)
assert batch.clone_progress.value == 1.0
assert batch.dub_progress.value == 1.0
assert queue_updates[-1][1] == "[REVISADA]"

batch.log_box = TextBox()
batch.append_review_process_message("CAP01/cena", "linha de teste", "info", "HISTÓRICO DA CENA")
assert "[REVISÃO — HISTÓRICO DA CENA] CAP01/cena: linha de teste" in batch.log_box.content
batch.append_review_process_message("CAP01/cena", "fase de teste", "info", "REFAZENDO A CENA")
assert "[REVISÃO — REFAZENDO A CENA] CAP01/cena: fase de teste" in batch.log_box.content

with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    batch_tab.configure_project_root(project)
    review_tab.configure_project_root(project)
    mirror = []
    review = ReviewApp.__new__(ReviewApp)
    review.state = {"CAP01/cena": {"status": "rejeitada", "updated_at": "agora", "reason": "teste"}}
    review.history_box = TextBox()
    review.process_message_callback = lambda stem, text, tag, section: mirror.append((stem, text, tag, section))
    review.update_history("CAP01/cena")
    assert mirror[-1][0] == "CAP01/cena"
    assert mirror[-1][3] == "HISTÓRICO DA CENA"
    review.regen_stem = "CAP01/cena"
    review.current_stem = lambda: "CAP01/cena"
    review.regen_log_box = TextBox()
    review.append_regen_log("Iniciando fase de teste")
    assert mirror[-1][3] == "REFAZENDO A CENA"
    assert "Iniciando fase de teste" in mirror[-1][1]

print("review_r_and_progress_ok")
