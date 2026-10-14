"""Optional, bounded completeness checks for managed OmniVoice synthesis.

ASR disagreement is evidence for review, never proof of a defective recording.
Heavy libraries are imported only inside the engine subprocess.
"""
from pathlib import Path
import json
from repetition_prosody import PROFILE_CODE

CHECK_CODE = r'''
def review_report_path(audio, project=None, pending=False):
    from pathlib import Path
    import hashlib
    audio = Path(audio).resolve()
    if project is None:
        folders = {'dublado', 'dublados personalizados', 'revisoes', 'TEXTO PARA FALA'}
        project = next((parent.parent for parent in reversed(audio.parents) if parent.name in folders), audio.parent)
    project = Path(project).resolve()
    base = project / 'revisoes' / '_conferencia_fala' / 'relatorios'
    if pending:
        return base / '_pendentes' / (hashlib.sha256(str(audio).encode('utf-8')).hexdigest() + '.json')
    try:
        relative = audio.relative_to(project)
    except ValueError:
        relative = Path(hashlib.sha256(str(audio).encode('utf-8')).hexdigest()) / audio.name
    return base / relative.with_suffix('.conferencia.json')

def normalized_words(text):
    import re, unicodedata
    text = re.sub(r'\[(?:laughter|sigh|surprise-oh|breath|hesitation)\]', '', text, flags=re.I)
    text = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')
    words = re.findall(r'[^\W_]+', text, re.UNICODE)
    # Equivalent everyday contractions often expanded by speech recognition.
    equivalent = {'pra': ['para'], 'pro': ['para', 'o'], 'pras': ['para', 'as'],
                  'pros': ['para', 'os'], 'ta': ['esta'], 'to': ['estou'], 'ne': ['nao', 'e']}
    return [part for word in words for part in equivalent.get(word, [word])]

def compare_speech(expected, recognized):
    import difflib
    target, heard = normalized_words(expected), normalized_words(recognized)
    if not target:
        return {'status': 'uncertain', 'missing': [], 'coverage': 0.0}
    matcher = difflib.SequenceMatcher(None, target, heard, autojunk=False)
    missing, extra, matched, replaced = [], [], 0, False
    for kind, a, b, c, d in matcher.get_opcodes():
        if kind == 'equal':
            matched += b - a
        elif kind == 'delete':
            missing.extend(target[a:b])
        elif kind == 'insert':
            extra.extend(heard[c:d])
        elif kind == 'replace':
            if ''.join(target[a:b]) == ''.join(heard[c:d]):
                # ASR may write a compound as separate words: casamata / casa mata.
                matched += b - a
            else:
                replaced = True
                missing.extend(target[a:b])
                # A spelling disagreement (Mathias / Matias) is not an insertion.
                # Longer replacement blocks may contain additional spoken words.
                if d - c > b - a:
                    extra.extend(heard[c:d])
    coverage = matched / len(target)
    status = 'complete' if not missing and not extra else ('suspect' if coverage >= .60 and not replaced else 'uncertain')
    return {'status': status, 'missing': missing, 'extra': extra, 'coverage': coverage}

def split_speech(text, max_words=20):
    import re
    if max_words < 1:
        raise ValueError('max_words must be positive')
    parts, pending = [], []
    for word in text.split():
        pending.append(word)
        if len(pending) >= max_words or (len(pending) >= 3 and re.search(r'[.!?]["\u201d]*$', word)):
            parts.append(' '.join(pending)); pending = []
    if pending:
        parts.append(' '.join(pending))
    # Very short commands retain the preceding sentence's language context.
    merged = []
    for part in parts:
        if merged and len(part.split()) <= 2 and len((merged[-1] + ' ' + part).split()) <= max_words:
            merged[-1] += ' ' + part
        else:
            merged.append(part)
    return merged

def extra_word_intervals(expected, chunks):
    """Only remove timestamped insertions; never guess where missing words were."""
    import difflib
    target = normalized_words(expected)
    heard, owners = [], []
    for index, chunk in enumerate(chunks):
        words = normalized_words(chunk.get('text', ''))
        heard.extend(words)
        owners.extend([index] * len(words))
    if not target or not heard:
        return []
    removed, kept = set(), set()
    for kind, a, b, c, d in difflib.SequenceMatcher(None, target, heard, autojunk=False).get_opcodes():
        if kind == 'equal':
            kept.update(owners[c:d])
        elif kind == 'insert':
            removed.update(owners[c:d])
        else:
            return []  # Substitutions/missing words require regeneration, not cuts.
    if removed & kept:
        return []
    intervals = []
    for index in sorted(removed):
        start, end = chunks[index].get('timestamp', (None, None))
        if start is None or end is None or start < 0 or end <= start:
            return []
        # Reject timestamps overlapping a requested word.
        for neighbor in kept:
            left, right = chunks[neighbor].get('timestamp', (None, None))
            if left is None or right is None or (start < right and end > left):
                return []
        intervals.append((start, end))
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged

def recovery_parts(text):
    words = text.split()
    if len(words) < 6:
        return None
    middle = len(words) // 2
    weak_endings = {'a', 'o', 'as', 'os', 'de', 'do', 'da', 'dos', 'das', 'no', 'na', 'nos', 'nas', 'para', 'com', 'e', 'que'}
    candidates = range(max(3, middle - 2), min(len(words) - 3, middle + 2) + 1)
    strong = [i for i in candidates if (normalized_words(words[i - 1]) or [''])[-1] not in weak_endings]
    cut = min(strong, key=lambda i: abs(i - middle)) if strong else middle
    return [' '.join(words[:cut]), ' '.join(words[cut:])]

def contextual_parts(parts):
    """Keep short sentences with adjacent context rather than synthesize alone."""
    merged = []
    for part in parts:
        if merged and (len(part.split()) < 6 or len(merged[-1].split()) < 6) and len((merged[-1]+' '+part).split()) <= 40:
            merged[-1] += ' ' + part
        else:
            merged.append(part)
    return merged

def repetition_plan(text):
    """Recognize consecutive identical words, retaining surrounding text verbatim."""
    import re
    words=list(re.finditer(r'[^\W_]+',text,re.UNICODE))
    result=[];cursor=0;i=0
    while i<len(words):
        j=i+1
        while j<len(words) and normalized_words(words[j].group())==normalized_words(words[i].group()) and not text[words[j-1].end():words[j].start()].strip(' ,.;:!?…\n\t'):
            j+=1
        if j-i>=3:
            if text[cursor:words[i].start()].strip():result.append(('text',text[cursor:words[i].start()].strip(),1))
            result.append(('repeat',words[i].group(),j-i))
            cursor=words[j-1].end()
        i=j
    if not result:return []
    if text[cursor:].strip(' ,.;:!?…\n\t'):result.append(('text',text[cursor:].lstrip(' ,.;:!?…\n\t'),1))
    return result

def matched_text_interval(expected,chunks,duration):
    target=normalized_words(expected);words=[];owners=[]
    for i,chunk in enumerate(chunks):
        current=normalized_words(chunk.get('text',''))
        words.extend(current);owners.extend([i]*len(current))
    for i in range(len(words)-len(target)+1):
        if not target or words[i:i+len(target)]!=target:continue
        first,last=owners[i],owners[i+len(target)-1]
        start=chunks[first].get('timestamp',(None,None))[0]
        end=chunks[last].get('timestamp',(None,None))[1]
        previous=chunks[first-1].get('timestamp',(None,None))[1] if first else 0
        following=chunks[last+1].get('timestamp',(None,None))[0] if last+1<len(chunks) else duration
        if None in (start,end,previous,following) or not 0<=previous<=start<end<=following<=duration:continue
        return max(previous,start-.025),min(following,end+.025)
    return None
'''
exec(CHECK_CODE)

