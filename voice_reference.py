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
        if not re.search(r'[.!?。！？]["\u201d\u2019]*\s*$', chunk.get('text', '')):
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

REFERENCE_SCAN_CODE = r'''
def find_reference_start(source):
    """Scan bounded blocks; silence in the original is never modified."""
    import numpy as np
    import soundfile as sf
    try:
        reader=sf.SoundFile(source)
    except AttributeError:return 0.0  # Older/testing decoder without streaming API.
    detector=None
    try:
        import torch
        from silero_vad import load_silero_vad,get_speech_timestamps
        detector=load_silero_vad()
    except (ImportError,OSError,RuntimeError):pass
    first_activity=None;offset=0
    with reader:
        rate=reader.samplerate
        while True:
            block=reader.read(round(8*rate),dtype='float32',always_2d=True)
            if not len(block):break
            # Do not average opposite-phase channels: that can cancel the voice.
            mono=block[:,int(np.argmax(np.mean(block*block,axis=0)))]
            width=max(1,round(rate*.1));count=len(mono)//width
            for index in range(max(0,count-1)):
                window=mono[index*width:(index+2)*width]
                if float(np.sqrt(np.mean(window*window)))>=.001 and float(np.max(np.abs(window)))>=.003:
                    if first_activity is None:first_activity=max(0,(offset+index*width)/rate-.2)
                    if detector is None:return first_activity
                    break
            if detector is not None and float(np.max(np.abs(mono)))>=.003:
                import librosa
                pcm=librosa.resample(mono,orig_sr=rate,target_sr=16000)
                regions=get_speech_timestamps(torch.from_numpy(pcm),detector,sampling_rate=16000,threshold=.4,min_speech_duration_ms=150,speech_pad_ms=80)
                if regions:return max(0,offset/rate+regions[0]['start']/16000-.15)
            offset+=len(block)
    if first_activity is not None:return first_activity
    raise RuntimeError('O áudio de referência está silencioso; escolha uma gravação com fala audível.')
'''
exec(REFERENCE_SCAN_CODE)

