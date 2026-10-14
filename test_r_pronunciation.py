from pathlib import Path

from batch_tab import (
    BatchApp,
    R_PRONUNCIATION_CHOICES,
    apply_r_pronunciation,
    r_pronunciation_instruction,
)


assert [mode_id for _label, mode_id in R_PRONUNCIATION_CHOICES] == ["unchanged", "soft", "normal", "strong"]
assert apply_r_pronunciation("O carro vermelho passou rápido.", "unchanged") == "O carro vermelho passou rápido."
assert apply_r_pronunciation("O carro vermelho passou rápido.", "normal") == "O carro vermelho passou rápido."
assert apply_r_pronunciation("O carro vermelho passou rápido.", "strong") == "O carro vermelho passou rápido."
assert apply_r_pronunciation("O caro vermelho passou rápido.", "strong") == "O carro vermelho passou rápido."
assert apply_r_pronunciation("O carro vermelho passou rápido.", "soft") == "O caro vermelho passou rápido."
assert r_pronunciation_instruction("soft") == ""
assert r_pronunciation_instruction("normal") == ""
assert r_pronunciation_instruction("strong") == ""
assert r_pronunciation_instruction("unchanged") == ""

app = BatchApp.__new__(BatchApp)
app.infer_prefix = ["omnivoice-infer"]
app.selected_model = "edwixx/omnivoice-brpt-v15"
app.selected_mode = "clone"
app.selected_instruct = "portuguese accent"
app.selected_r_pronunciation = "soft"
reference = Path("/tmp/reference.wav")
app.audio_by_stem = {"CAP01/cena": reference}
command = app.build_infer_command("CAP01/cena", "O carro vermelho.", Path("/tmp/out.wav"))
assert command[command.index("--text") + 1] == "O caro vermelho."
assert command[command.index("--instruct") + 1] == "portuguese accent"
assert "R suave" not in command[command.index("--instruct") + 1]
assert command[command.index("--ref_audio") + 1] == str(reference)

app.selected_r_pronunciation = "unchanged"
unchanged_command = app.build_infer_command("CAP01/cena", "O carro vermelho.", Path("/tmp/out.wav"))
assert unchanged_command[unchanged_command.index("--text") + 1] == "O carro vermelho."
assert unchanged_command[unchanged_command.index("--instruct") + 1] == "portuguese accent"

print("r_pronunciation_ok")