WORKER_CODE = CHECK_CODE + PROFILE_CODE + r'''
import sys, json, time
from pathlib import Path
import numpy as np
import soundfile as sf
from omnivoice.models.omnivoice import OmniVoice
_unchecked_generate = OmniVoice.generate
_DUBLASKIZON_TEXT_COMPLETE = False
_DUBLASKIZON_TEXT_AVAILABLE = False

def _verified_generate(self, *args, **kwargs):
    global _DUBLASKIZON_TEXT_COMPLETE, _DUBLASKIZON_TEXT_AVAILABLE
    _DUBLASKIZON_TEXT_COMPLETE = False
    _DUBLASKIZON_TEXT_AVAILABLE = False
    review_notes = []
    if args or not isinstance(kwargs.get('text'), str):
        return _unchecked_generate(self, *args, **kwargs)
    text = kwargs['text'].strip()
    if not text:
        raise ValueError('Texto de síntese vazio')
    if not normalized_words(text):
        print('CONFERÊNCIA: som não verbal sem palavras; conferência textual não se aplica.', flush=True)
        audio = _unchecked_generate(self, **kwargs)
        _DUBLASKIZON_TEXT_COMPLETE = True
        return audio
    preserve_pauses = globals().get('PERSONALIZED_TEXT_PAUSES', False)
    if preserve_pauses:
        import re
        # Explicit hesitations must survive synthesis and word verification.
        clauses = re.split(r'(?:\.{3,}|…+)', text)
        parts = []
        pause_before = []
        pending_pause = False
        for clause in clauses:
            chunks = split_speech(clause.strip()) if clause.strip() else []
            for chunk_index, chunk in enumerate(chunks):
                pause_before.append(.45 if pending_pause and chunk_index == 0 else .10)
                parts.append(chunk)
            if chunks:
                pending_pause = True
    else:
        parts = contextual_parts(split_speech(text))
        pause_before = [.10] * len(parts)
    reference_for_prosody = kwargs.get("ref_audio")
    options = dict(kwargs)
    # Do not fade a complete 100 ms syllable or automatically trim quiet endings.
    options['postprocess_output'] = False
    options['fade_duration'] = .005
    options['pad_duration'] = max(.10, float(options.get('pad_duration', .10)))
    if options.get('ref_audio') is not None and options.get('voice_clone_prompt') is None:
        options['voice_clone_prompt'] = self.create_voice_clone_prompt(options.pop('ref_audio'), options.pop('ref_text', None))
    def generate_checked(part, duration, label, depth=0):
        options = dict(base_options)
        options['text'] = part
        options['duration'] = duration
        accepted = None
        last_waveform = None
        best_waveform = None
        best_verdict = None
        best_heard = ''
        heard = ''
        verdict = compare_speech(part, '')
        failure_reason = ''
        batch_budget = globals().get('BATCH_VERIFICATION_BUDGET', False)
        attempts = 2 if batch_budget else (3 if depth == 0 else 2)
        for attempt in range(1, attempts + 1):
            base_steps = max(1, int(kwargs.get('num_step', 32)))
            options['num_step'] = min(max(96, base_steps), base_steps + 16 * (attempt - 1))
            if duration is None:
                # Retry with more synthesis steps, preserving the requested speaking rate.
                options['speed'] = float(kwargs.get('speed', 1.0))
            print('CONFERÊNCIA: trecho %s; tentativa %s/%s — gerando e verificando palavras' % (label, attempt, attempts), flush=True)
            synthesis_started = time.monotonic()
            waveforms = _unchecked_generate(self, **options)
            print('TEMPO: síntese %.2f s' % (time.monotonic()-synthesis_started), flush=True)
            if waveforms is None or len(waveforms) != 1 or waveforms[0] is None:
                failure_reason = 'Motor não retornou um áudio utilizável'
                print('CONFERÊNCIA: ' + failure_reason + '; tentando recuperar o trecho.', flush=True)
                continue
            waveform = np.asarray(waveforms[0], dtype=np.float32).squeeze().reshape(-1)
            if not waveform.size or not np.isfinite(waveform).all() or np.max(np.abs(waveform)) < 1e-6:
                failure_reason = 'Motor retornou áudio vazio, silencioso ou inválido'
                print('CONFERÊNCIA: ' + failure_reason + '; tentando recuperar o trecho.', flush=True)
                continue
            last_waveform = waveform
            if self._asr_pipe is None:
                self.load_asr_model()
            import librosa
            pcm = librosa.resample(waveform, orig_sr=self.sampling_rate, target_sr=16000)
            generation = {'task': 'transcribe'}
            language = kwargs.get('language')
            if language:
                generation['language'] = language
            # Enough tokens for the entire requested text, with punctuation
            # headroom. Bound hallucinated ASR loops, not the speech synthesis.
            generation['max_new_tokens'] = min(256 if batch_budget else 448,max(128,len(part.encode('utf-8'))+64))
            verification_started = time.monotonic()
            from contextlib import nullcontext
            asr_session=self._asr_pipe.session() if hasattr(self._asr_pipe,'session') else nullcontext()
            with asr_session:
                transcripts = []
                for start in range(0, len(pcm), 26 * 16000):
                    result = self._asr_pipe({'array': pcm[start:start+26*16000], 'sampling_rate': 16000}, generate_kwargs=generation)
                    transcripts.append(result['text'].strip())
                heard = ' '.join(transcripts)
                print('TEMPO: conferência %.2f s; duração gerada %.2f s' % (time.monotonic()-verification_started, len(waveform)/self.sampling_rate), flush=True)
                verdict = compare_speech(part, heard)
                expected_words=normalized_words(part)
                if duration is None and (verdict['coverage'] < .60 or (verdict['missing'] and (expected_words[0] in verdict['missing'] or expected_words[-1] in verdict['missing']))) and len(waveform)/self.sampling_rate < max(1.0,len(expected_words)*.38):
                    options['duration']=max(1.5,len(normalized_words(part))*.38)
                    print('CONFERÊNCIA: duração estimada curta demais; próxima tentativa com %.2f s para preservar palavras.'%options['duration'],flush=True)
                if verdict.get('extra') and not verdict['missing'] and len(pcm) <= 26 * 16000:
                    try:
                        timed = self._asr_pipe({'array': pcm, 'sampling_rate': 16000},
                                              generate_kwargs=generation, return_timestamps='word')
                        intervals = extra_word_intervals(part, timed.get('chunks', []))
                        if intervals and all(end <= len(waveform)/self.sampling_rate for start, end in intervals):
                            keep = np.ones(len(waveform), dtype=bool)
                            for start, end in intervals:
                                keep[round(start*self.sampling_rate):round(end*self.sampling_rate)] = False
                            candidate = waveform[keep]
                            if candidate.size:
                                check_pcm = librosa.resample(candidate, orig_sr=self.sampling_rate, target_sr=16000)
                                check = self._asr_pipe({'array': check_pcm, 'sampling_rate': 16000}, generate_kwargs=generation)
                                cleaned_verdict = compare_speech(part, check['text'])
                                if cleaned_verdict['status'] == 'complete':
                                    waveform, heard, verdict = candidate, check['text'], cleaned_verdict
                                    print('CONFERÊNCIA: acréscimo isolado removido e texto reconferido.', flush=True)
                    except Exception as repair_error:
                        print('CONFERÊNCIA: corte seguro indisponível; nova tentativa: ' + str(repair_error), flush=True)
                def candidate_score(result, transcript):
                    words=normalized_words(transcript)
                    edges=int(bool(words) and words[0]==expected_words[0])+int(bool(words) and words[-1]==expected_words[-1])
                    return (not result.get('extra'),result['coverage'],edges,-len(result.get('extra',[])))
                if best_verdict is None or candidate_score(verdict,heard)>candidate_score(best_verdict,best_heard):
                    best_waveform, best_verdict, best_heard = waveform, verdict, heard
                print('CONFERÊNCIA: texto reconhecido: ' + heard, flush=True)
                if verdict.get('extra'):
                    print('CONFERÊNCIA: palavras extras detectadas: ' + ', '.join(verdict['extra']), flush=True)
                verdict_label = {'complete': 'texto confirmado', 'suspect': 'possível trecho incompleto', 'uncertain': 'resultado incerto'}[verdict['status']]
                print('CONFERÊNCIA: %s; correspondência %.0f%%; palavras a conferir: %s' % (verdict_label, verdict['coverage'] * 100, ', '.join(verdict['missing'])), flush=True)
                if verdict['status'] == 'complete':
                    accepted = waveform
                    break
        if accepted is None:
            children = recovery_parts(part)
            if last_waveform is not None and children and any(len(child.split()) < 4 for child in children):
                children = None  # Tiny fragments lose context and can add speech artifacts.
            if not batch_budget and depth < 2 and children and not (globals().get('SAVE_UNCONFIRMED', False) and best_verdict and not best_verdict.get('extra') and best_verdict['coverage'] >= .75):
                # A different recovery strategy, rather than repeating the full failing phrase.
                print('CONFERÊNCIA: recuperação automática em dois trechos menores; texto preservado.', flush=True)
                recovered = []
                note_index = len(review_notes)
                try:
                    for child_index, child in enumerate(children, 1):
                        child_duration = None if duration is None else duration * len(child) / sum(len(p) for p in children)
                        recovered.append(generate_checked(child, child_duration, label + '.' + str(child_index), depth + 1))
                except RuntimeError as error:
                    if not (globals().get('SAVE_UNCONFIRMED', False) and best_waveform is not None and 'DUBLASKIZON_NEEDS_REVIEW' in str(error)):
                        raise
                    del review_notes[note_index:]
                    recovered = []
                if recovered:
                    if duration is None:
                        recovered.insert(1, np.zeros(round(self.sampling_rate * .06), dtype=np.float32))
                    return np.concatenate(recovered)
            if best_waveform is not None:
                last_waveform, verdict, heard = best_waveform, best_verdict, best_heard
            # Retain the best usable evidence; availability is distinct from confirmation.
            folder = Path(COMPLETENESS_REVIEW_DIR)
            folder.mkdir(parents=True, exist_ok=True)
            name = ('fala_' + str(time.time_ns()) + '_trecho_' + label.replace('/', '_'))
            path = folder / (name + '.wav')
            if last_waveform is not None:
                sf.write(path, last_waveform, self.sampling_rate)
            report = folder / (name + '.json')
            report.write_text(json.dumps({'requested': part, 'recognized': heard, 'result': verdict, 'generation_problem': failure_reason}, ensure_ascii=False, indent=2), encoding='utf-8')
            evidence = 'Amostra para ouvir: ' + str(path) if last_waveform is not None else 'Nenhum áudio utilizável foi gerado. Relatório: ' + str(report)
            if globals().get('SAVE_UNCONFIRMED', False) and last_waveform is not None:
                review_notes.append({'requested': part, 'recognized': heard, 'result': verdict, 'report': str(report)})
                print('DUBLASKIZON_REVIEW_REQUIRED: áudio disponível; confira a pronúncia e as palavras: ' + part, flush=True)
                return last_waveform
            raise RuntimeError('DUBLASKIZON_NEEDS_REVIEW: A fala precisa de revisão após as tentativas de recuperação. A transcrição também pode errar. O áudio anterior foi preservado. ' + evidence)
        return accepted

    base_options = options
    repeated_plan = repetition_plan(text) if kwargs.get('language') in ('pt','Portuguese') and kwargs.get('duration') is None else []
    if repeated_plan:
        print('CONFERÊNCIA: recuperação de repetições explícitas; quantidade do TXT preservada.',flush=True)
        repeated_clips=[]
        for plan_index, (kind, value, count) in enumerate(repeated_plan):
            if kind=='text':
                recovered=None
                if len(normalized_words(value))<6:
                    for attempt in range(3):
                        carrier='Vou dizer uma frase. '+value.strip(' ,.;:!?')+'.'
                        print('CONFERÊNCIA: recuperando frase curta com contexto; tentativa %s/3'%(attempt+1),flush=True)
                        probe=_unchecked_generate(self,**dict(base_options,text=carrier,duration=max(4.0,len(normalized_words(carrier))*.42),num_step=32+16*attempt))
                        if probe is None or len(probe)!=1 or probe[0] is None:continue
                        probe=np.asarray(probe[0],dtype=np.float32).reshape(-1)
                        if not probe.size or not np.isfinite(probe).all():continue
                        if self._asr_pipe is None:self.load_asr_model()
                        import librosa
                        pcm=librosa.resample(probe,orig_sr=self.sampling_rate,target_sr=16000)
                        try:timed=self._asr_pipe({'array':pcm,'sampling_rate':16000},return_timestamps='word',generate_kwargs={'task':'transcribe','language':'pt'})
                        except (RuntimeError,ValueError,TypeError):continue
                        print('CONFERÊNCIA: frase com contexto reconhecida: '+str(timed.get('text','')),flush=True)
                        interval=matched_text_interval(value,timed.get('chunks',[]),len(probe)/self.sampling_rate)
                        if interval:
                            start,end=interval
                            recovered=probe[round(start*self.sampling_rate):round(end*self.sampling_rate)].copy()
                            if recovered.size and np.max(np.abs(recovered))>1e-5:break
                            recovered=None
                repeated_clips.append(recovered if recovered is not None else generate_checked(value,None,'contexto'))
                repeated_clips.append(np.zeros(round(self.sampling_rate*.15),dtype=np.float32))
                continue
            carrier='Vou falar uma palavra. '+value.capitalize()+'!'
            isolated=None
            takes=[]
            for attempt in range(3):
                # Stuttering references can produce an unrealistically short
                # automatic duration estimate. Give the carrier enough time.
                probe_options=dict(base_options,text=carrier,duration=max(3.5,len(normalized_words(carrier))*.42),num_step=32+16*attempt)
                print('CONFERÊNCIA: preparando palavra repetida %s; tentativa %s/3'%(value,attempt+1),flush=True)
                probe=_unchecked_generate(self,**probe_options)
                if probe is None or len(probe)!=1 or probe[0] is None:continue
                probe=np.asarray(probe[0],dtype=np.float32).reshape(-1)
                if not probe.size or not np.isfinite(probe).all():continue
                if self._asr_pipe is None:self.load_asr_model()
                import librosa
                pcm=librosa.resample(probe,orig_sr=self.sampling_rate,target_sr=16000)
                try:
                    timed=self._asr_pipe({'array':pcm,'sampling_rate':16000},return_timestamps='word',generate_kwargs={'task':'transcribe','language':'pt'})
                except (RuntimeError,ValueError,TypeError) as exc:
                    print('CONFERÊNCIA: tempos da repetição indisponíveis: '+str(exc),flush=True)
                    continue
                chunks=timed.get('chunks',[])
                print('CONFERÊNCIA: frase auxiliar reconhecida: '+str(timed.get('text',''))+'; tempos: '+repr(chunks[:3]),flush=True)
                index=next((i for i,chunk in enumerate(chunks) if normalized_words(chunk.get('text',''))==normalized_words(value)),None)
                if index is None:continue
                start,end=chunks[index].get('timestamp',(None,None))
                following=chunks[index+1].get('timestamp',(None,None))[0] if index+1<len(chunks) else len(probe)/self.sampling_rate
                if start is None or end is None or following is None or not 0<=start<min(end,following):continue
                stop=min(end+.025,following)
                previous=chunks[index-1].get('timestamp',(None,None))[1] if index else 0
                if previous is None or previous>start:continue
                isolated=probe[round(max(0,start-.025,previous)*self.sampling_rate):round(stop*self.sampling_rate)].copy()
                if isolated.size and np.max(np.abs(isolated))>1e-5:
                    takes.append(isolated)
                    if len(takes)>=2:break
                isolated=None
            if not takes:
                print('CONFERÊNCIA: isolamento indisponível; mantendo recuperação normal.',flush=True)
                repeated_clips.append(generate_checked(', '.join([value]*count),None,'repeticoes'))
            else:
                words=normalized_words(text)
                total=max(1,len(words))
                preceding=sum(len(normalized_words(v))*n for k,v,n in repeated_plan[:plan_index])
                profile=reference_repetition_profile(reference_for_prosody,count,preceding/total,(preceding+count)/total)
                repeated_clips.extend(expressive_repetition_clips(takes,profile,self.sampling_rate))
                review_notes.append({'repetition_profile':profile,'independent_takes':len(takes)})
                print('CONFERÊNCIA: %s ocorrências audíveis de %s montadas sem o texto auxiliar.'%(count,value),flush=True)
        result=[np.concatenate(repeated_clips)]
        _DUBLASKIZON_TEXT_AVAILABLE=True
        _DUBLASKIZON_TEXT_COMPLETE=False
        review_notes.append({'requested':text,'reason':'Repetições reconstruídas; conferir cadência e contagem.'})
        if '--output' in sys.argv:
            output=Path(sys.argv[sys.argv.index('--output')+1])
            assessment=review_report_path(output,Path(COMPLETENESS_REVIEW_DIR).parent.parent,pending=True)
            assessment.parent.mkdir(parents=True,exist_ok=True)
            assessment.write_text(json.dumps({'needs_review':True,'notes':review_notes},ensure_ascii=False,indent=2),encoding='utf-8')
        return result
    clips = []
    for index, part in enumerate(parts, 1):
        duration = None if kwargs.get('duration') is None else kwargs['duration'] * len(part) / sum(len(p) for p in parts)
        accepted = generate_checked(part, duration, '%s/%s' % (index, len(parts)))
        if clips and kwargs.get('duration') is None:
            clips.append(np.zeros(round(self.sampling_rate * pause_before[index-1]), dtype=np.float32))
        clips.append(accepted)
    print('CONFERÊNCIA: salvando áudio para revisão.' if review_notes else 'CONFERÊNCIA: todos os trechos confirmados; salvando áudio completo.', flush=True)
    if '--output' in sys.argv:
        output = Path(sys.argv[sys.argv.index('--output') + 1])
        assessment = review_report_path(output, Path(COMPLETENESS_REVIEW_DIR).parent.parent, pending=True)
        assessment.parent.mkdir(parents=True, exist_ok=True)
        assessment.write_text(json.dumps({'needs_review': bool(review_notes), 'notes': review_notes}, ensure_ascii=False, indent=2), encoding='utf-8')
    result = [np.concatenate(clips)]
    _DUBLASKIZON_TEXT_COMPLETE = not review_notes
    _DUBLASKIZON_TEXT_AVAILABLE = True
    return result

OmniVoice.generate = _verified_generate
'''


