from __future__ import annotations

import os
import stat
import tempfile
import time
from pathlib import Path

import audio_player


class DummyParent:
    def after(self, _delay, callback):
        callback()


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        audio = root / "CAV_003_Gray.wav"
        next_audio = root / "CAV_004_Gray.wav"
        audio.write_bytes(b"RIFF-test")
        next_audio.write_bytes(b"RIFF-test-next")
        original_dir = root / "WAV ORIGINAIS"
        original_dir.mkdir()
        original_audio = original_dir / audio.name
        original_next_audio = original_dir / next_audio.name
        original_audio.write_bytes(b"RIFF-original")
        original_next_audio.write_bytes(b"RIFF-original-next")
        capture = root / "ffplay_args.txt"
        fake_ffplay = root / "ffplay"
        fake_ffplay.write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$CAPTURE_FILE\"\nexit 0\n",
            encoding="utf-8",
        )
        fake_ffplay.chmod(fake_ffplay.stat().st_mode | stat.S_IXUSR)

        old_path = os.environ.get("PATH")
        old_app_dir = os.environ.get("DUBLASKIZON_APP_DIR")
        old_capture = os.environ.get("CAPTURE_FILE")
        try:
            os.environ["PATH"] = str(root)
            os.environ["DUBLASKIZON_APP_DIR"] = str(root)
            os.environ["CAPTURE_FILE"] = str(capture)
            statuses: list[str] = []
            manager = audio_player.AudioPlayerManager(
                DummyParent(), root, status_callback=statuses.append
            )
            previous_tk_available = audio_player.TK_AVAILABLE
            audio_player.TK_AVAILABLE = False
            try:
                manager.play_one(audio, "OUVIR CENA — CAV_003_Gray", playlist=[audio, next_audio], index=0)
                assert manager.pending_paths == [audio.resolve()]
                assert manager.navigation_paths == [audio.resolve(), next_audio.resolve()]
                assert manager.current_index == 0
                manager.navigate(1)
                assert manager.current_index == 1
                assert manager.pending_paths == [next_audio.resolve()]
                assert manager.original_pending_paths == [original_next_audio.resolve()]
            finally:
                audio_player.TK_AVAILABLE = previous_tk_available
            manager.pending_paths = [audio.resolve()]
            manager.start_pending()
            assert manager.thread is not None
            manager.thread.join(timeout=3)
            assert not manager.thread.is_alive(), "worker do player não terminou"
            assert capture.is_file(), "FFplay não recebeu o arquivo"
            captured = capture.read_text(encoding="utf-8")
            captured_args = captured.splitlines()
            assert str(audio.resolve()) in captured, "o caminho real não foi enviado ao FFplay"
            assert "-nostdin" not in captured_args, "a opção incompatível -nostdin não deve ser enviada"
            assert "-hide_banner" not in captured_args, "a opção incompatível -hide_banner não deve ser enviada"
            assert any("Reprodução concluída" in status for status in statuses)
            capture.write_text("", encoding="utf-8")
            manager.original_pending_paths = [original_audio.resolve()]
            manager.start_original_pending()
            assert manager.thread is not None
            manager.thread.join(timeout=3)
            original_capture = capture.read_text(encoding="utf-8")
            assert str(original_audio.resolve()) in original_capture, "o botão original não enviou o WAV de WAV ORIGINAIS"
        finally:
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path
            if old_app_dir is None:
                os.environ.pop("DUBLASKIZON_APP_DIR", None)
            else:
                os.environ["DUBLASKIZON_APP_DIR"] = old_app_dir
            if old_capture is None:
                os.environ.pop("CAPTURE_FILE", None)
            else:
                os.environ["CAPTURE_FILE"] = old_capture


if __name__ == "__main__":
    main()
    print("audio_player_ok")

