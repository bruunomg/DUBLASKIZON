import shutil
import subprocess
import tempfile
import time
from pathlib import Path
import tkinter as tk

import batch_tab
import review_tab


if shutil.which("ffmpeg") is None:
    raise SystemExit("ffmpeg_not_available")

root = tk.Tk()
root.withdraw()
old_ask = batch_tab.messagebox.askyesno
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    audio_dir = project / "WAV ORIGINAIS"
    text_dir = project / "TXT TEXTO PORTUGUES"
    audio_dir.mkdir()
    text_dir.mkdir()
    source = audio_dir / "cena_mp3.mp3"
    source_ogg = audio_dir / "cena_ogg.ogg"
    legacy_wav = audio_dir / "cena_legado_convertido.wav"
    legacy_archived_wav = audio_dir / "mp3" / "cena_legado_subpasta_convertido.wav"
    legacy_archived_wav.parent.mkdir()
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2", "-ac", "2", str(source)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=0.2", "-ac", "1", str(source_ogg)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=520:duration=0.2", "-ar", "44100", "-ac", "2", str(legacy_wav)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=620:duration=0.2", "-ar", "48000", "-ac", "2", str(legacy_archived_wav)],
        check=True,
    )
    (text_dir / "cena_mp3.txt").write_text("Texto da cena", encoding="utf-8")
    (text_dir / "cena_ogg.txt").write_text("Texto OGG", encoding="utf-8")
    (text_dir / "cena_legado.txt").write_text("Texto legado", encoding="utf-8")
    (text_dir / "cena_legado_subpasta.txt").write_text("Texto legado subpasta", encoding="utf-8")
    batch_tab.messagebox.askyesno = lambda *args, **kwargs: True
    batch_tab.configure_project_root(project)
    app = batch_tab.BatchApp(root, embedded=False)
    for _ in range(150):
        root.update()
        if len(app.stems) == 4:
            break
        time.sleep(0.01)
    root.update_idletasks()
    assert app.stems == ["cena_legado", "cena_legado_subpasta", "cena_mp3", "cena_ogg"]
    assert (audio_dir / "cena_legado.wav").is_file()
    assert (audio_dir / "cena_legado_subpasta.wav").is_file()
    assert not legacy_wav.exists() and not legacy_archived_wav.exists()
    backup_dir = audio_dir / batch_tab.OMNIVOICE_BACKUP_DIR_NAME
    assert (backup_dir / "cena_legado.wav").is_file()
    assert (backup_dir / "cena_legado_subpasta.wav").is_file()
    output_wav = audio_dir / "cena_mp3.wav"
    output_ogg_wav = audio_dir / "cena_ogg.wav"
    archived_source = audio_dir / "mp3" / "cena_mp3.mp3"
    archived_ogg_source = audio_dir / "ogg" / "cena_ogg.ogg"
    assert app.audio_by_stem["cena_mp3"] == output_wav
    assert app.audio_by_stem["cena_ogg"] == output_ogg_wav
    assert output_wav.is_file() and output_ogg_wav.is_file()
    assert "_convertido" not in output_wav.name and "_convertido" not in output_ogg_wav.name
    assert not source.exists() and not source_ogg.exists(), "os formatos originais devem ser arquivados após a conversão"
    assert archived_source.is_file(), "o MP3 original deve ficar preservado na pasta mp3"
    assert archived_ogg_source.is_file(), "o OGG original deve ficar preservado na pasta ogg"
    for converted_path in (output_wav, output_ogg_wav, audio_dir / "cena_legado.wav", audio_dir / "cena_legado_subpasta.wav"):
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name,sample_rate,channels,bits_per_sample", "-of", "json", str(converted_path)], capture_output=True, text=True, check=True)
        stream = __import__("json").loads(probe.stdout)["streams"][0]
        assert stream["codec_name"] == "pcm_s16le"
        assert int(stream["sample_rate"]) == 24000
        assert int(stream["channels"]) == 1, "o perfil de clonagem OmniVoice deve ser mono"
        assert int(stream["bits_per_sample"]) == 16
        assert batch_tab.wav_needs_omnivoice_adjustment(converted_path) is False
    review_tab.configure_project_root(project)
    review_audio = review_tab.scene_audio_files()
    assert sorted(review_audio) == ["cena_legado", "cena_legado_subpasta", "cena_mp3", "cena_ogg"]
    assert app.audio_count_var.get().endswith("Cenas prontas: 4")
    assert hasattr(app, "dependencies_button")
    assert hasattr(app, "tools_help_button")
    assert hasattr(app, "download_progress")
    assert app.missing_tools() == []
    root.destroy()
batch_tab.messagebox.askyesno = old_ask
print("batch_audio_formats_ok")
