"""Prepare complete reference phrases inside the managed OmniVoice subprocess.

The host imports only standard-library code; model dependencies stay outside EXE.
Original references are never modified. Cache identity includes the audio contents.
"""

SELECTOR_CODE = r'''
def select_complete_reference(chunks, duration):
    """Return (end seconds, transcript) for a complete 3–10 second phrase."""
    import re
    words = []
    for index, chunk in enumerate(chunks):
        words.append(chunk.get('text', ''))
        start, end = chunk.get('timestamp', (None, None))
        if start is None or end is None or end <= start:
            continue
        if not 3 <= end <= 10 or end > duration - 0.2:
            continue
        if not re.search(r'[.!?]["\u201d\u2019]*\s*$', chunk.get('text', '')):
            continue
        next_start = chunks[index + 1].get('timestamp', (None, None))[0] if index + 1 < len(chunks) else duration
        if next_start is None or next_start - end < 0.10:
            continue
        # End inside the pause, before the following word begins.
        cutoff = end + min(0.15, (next_start - end) / 2)
        return cutoff, ''.join(words).strip()
    return None
'''
exec(SELECTOR_CODE)

WORKER_CODE = SELECTOR_CODE + r'''
import hashlib, json, os
from pathlib import Path
import numpy as np
import soundfile as sf
from omnivoice.models.omnivoice import OmniVoice
_original_prompt = OmniVoice.create_voice_clone_prompt

def _complete_prompt(self, ref_audio, ref_text=None, preprocess_prompt=True):
    if ref_text or not isinstance(ref_audio, (str, Path)):
        return _original_prompt(self, ref_audio, ref_text, preprocess_prompt)
    source = Path(ref_audio)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    root = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.cache'))) / 'Dublaskizon' / 'runtime' / 'voice-references-v1'
    root.mkdir(parents=True, exist_ok=True)
    audio_path, meta_path = root / (digest + '.wav'), root / (digest + '.json')
    try:
        metadata = json.loads(meta_path.read_text(encoding='utf-8'))
        if metadata.get('preserved') and metadata.get('digest') == digest and metadata.get('text','').strip():
            print('DESEMPENHO: transcrição da referência preservada reutilizada.',flush=True)
            return _original_prompt(self,ref_audio,metadata['text'],preprocess_prompt)
        cached, sr = sf.read(audio_path, dtype='float32')
        if metadata['digest'] != digest or not metadata['text'].strip() or len(cached) == 0:
            raise ValueError('Invalid cached reference')
        text = metadata['text']
        print('Referência completa reutilizada: ' + text, flush=True)
    except (OSError, ValueError, KeyError, RuntimeError):
        waveform, sr = sf.read(source, dtype='float32', always_2d=True)
        waveform = waveform.mean(axis=1)
        if self._asr_pipe is None:
            self.load_asr_model()
        import librosa
        asr_audio = librosa.resample(waveform, orig_sr=sr, target_sr=16000)
        generation={'task':'transcribe'}
        if len(waveform)/sr <= 10:
            generation['max_new_tokens']=128
        result = self._asr_pipe({'array': asr_audio, 'sampling_rate': 16000}, return_timestamps='word', generate_kwargs=generation)
        selection = select_complete_reference(result.get('chunks', []), len(waveform) / sr)
        if selection is None:
            print('AVISO: não foi identificado um trecho completo de 3–10 s; referência preservada. Prefira uma gravação sem palavras cortadas.', flush=True)
            text=result.get('text','').strip()
            if text:
                try:
                    temporary=meta_path.with_name(digest+'.'+str(os.getpid())+'.json')
                    temporary.write_text(json.dumps({'digest':digest,'text':text,'preserved':True},ensure_ascii=False),encoding='utf-8')
                    temporary.replace(meta_path)
                except OSError:
                    pass  # A cache problem must never stop dubbing.
            return _original_prompt(self, ref_audio, text or None, preprocess_prompt)
        cutoff, text = selection
        cached = waveform[:round(cutoff * sr)]
        # Publish cache with unique temporary files; simultaneous scenes cannot truncate it.
        token = str(os.getpid())
        temporary = audio_path.with_name(digest + '.' + token + '.wav')
        sf.write(temporary, cached, sr, subtype='PCM_16')
        temporary.replace(audio_path)
        temporary = meta_path.with_name(digest + '.' + token + '.json')
        temporary.write_text(json.dumps({'digest': digest, 'text': text}, ensure_ascii=False), encoding='utf-8')
        temporary.replace(meta_path)
        print('Referência completa preparada: %.2f s — %s' % (cutoff, text), flush=True)
    return _original_prompt(self, (cached, sr), text, False)

OmniVoice.create_voice_clone_prompt = _complete_prompt
'''


def protect_reference_command(command: list[str], model: str) -> list[str]:
    """Embed the preparation in managed OmniVoice only; other engines unchanged."""
    if 'omnivoice' not in model.lower() or len(command) < 4 or command[2] != '-c':
        return command
    result = list(command)
    result[3] = WORKER_CODE + '\n' + result[3]
    return result
