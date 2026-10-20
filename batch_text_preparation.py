"""Prepare all missing scene texts before starting any synthesis."""
import hashlib,json
from pathlib import Path
import transcription_backend as backend
import audio_translation as translation

def prepare_missing_texts(stems,audios,texts,text_root,project,config,emit,cancelled,wait=lambda:None,on_progress=lambda *a:None,on_theme=lambda profile:None):
    config=dict(config);profile=dict(config.get('context_profile',{}));config['context_profile']=profile
    pending=[];records={};prepared={};errors={};cache={};existing=0
    folder=Path(project)/'revisoes'/'preparacao_textos';folder.mkdir(parents=True,exist_ok=True)
    emit('VARREDURA: verificando áudios sem TXT ou com TXT vazio; textos existentes serão preservados.')
    for stem in stems:
        if cancelled():raise RuntimeError('Preparação cancelada.')
        path=Path(texts.get(stem) or Path(text_root)/(stem+'.txt'))
        try:
            if path.is_file() and path.read_text(encoding='utf-8-sig').strip():
                existing+=1;continue
        except (OSError,UnicodeError) as exc:errors[stem]=str(exc);continue
        audio=Path(audios[stem]);stat=audio.stat()
        marker=json.dumps([str(audio.resolve()),stat.st_size,stat.st_mtime_ns,config],sort_keys=True,ensure_ascii=False)
        target=folder/(hashlib.sha256(marker.encode()).hexdigest()+'.json');cache[stem]=target
        try:record=json.loads(target.read_text(encoding='utf-8'))
        except (OSError,ValueError):record={}
        if record.get('translated') and record.get('language'):
            prepared[stem]=(record['translated'],record['language']);emit('PREPARAÇÃO: texto pronto retomado — '+stem)
        elif record.get('transcript'):records[stem]=record
        else:pending.append(stem)
    emit(f'VARREDURA: {len(stems)} áudios verificados; {existing} TXTs preenchidos preservados; {len(pending)+len(records)+len(prepared)} ausentes/vazios; {len(prepared)} prontos para retomar; {len(errors)} erros de leitura.')
    if not pending and not records and not prepared:emit('NENHUM TXT AUSENTE OU VAZIO: não é necessário transcrever/traduzir nesta execução. Cadastrar tema não substitui textos existentes.')
    def checkpoint(stem):backend.atomic_json(cache[stem],records[stem])
    def accept(index,data):
        stem=pending[index]
        if data.get('error') or not str(data.get('transcript','')).strip():
            errors[stem]=str(data.get('error') or 'Transcrição vazia.');emit('ERRO NA TRANSCRIÇÃO '+stem+': '+errors[stem]);return
        records[stem]=dict(data);checkpoint(stem);emit(f'TRANSCRITO {index+1}/{len(pending)}: '+stem);on_progress(stem,'transcribe',1);wait()
        if cancelled():raise RuntimeError('Preparação cancelada; transcrições salvas.')
    if pending:
        emit('PREPARAÇÃO 1/3: transcrevendo todos os áudios sem TXT; síntese ainda não iniciada.')
        try:backend.run_local_batch([Path(audios[s]) for s in pending],config,emit,cancelled,accept)
        except Exception as exc:
            if cancelled():raise
            emit('AVISO na transcrição do lote: '+str(exc))
        for stem in pending:
            if stem not in records:errors.setdefault(stem,'Transcrição não concluída; tente retomar.')
    corpus='\n\n'.join(record['transcript'] for record in records.values())
    if profile.get('title') and corpus.strip():
        wait()
        if cancelled():raise RuntimeError('Preparação cancelada.')
        emit('PREPARAÇÃO 2/3: pesquisando o tema e os termos dos transcritos com a IA configurada; pode gerar cobrança de API.')
        try:
            from theme_research import enrich_from_transcripts
            from translation_context import save_context
            profile=enrich_from_transcripts(profile,corpus,emit,cancelled);save_context(project,profile);on_theme(profile)
        except Exception as exc:
            if cancelled():raise
            emit('AVISO: pesquisa indisponível; contexto cadastrado preservado. '+str(exc))
        config['context_profile']=profile
    for index,(stem,record) in enumerate(records.items(),1):
        wait()
        if cancelled():raise RuntimeError('Preparação cancelada; resultados concluídos preservados.')
        emit(f'PREPARAÇÃO 3/3: traduzindo {index}/{len(records)} — '+stem)
        try:
            text,language=translation.generate_text(audios[stem],texts.get(stem) or Path(text_root)/(stem+'.txt'),project,stem,{**config,'_prepared_transcription':record},emit,cancelled,on_progress=lambda stage,fraction:on_progress(stem,stage,fraction))
            emit('TRADUÇÃO PRONTA: '+stem);prepared[stem]=(text,language);record.update(translated=text,language=language);checkpoint(stem)
        except Exception as exc:
            if cancelled():raise
            errors[stem]=str(exc);emit('REVISAR TEXTO '+stem+': '+str(exc))
    emit(f'PREPARAÇÃO CONCLUÍDA: {len(prepared)} textos prontos; {len(errors)} pendências. Agora pode iniciar a síntese.')
    return prepared,errors