WORKER_CODE = SELECTOR_CODE + REFERENCE_SCAN_CODE + r'''
import hashlib, json, os
from pathlib import Path
import numpy as np
import soundfile as sf
from omnivoice.models.omnivoice import OmniVoice
_original_prompt = OmniVoice.create_voice_clone_prompt

def reference_has_speech(text, seconds):
    import re,unicodedata
    if not isinstance(text,str) or seconds<=0:return False
    words=re.findall(r"[^\W\d_]+",text.lower(),re.UNICODE)
    # Scripts without mandatory word spaces cannot use a Latin word-rate gate.
    characters=[char for char in text if unicodedata.category(char).startswith('L') and any(script in unicodedata.name(char,'') for script in ('CJK','HIRAGANA','KATAKANA','HANGUL','THAI','LAO','KHMER','MYANMAR'))]
    if len(characters)>=5:
        return bool(.6<=len(characters)/seconds<=14 and len(set(characters))/len(characters)>=.35)
    return bool(len(words)>=3 and .6<=len(words)/seconds<=6 and len(set(words))/len(words)>=.35)

def _complete_prompt(self, ref_audio, ref_text=None, preprocess_prompt=True):
    if not isinstance(ref_audio, (str, Path)):
        return _original_prompt(self, ref_audio, ref_text, preprocess_prompt)
    if ref_text and sf.info(ref_audio).duration<=20:
        return _original_prompt(self,ref_audio,ref_text,preprocess_prompt)
    source = Path(ref_audio)
    hasher=hashlib.sha256()
    with source.open('rb') as reader:
        for block in iter(lambda:reader.read(1024*1024),b''):hasher.update(block)
    digest=hasher.hexdigest()
    root = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.cache'))) / 'Dublaskizon' / 'runtime' / 'voice-references-v4'
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
        if not reference_has_speech(text,len(cached)/sr):raise ValueError('Referência sem fala suficiente')
        print('Referência completa reutilizada: ' + text, flush=True)
    except (OSError, ValueError, KeyError, RuntimeError):
        # Decode at most twenty seconds; never allocate a full long recording.
        info=sf.info(source)
        reference_start=find_reference_start(source) if info.duration>20 else 0.0
        if reference_start>0:print('Referência: início silencioso ignorado somente para clonagem; fala a partir de %.2f s.'%reference_start,flush=True)
        waveform, sr = sf.read(source, start=round(reference_start*info.samplerate),frames=round(20*info.samplerate), dtype='float32', always_2d=True)
        waveform = waveform[:,int(np.argmax(np.mean(waveform*waveform,axis=0)))]
        if self._asr_pipe is None:
            self.load_asr_model()
        import librosa
        asr_audio = librosa.resample(waveform, orig_sr=sr, target_sr=16000)
        generation={'task':'transcribe'}
        if len(waveform)/sr <= 10:
            generation['max_new_tokens']=128
        result = self._asr_pipe({'array': asr_audio, 'sampling_rate': 16000}, return_timestamps='word', generate_kwargs=generation)
        selection = select_complete_reference(result.get('chunks', []), len(waveform) / sr)
        if selection is None and info.duration > 20:
            # A word boundary with a real pause is safe even without punctuation.
            chunks=result.get('chunks',[]);words=[];candidates=[]
            for index,chunk in enumerate(chunks):
                words.append(chunk.get('text',''))
                start,end=chunk.get('timestamp',(None,None))
                following=chunks[index+1].get('timestamp',(None,None))[0] if index+1<len(chunks) else len(waveform)/sr
                if end is not None and following is not None and 3<=end<=10 and following-end>=.06:
                    candidates.append((end+min(.1,(following-end)/2),''.join(words).strip()))
            if candidates:selection=candidates[-1]
            else:
                # Transcribe exactly the bounded sample so reference text matches it.
                cutoff=min(8,len(waveform)/sr)
                bounded=asr_audio[:round(cutoff*16000)]
                result=self._asr_pipe({'array':bounded,'sampling_rate':16000},generate_kwargs={'task':'transcribe','max_new_tokens':128})
                selection=(cutoff,result.get('text','').strip())
            print('ESTABILIDADE: referência longa limitada a um trecho curto; original preservado.',flush=True)
        if selection is None:
            text=result.get('text','').strip()
            if text:
                try:
                    temporary=meta_path.with_name(digest+'.'+str(os.getpid())+'.json')
                    temporary.write_text(json.dumps({'digest':digest,'text':text,'preserved':True},ensure_ascii=False),encoding='utf-8')
                    temporary.replace(meta_path)
                except OSError:pass
            return _original_prompt(self, ref_audio, text or None, preprocess_prompt)
        cutoff, text = selection
        if info.duration>20 and not reference_has_speech(text,cutoff):
            # Opening logos/music often contain almost no dialogue. Search a few
            # bounded windows instead of using a one-word transcript as a voice.
            for offset in dict.fromkeys([reference_start+8,reference_start+16,reference_start+(info.duration-reference_start)*.5]):
                offset=min(offset,max(0,info.duration-8))
                candidate,sr=sf.read(source,start=round(offset*info.samplerate),frames=round(8*info.samplerate),dtype='float32',always_2d=True)
                candidate=candidate[:,int(np.argmax(np.mean(candidate*candidate,axis=0)))]
                pcm=librosa.resample(candidate,orig_sr=sr,target_sr=16000)
                recognized=self._asr_pipe({'array':pcm,'sampling_rate':16000},generate_kwargs={'task':'transcribe','max_new_tokens':128})
                candidate_text=recognized.get('text','').strip()
                if reference_has_speech(candidate_text,len(candidate)/sr):
                    waveform=candidate;cutoff=len(candidate)/sr;text=candidate_text
                    print('Referência com fala encontrada a partir de %.2f s.'%offset,flush=True)
                    break
            else:raise RuntimeError('Não foi possível validar fala suficiente nos trechos de referência testados. Isso pode ocorrer com música/ruído, fala baixa ou falha de reconhecimento. Selecione um recorte com voz audível ou outro áudio de referência; o original foi preservado.') from None
        if not text:raise RuntimeError('Não foi possível reconhecer fala na referência. Escolha um trecho com voz audível.') from None
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
