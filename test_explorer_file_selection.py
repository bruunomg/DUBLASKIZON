import tempfile
from pathlib import Path

import audio_player


with tempfile.TemporaryDirectory() as folder:
    path = (Path(folder) / "CAP02" / "cena.wav").resolve()
    path.parent.mkdir(parents=True)
    path.write_bytes(b"RIFF-test")
    commands = []
    old_platform = audio_player.sys.platform
    old_popen = audio_player.subprocess.Popen
    old_startfile = getattr(audio_player.os, "startfile", None)
    audio_player.sys.platform = "win32"
    audio_player.subprocess.Popen = lambda command, **kwargs: commands.append((command, kwargs))
    audio_player.os.startfile = lambda value: (_ for _ in ()).throw(AssertionError("os.startfile não deve ser usado"))
    try:
        assert audio_player.reveal_in_file_manager(path)
        assert [item[0] for item in commands] == [["explorer.exe", str(path.parent)]]

        invalid = path.parent / "arquivo_que_nao_existe.wav"
        assert not audio_player.reveal_in_file_manager(invalid)
        assert len(commands) == 1

        audio_player.subprocess.Popen = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("Explorer indisponível"))
        assert not audio_player.reveal_in_file_manager(path)
    finally:
        audio_player.sys.platform = old_platform
        audio_player.subprocess.Popen = old_popen
        if old_startfile is None:
            delattr(audio_player.os, "startfile")
        else:
            audio_player.os.startfile = old_startfile

print("explorer_file_selection_ok")
