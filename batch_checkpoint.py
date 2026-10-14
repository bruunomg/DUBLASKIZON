"""Append-only project checkpoint: one small record per completed scene."""
from pathlib import Path
import json

def load_checkpoint(project):
    records = {}
    path = Path(project) / 'revisoes' / '_controle_lote' / 'clonagem.jsonl'
    if path.exists():
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                    records[item['stem']] = item['status']
                except (ValueError, KeyError, TypeError):
                    continue  # A power failure may leave the last line incomplete.
    return records

def record_checkpoint(project, stem, status):
    path = Path(project) / 'revisoes' / '_controle_lote' / 'clonagem.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'stem': stem, 'status': status}, ensure_ascii=False) + '\n')

def plan_batch(stems, records, output, *, resume=False, ignore_errors=False):
    result = []
    for stem in stems:
        if ignore_errors and records.get(stem) == 'error':
            continue
        file = Path(output) / f'{stem}.wav'
        if resume and records.get(stem) not in ('error','revisar') and file.is_file() and file.stat().st_size > 44:
            continue
        result.append(stem)
    return result

def session_file(project):
    return Path(project) / 'revisoes/_controle_lote/fila.json'

def save_session(project, stems):
    path = session_file(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(list(stems),ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)
    save_cursor(project,0)

def save_cursor(project, cursor):
    path=session_file(project).with_name('posicao.json')
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(int(cursor)),encoding='utf-8')
    temporary.replace(path)

def remaining_session(project):
    try:
        stems=json.loads(session_file(project).read_text(encoding='utf-8'))
        cursor=json.loads(session_file(project).with_name('posicao.json').read_text(encoding='utf-8'))
        if isinstance(stems,list) and all(isinstance(item,str) for item in stems) and isinstance(cursor,int):
            return stems[max(0,cursor):]
    except (OSError,ValueError):
        pass
    return None

def recover_records(project, stems, output):
    records=load_checkpoint(project)
    from speech_completeness import needs_review
    import os
    wanted=set(stems); output=Path(output)
    # Enumerate existing outputs instead of querying all 51k missing paths.
    for folder,dirs,names in os.walk(output):
        for name in names:
            if not name.lower().endswith('.wav') or name.startswith('.'):continue
            file=Path(folder)/name
            stem=file.relative_to(output).with_suffix('').as_posix()
            if stem not in wanted or records.get(stem) in ('error','timed_out','no_speech'):continue
            if file.stat().st_size > 44:
                records[stem]='revisar' if needs_review(file) else records.get(stem,'existing')
    return records
