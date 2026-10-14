import tempfile
import wave
from pathlib import Path

import tkinter as tk

from audio_player import AudioPlayerManager


def make_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * 240)


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    original_one = project / "WAV ORIGINAIS" / "CAP01" / "cena_001.wav"
    original_two = project / "WAV ORIGINAIS" / "CAP02" / "cena_001.wav"
    dubbed_one = project / "dublado" / "CAP01" / "cena_001.wav"
    dubbed_two = project / "dublado" / "CAP02" / "cena_001.wav"
    for path in (original_one, original_two, dubbed_one, dubbed_two):
        make_wav(path)

    root = tk.Tk()
    root.withdraw()
    try:
        selected = []
        actions = []
        player = AudioPlayerManager(root, project_root=project)
        auto_open_var = tk.StringVar(value="1")
        request_r_var = tk.StringVar(value="1")
        player.set_review_preferences({"auto_open_var": auto_open_var, "request_r_var": request_r_var})
        player.set_scene_integration(
            lambda key, index: selected.append((key, index)),
            {name: lambda key, action=name: actions.append((action, key)) for name in ("open_audacity", "approve", "reject", "redub", "redub_other")},
        )
        player.play_one(
            dubbed_one,
            "OUVIR CENA",
            playlist=[dubbed_one, dubbed_two],
            index=0,
            scene_key="CAP01/cena_001",
            scene_keys=["CAP01/cena_001", "CAP02/cena_001"],
        )
        root.update_idletasks()
        root.update()
        assert len(player.review_action_buttons) == 5, player.review_action_buttons
        assert len(player.audio_action_buttons) == 5, player.audio_action_buttons
        assert len(player.review_preference_widgets) == 2, player.review_preference_widgets
        assert [widget.cget("text") for widget in player.review_preference_widgets] == ["Abrir Audacity após redublar", "Pedido de alterar pronúncia do R"]
        assert [role for _button, role in player.audio_action_buttons] == ["neutral"] * 5
        min_width, min_height = player.window.minsize()
        assert (int(min_width), int(min_height)) >= (900, 380)
        assert all(int(button.cget("wraplength")) == 280 for button, _role in player.audio_action_buttons)
        assert selected[-1] == ("CAP01/cena_001", 0), selected
        old_reveal = __import__("audio_player").reveal_in_file_manager
        opened = []
        __import__("audio_player").reveal_in_file_manager = lambda path: opened.append(Path(path)) or True
        player._audio_context_action("open_dubbed")
        player._audio_context_action("open_original")
        assert opened == [dubbed_one.resolve(), original_one.resolve()]
        player._audio_context_action("copy_name")
        assert root.clipboard_get() == "cena_001.wav"
        player._audio_context_action("copy_dubbed")
        assert root.clipboard_get() == str(dubbed_one.parent.resolve())
        player._audio_context_action("copy_original")
        assert root.clipboard_get() == str(original_one.parent.resolve())
        __import__("audio_player").reveal_in_file_manager = old_reveal
        for action_name in ("open_audacity", "approve", "reject", "redub", "redub_other"):
            player._invoke_review_action(action_name)
        assert [item[0] for item in actions] == ["open_audacity", "approve", "reject", "redub", "redub_other"]
        assert all(item[1] == "CAP01/cena_001" for item in actions)

        player.navigate(1)
        root.update_idletasks()
        root.update()
        assert selected[-1] == ("CAP02/cena_001", 1), selected
        assert player.current_context_key == "CAP02/cena_001"
        player.close_window()
    finally:
        root.destroy()

print("audio_player_review_actions_ok")
