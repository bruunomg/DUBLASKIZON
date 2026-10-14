"""Persistent, per-output recovery. Never move or modify an original WAV."""
from pathlib import Path
import hashlib
import json
import re
import os
import shutil
import tempfile
import time
import wave


def _folder(target, project):
    target, project = Path(target).resolve(), Path(project).resolve()
    if any(part.casefold() == 'wav originais' for part in target.parts):
        raise ValueError('A recuperação é somente para áudios dublados.')
    return project/'revisoes'/'_recuperacao_audio'/hashlib.sha256(str(target).encode()).hexdigest()


def _digest(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def _validate(path):
    with wave.open(str(path),'rb') as wav:
        if wav.getnframes()<1 or wav.getcomptype()!='NONE':
            raise ValueError('A versão não contém áudio WAV PCM válido.')
        # Also reject truncated files, before touching the current output.
        expected=wav.getnframes()*wav.getnchannels()*wav.getsampwidth()
        read=0
        while chunk:=wav.readframes(65536):read+=len(chunk)
        if read!=expected:raise ValueError('Arquivo WAV incompleto; áudio atual preservado.')


def archive(target, project):
    target=Path(target).resolve()
    if not target.is_file():return None
    folder=_folder(target,project)/'historico'
    folder.mkdir(parents=True,exist_ok=True)
    destination=folder/f'{time.time_ns()}.wav'
    shutil.copy2(target,destination)
    return destination


def _previous(target, project, folder):
    own=sorted((folder/'historico').glob('*.wav'),key=lambda p:p.name,reverse=True)
    if own:return own[0]
    target,project=Path(target).resolve(),Path(project).resolve()
    try:relative=target.relative_to(project)
    except ValueError:relative=Path(target.name)
    parent=Path(*relative.parts[1:]).parent if relative.parts[0].casefold() in {'dublado','dublados personalizados'} else relative.parent
    candidates=[]
    revision=project/'revisoes'/parent
    for pattern in (target.stem+'_v*.wav',target.stem+'_edit_v*.wav'):
        candidates.extend(p for p in revision.glob(pattern) if re.fullmatch(re.escape(target.stem)+r'_(?:edit_)?v[0-9]+',p.stem))
    candidates.extend(target.parent.glob(target.stem+'_antes*.wav'))
    candidates=[p for p in candidates if p.resolve()!=target]
    return max(candidates,key=lambda p:(p.stat().st_mtime_ns,p.name),default=None)


def switch(target, project, latest=False):
    """Restore a previous output or undo recovery at precisely the same path."""
    target=Path(target).resolve()
    folder=_folder(target,project)
    try:state=json.loads((folder/'estado.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):state={}
    if latest:
        if not state or not target.is_file() or _digest(target)!=state.get('previous_hash'):
            raise ValueError('O áudio anterior não está ativo; o áudio atual foi mantido.')
        source=folder/'mais_atual.wav'
    else:
        if state and target.is_file() and _digest(target)==state.get('previous_hash'):
            raise ValueError('O áudio anterior já está ativo. Use VOLTAR AO MAIS ATUAL.')
        source=_previous(target,project,folder)
        if source is None:raise ValueError('Ainda não há uma versão anterior salva para este áudio.')
    _validate(source)
    if not latest:
        if not target.is_file():raise ValueError('Áudio dublado atual não encontrado.')
        _validate(target)
        folder.mkdir(parents=True,exist_ok=True)
        shutil.copy2(target,folder/'mais_atual.wav')
        shutil.copy2(source,folder/'anterior.wav')
        source=folder/'anterior.wav'
        state={'target':str(target),'previous_hash':_digest(source)}
        (folder/'estado.json').write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
    # Same-directory staging ensures a failed replacement leaves the output intact.
    fd,name=tempfile.mkstemp(prefix='.recuperar_',suffix='.wav',dir=target.parent)
    os.close(fd)
    temporary=Path(name)
    try:
        shutil.copyfile(source,temporary)
        os.replace(temporary,target)
    finally:temporary.unlink(missing_ok=True)
    # Existing ASR assessment describes another version; require fresh review.
    from speech_completeness import review_report_path
    report=review_report_path(target,project)
    report.parent.mkdir(parents=True,exist_ok=True)
    try:
        report.write_text(json.dumps({'needs_review':True,'notes':[{'version_switch':'mais atual' if latest else 'anterior'}]},ensure_ascii=False),encoding='utf-8')
    except OSError:
        pass  # Recovery succeeded; metadata cannot prevent the audio reload.
    return target