def enabled(project):
    try:
        return bool(json.loads((Path(project) / 'Dublaskizon_conferencia_fala.json').read_text(encoding='utf-8')).get('enabled', True))
    except (OSError, ValueError):
        return True


def friendly_error(error):
    marker = 'DUBLASKIZON_NEEDS_REVIEW: '
    lines = str(error).splitlines()
    messages = [line.split(marker, 1)[1] for line in lines if marker in line and not line.lstrip().startswith(('raise ', 'File '))]
    return messages[-1] if messages else str(error)


def verified_command(command, model, project, *, require_complete=True, personalized_pauses=False, batch_budget=False):
    if (not require_complete and not enabled(project)) or 'omnivoice' not in str(model).lower() or len(command) < 4 or command[2] != '-c':
        return command
    result = list(command)
    # Normal cloning and review also need a complete short reference. Previously
    # only personalized dubbing used this protection, leaving long game scenes
    # (including effects/music) as conditioning for every generated fragment.
    if 'OmniVoice.create_voice_clone_prompt = _complete_prompt' not in result[3]:
        from voice_reference import protect_reference_command
        result = protect_reference_command(result, str(model))
    directory = str(Path(project).resolve() / 'revisoes' / '_conferencia_fala')
    result[3] = 'SAVE_UNCONFIRMED=True\nBATCH_VERIFICATION_BUDGET=' + repr(bool(batch_budget)) + '\nPERSONALIZED_TEXT_PAUSES=' + repr(bool(personalized_pauses)) + '\nCOMPLETENESS_REVIEW_DIR=' + repr(directory) + '\n' + WORKER_CODE + '\n' + result[3]
    # Avoid the Windows CreateProcess command-line limit without truncation.
    if Path(str(result[0])).is_file() and sum(len(str(arg)) + 3 for arg in result) > 28000:
        import hashlib
        script_dir = Path(directory) / '_scripts'
        script_dir.mkdir(parents=True, exist_ok=True)
        script = script_dir / (hashlib.sha256(result[3].encode('utf-8')).hexdigest() + '.py')
        if not script.exists():
            script.write_text(result[3], encoding='utf-8')
        result[3] = "exec(compile(__import__('pathlib').Path(" + repr(str(script)) + ").read_text(encoding='utf-8'), '<script Python interno>', 'exec'))"
    return result


