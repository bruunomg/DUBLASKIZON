import tempfile
import time
from pathlib import Path

import batch_tab
import review_tab

with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    audio_root = project / "WAV ORIGINAIS"
    text_root = project / "TXT TEXTO PORTUGUES"
    total = 3000
    for index in range(total):
        chapter = audio_root / f"CAP{index // 100:03d}"
        text_chapter = text_root / chapter.name
        chapter.mkdir(parents=True, exist_ok=True)
        text_chapter.mkdir(parents=True, exist_ok=True)
        basename = f"cena_{index % 100:03d}"
        (chapter / f"{basename}.wav").write_bytes(b"RIFF")
        (text_chapter / f"{basename}.txt").write_text("texto", encoding="utf-8")
    batch_tab.configure_project_root(project)
    review_tab.configure_project_root(project)
    started = time.monotonic()
    audio = batch_tab.find_audio_by_stem()
    texts = batch_tab.find_text_by_stem()
    review_audio = review_tab.scene_audio_files()
    elapsed = time.monotonic() - started
    assert len(audio) == total, len(audio)
    assert len(texts) == total, len(texts)
    assert len(review_audio) == total, len(review_audio)
    assert "CAP000/cena_000" in audio
    assert "CAP029/cena_099" in audio
    assert set(audio) == set(texts) == set(review_audio)
    print(f"nested_discovery_performance_ok: {total} pares em {elapsed:.3f}s")
