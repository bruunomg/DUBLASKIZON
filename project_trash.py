"""Move only a selected scene into a reversible project-local trash folder."""
from pathlib import Path
import json
import os
import time

ROOTS = {'WAV ORIGINAIS':('.wav','.wave','.mp3','.flac','.ogg','.wem'),
         'dublado':('.wav','.wave','.mp3','.flac','.ogg'),
         'dublados':('.wav','.wave','.mp3','.flac','.ogg'),
         'dublados personalizados':('.wav','.wave','.mp3','.flac','.ogg'),
         'TXT TEXTO ORIGINAL':('.txt',), 'TXT TEXTO PORTUGUES':('.txt',),
         'TXT TEXTO do WAV TRANSCRITO e TRADUZIDO':('.txt',)}


def scene_files(project, key):
    project=Path(project).resolve()
    key=Path(str(key).replace('\\','/'))
    if key.is_absolute() or not key.parts or any(p in ('.','..') for p in key.parts):
        raise ValueError('Identificador de cena inválido.')
    files=[]
    for name, extensions in ROOTS.items():
        for extension in extensions:
            file=project/name/str(key.parent)/(key.name+extension)
            if file.is_file():
                if not file.resolve().is_relative_to(project):
                    raise ValueError('A cena contém um caminho fora do projeto; nada foi movido.')
                files.append(file)
    return files


def move_scene(project, key):
    project=Path(project).resolve();files=scene_files(project,key)
    if not files:raise ValueError('Nenhum áudio ou TXT da cena foi encontrado nas pastas do projeto.')
    trash=project/'lixeira do projeto'
    if trash.exists() and not trash.resolve().is_relative_to(project):
        raise ValueError('A lixeira aponta para fora do projeto; nada foi movido.')
    token=str(time.time_ns())
    # Keep the original hierarchy directly under trash; never overwrite a prior move.
    base=trash
    if any((base/file.relative_to(project)).exists() for file in files):
        base=trash/'movimentos anteriores'/token
    moved=[]
    try:
        for source in files:
            destination=base/source.relative_to(project)
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.parent.resolve().is_relative_to(trash.resolve()) or destination.exists():
                raise ValueError('Destino inseguro ou já existente; movimento cancelado.')
            os.replace(source,destination)
            moved.append((source,destination))
        records=trash/'_registros';records.mkdir(parents=True,exist_ok=True)
        (records/(token+'.json')).write_text(json.dumps({'scene':str(key),'files':[{'original':str(s.relative_to(project)),'trash':str(d.relative_to(trash))} for s,d in moved]},ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception as error:
        rollback=[]
        for source,destination in reversed(moved):
            try:os.replace(destination,source)
            except OSError:rollback.append(str(destination))
        if rollback:raise RuntimeError('Falha ao mover; arquivos preservados na lixeira: '+', '.join(rollback)) from error
        raise RuntimeError('Movimento cancelado; arquivos devolvidos aos locais originais: '+str(error)) from error
    return [destination for source,destination in moved]