def mount_controls(parent, project):
    from tkinter import messagebox, ttk
    row = ttk.Frame(parent)
    row.pack(fill='x', padx=6, pady=(3, 4))
    ttk.Label(row, text='CONFERÊNCIA AUTOMÁTICA DO TEXTO INTEIRO — OmniVoice').pack(side='left')
    ttk.Button(row, text='?', width=3, command=lambda: messagebox.showinfo('Conferência da fala',
        'OmniVoice gerenciado: a conferência é automática, inclusive se uma configuração antiga a desativava.\n'
        'Textos longos são divididos em frases e trechos de até 20 palavras. Cada trecho é transcrito e conferido.\n'
        'Trechos incompletos são tentados novamente e, se necessário, divididos para recuperação.\n'
        'Se o reconhecimento não confirmar, a melhor amostra válida é salva para REVISAR, com relatório. Falhas sem áudio válido preservam a saída anterior.\n'
        'Palavras extras detectadas provocam nova tentativa. Se persistirem, o melhor áudio válido é salvo como REVISAR, sem bloquear a geração.\n'
        'O reconhecimento pode errar. A conferência usa os modelos já carregados na fila rápida.', parent=row)).pack(side='left', padx=4)
    return row


def publish_review_report(temporary, target):
    """Keep assessments in the project's review area, separate from the WAVs."""
    source = review_report_path(temporary, pending=True)
    legacy_source = Path(temporary).with_suffix('.conferencia.json')
    if not source.exists() and legacy_source.exists():
        source = legacy_source
    destination = review_report_path(target)
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        Path(target).with_suffix('.conferencia.json').unlink(missing_ok=True)
    else:
        destination.unlink(missing_ok=True)
        Path(target).with_suffix('.conferencia.json').unlink(missing_ok=True)
    return needs_review(target)


def mark_pending_review(audio, project, reason):
    path = review_report_path(audio, project, pending=True)
    try:
        report = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        report = {'notes': []}
    report['needs_review'] = True
    report.setdefault('notes', []).append({'alignment_warning': str(reason)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

def needs_review(audio):
    path = review_report_path(audio)
    legacy = Path(audio).with_suffix('.conferencia.json')
    try:
        if not path.exists() and legacy.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            legacy.replace(path)
        return bool(json.loads(path.read_text(encoding='utf-8')).get('needs_review'))
    except (OSError, ValueError):
        return False
