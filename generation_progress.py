"""Progress from generator output; never extrapolate completion from elapsed time."""
import re
import os
import tempfile
import threading
from pathlib import Path


class GenerationProgress:
    def __init__(self, emit):
        self.emit = emit
        self.clone = self.dub = 0.0
        self.phase = 'Preparando modelo / referência'

    def feed(self, line):
        text = line.lower()
        clone, dub, phase = self.clone, self.dub, self.phase
        if any(word in text for word in ('generating audio', 'sampling', 'denoising', 'synthesizing', 'generation steps')):
            clone, dub, phase = 100.0, max(dub, 1.0), 'Dublando / síntese'
        elif any(word in text for word in ('transcrib', 'asr model', 'encoding prompt', 'reference audio')) and not dub:
            clone, phase = max(clone, 65.0), 'Preparando / transcrevendo referência'
        elif 'model loaded' in text and not dub:
            clone, phase = max(clone, 50.0), 'Modelo carregado; preparando referência'
        elif any(word in text for word in ('loading', 'fetching', 'download')) and not dub:
            clone, phase = max(clone, 5.0), 'Carregando modelo / referência'
        percent = re.search(r'(\d+(?:\.\d+)?)%\|', text)
        if percent and dub and not any(w in text for w in ('loading', 'fetching', 'download')):
            dub = max(dub, min(99.0, float(percent.group(1))))
        if 'saved to' in text or 'audio saved' in text:
            clone, dub, phase = 100.0, 99.0, 'Áudio gerado; validando e salvando'
        state = (max(self.clone, clone), max(self.dub, dub), phase)
        if state != (self.clone, self.dub, self.phase):
            self.clone, self.dub, self.phase = state
            self.emit(*state)


def run_observed(command, emit, runner, **kwargs):
    """Keep subprocess.run compatibility while observing CR-delimited output live."""
    kwargs["env"] = {**os.environ, **kwargs.get("env", {}), "PYTHONUNBUFFERED":"1", "PYTHONIOENCODING":"utf-8"}
    done = threading.Event()
    observer = GenerationProgress(emit)
    with tempfile.TemporaryDirectory(prefix='dublaskizon-progress-') as directory:
        path = Path(directory) / 'output.log'
        path.touch()
        def tail():
            pending = ''
            with path.open('r', encoding='utf-8', errors='replace') as stream:
                while True:
                    pending += stream.read()
                    parts = re.split(r'[\r\n]', pending)
                    pending = parts.pop()
                    for line in parts:
                        observer.feed(line)
                    if done.is_set():
                        pending += stream.read()
                        for line in re.split(r'[\r\n]', pending):
                            observer.feed(line)
                        return
                    done.wait(.1)
        with path.open('wb') as output:
            thread = threading.Thread(target=tail, daemon=True)
            thread.start()
            try:
                result = runner(command, stdout=output, **kwargs)
            finally:
                done.set()
                thread.join()
        if not getattr(result, 'stdout', None):
            result.stdout = path.read_text(encoding='utf-8', errors='replace')[-16000:]
        return result
