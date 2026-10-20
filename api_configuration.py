"""Safe configuration parsing and read-only API diagnostics (no inference calls)."""
import json,re,shlex,urllib.request,urllib.error,urllib.parse
from pathlib import Path

MODEL_EXAMPLES={'openai_model':('gpt-4.1-mini',),'codex_model':('gpt-5-codex',)}
ENV_ALIASES={
 'BATCH_SIZE':'batch_size','MAX_BATCHES':'max_batches','MAX_RETRIES':'max_retries','REQUEST_TIMEOUT':'request_timeout',
 'OPENAI_API_KEY':'openai_key','OPENAI_BASE_URL':'openai_base','OPENAI_API_BASE':'openai_base',
 'OPENAI_MODEL':'openai_model','OPENAI_CHATGPT_MODEL':'openai_model','LUNA_TRANSLATION_MODEL':'openai_model',
 'CODEX_MODEL':'codex_model','OPENAI_CODEX_MODEL':'codex_model','SOL_REVIEW_MODEL':'codex_model',
 'ANTHROPIC_API_KEY':'claude_key','CLAUDE_API_KEY':'claude_key','ANTHROPIC_BASE_URL':'claude_base','CLAUDE_BASE_URL':'claude_base','ANTHROPIC_MODEL':'claude_model','CLAUDE_MODEL':'claude_model',
 'GEMINI_API_KEY':'gemini_key','GOOGLE_API_KEY':'gemini_key','GEMINI_BASE_URL':'gemini_base','GOOGLE_BASE_URL':'gemini_base','GEMINI_MODEL':'gemini_model','GOOGLE_MODEL':'gemini_model'}

def provider_name(value):
    return 'gemini' if value.lower().startswith(('gemini','google')) else 'claude' if value.lower().startswith(('claude','anthropic')) else 'openai'

def import_env(path,provider='openai'):
    path=Path(path)
    if path.stat().st_size>1_000_000:raise ValueError('Arquivo .env muito grande; selecione somente a configuração de APIs.')
    raw={}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if line.startswith('export '):line=line[7:].strip()
        if not line or line.startswith('#') or '=' not in line:continue
        name,value=line.split('=',1);name=name.strip()
        if name not in ENV_ALIASES and name not in ('API_KEY','BASE_URL','API_BASE_URL','MODEL'):continue
        try:
            lexer=shlex.shlex(value,posix=True);lexer.whitespace_split=True;lexer.commenters='#'
            parts=list(lexer)
        except ValueError:raise ValueError('Há uma variável com aspas incompletas no .env; confira o arquivo.') from None
        if len(parts)>1:raise ValueError('Uma variável de API tem espaços sem aspas; confira o .env.')
        raw[name]=parts[0] if parts else ''
    result={}
    # Generic names apply only to the selected provider. Specific variables override aliases.
    name=provider_name(provider)
    for source,target in [('API_KEY',name+'_key'),('BASE_URL',name+'_base'),('API_BASE_URL',name+'_base'),('MODEL',name+'_model' if name!='openai' else 'openai_model')]:
        if source in raw:result[target]=raw[source]
    for source,target in ENV_ALIASES.items():
        if source in raw:result[target]=raw[source]
    for source,target in [('OPENAI_MODEL','openai_model'),('CODEX_MODEL','codex_model'),('OPENAI_CODEX_MODEL','codex_model'),('ANTHROPIC_API_KEY','claude_key'),('GEMINI_API_KEY','gemini_key')]:
        if source in raw:result[target]=raw[source]
    if 'codex_model' not in result and 'openai_model' in result:result['codex_model']=result['openai_model']
    result={key:value for key,value in result.items() if value.strip()}
    if not result:raise ValueError('Nenhuma variável de API reconhecida. Use OPENAI_API_KEY, OPENAI_MODEL, CODEX_MODEL, ANTHROPIC_API_KEY ou GEMINI_API_KEY.')
    return result

def validate_model(value,key='',official=True):
    if not isinstance(value,str) or not value.strip():raise ValueError('Escolha um ID de modelo no campo Modelo; use CONSULTAR MODELOS ou importe o .env.')
    value=value.strip()
    if value==key.strip() or value.startswith(('sk-','AIza','OPENAI_API_KEY=','ANTHROPIC_API_KEY=','GEMINI_API_KEY=')):
        raise ValueError('O campo Modelo contém uma chave ou variável. Cole a chave somente em Chave secreta e escolha o nome do modelo no campo Modelo.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}',value):raise ValueError('ID de modelo inválido. Use o nome exato retornado pela consulta, sem espaços ou aspas.')
    if official and re.fullmatch(r'[A-Za-z0-9]{12,}',value):raise ValueError('O campo Modelo parece conter um identificador de chave. Escolha o nome do modelo em CONSULTAR MODELOS; não use o nome/ID da chave.')
    return value

def normalize_base(name,value):
    from transcription_backend import validate_base
    value=validate_base(value.strip());parsed=urllib.parse.urlsplit(value)
    if parsed.hostname in ('platform.openai.com','developers.openai.com','chatgpt.com','claude.ai','aistudio.google.com'):
        raise ValueError('Este é o site de cadastro, não a URL da API. Use RESTAURAR URL PADRÃO nesta guia.')
    for suffix in ('/responses','/messages','/models'):
        if value.endswith(suffix):value=value[:-len(suffix)]
    if parsed.hostname=='api.openai.com' and value=='https://api.openai.com':value+='/v1'
    return value

def model_field(provider):return 'gemini_model' if provider_name(provider)=='gemini' else 'claude_model' if provider_name(provider)=='claude' else 'codex_model' if 'codex' in provider.lower() else 'openai_model'

def official_base(value):return urllib.parse.urlsplit(value).hostname in ('api.openai.com','api.anthropic.com','generativelanguage.googleapis.com')

def http_message(code,operation='consulta da API'):
    reasons={401:'A chave secreta foi recusada. Confira se copiou o valor completo, e não o nome/ID da chave, e se ela pertence a este provedor.',403:'A conta/chave não tem permissão para este recurso; confira permissões e restrições do projeto.',404:'O endereço ou modelo não foi encontrado, ou não está acessível para a conta. Restaure a URL padrão e consulte os modelos.',429:'O provedor limitou a consulta ou a cota/saldo da API. Confira a conta antes de repetir.'}
    return f'HTTP {code} — {operation}: '+reasons.get(code,'O provedor recusou a solicitação. Confira endereço e disponibilidade do serviço.')

def _get(name,base,key,resource,opener):
    if not key.strip():raise ValueError('Cole a chave secreta completa no campo protegido antes de consultar.')
    if '\n' in key or '\r' in key or '=' in key and key.strip().startswith(('OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY')):raise ValueError('Cole somente o valor da chave secreta, ou use IMPORTAR .env.')
    headers={'x-goog-api-key':key.strip()} if name=='gemini' else {'x-api-key':key.strip(),'anthropic-version':'2023-06-01'} if name=='claude' else {'Authorization':'Bearer '+key.strip()}
    request=urllib.request.Request(base+resource,headers=headers)
    try:
        with opener(request,timeout=20) as response:
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise RuntimeError('Resposta da API extensa demais; consulta interrompida.')
            data=json.loads(raw)
    except urllib.error.HTTPError as exc:raise RuntimeError(http_message(exc.code)) from None
    except (urllib.error.URLError,TimeoutError):raise RuntimeError('Não foi possível conectar à API. Confira a conexão e a URL; nenhuma tradução foi solicitada.') from None
    except (ValueError,UnicodeError):raise RuntimeError('A URL não retornou JSON de uma API. Confira a URL base; ela não é a página de cadastro.') from None
    if not isinstance(data,dict):raise RuntimeError('O provedor retornou uma resposta de consulta inválida.')
    return data

def list_models(provider,base,key,opener=None):
    name=provider_name(provider);base=normalize_base(name,base);opener=opener or urllib.request.urlopen;models=[];token='';partial=False
    for page in range(5):
        params={'pageSize':1000} if name=='gemini' else {'limit':100}
        if token:params['pageToken' if name=='gemini' else 'after_id' if name=='claude' else 'after']=token
        # OpenAI /models has no list pagination arguments.
        if name=='openai':params={}
        data=_get(name,base,key,'/models'+('?'+urllib.parse.urlencode(params) if params else ''),opener)
        items=data.get('models' if name=='gemini' else 'data')
        if not isinstance(items,list):raise RuntimeError('O provedor não retornou uma lista de modelos. Confira a URL base.')
        for item in items:
            if not isinstance(item,dict):continue
            if name=='gemini' and 'generateContent' not in item.get('supportedGenerationMethods',[]):continue
            value=item.get('name' if name=='gemini' else 'id')
            if isinstance(value,str) and value.strip():models.append(value.removeprefix('models/'))
        token=str(data.get('nextPageToken') or '') if name=='gemini' else str(data.get('last_id') or '') if data.get('has_more') else ''
        if not token or name=='openai':break
        partial=page==4
    return {'models':sorted(set(models)),'partial':partial}

def test_model(provider,base,key,model,opener=None):
    name=provider_name(provider);base=normalize_base(name,base);model=validate_model(model,key,official_base(base))
    if name=='gemini':model=model.removeprefix('models/')
    data=_get(name,base,key,'/models/'+urllib.parse.quote(model,safe=''),opener or urllib.request.urlopen)
    actual=data.get('name' if name=='gemini' else 'id','')
    if str(actual).removeprefix('models/')!=model:raise RuntimeError('O provedor não confirmou o modelo selecionado. Consulte novamente os modelos.')
    return 'Consulta aceita: chave e modelo encontrados. Isto não testa geração, saldo nem compatibilidade completa; nenhum texto foi traduzido.'


PARAMETERS={'batch_size':(1,32,8),'max_batches':(0,100000,0),'max_retries':(0,3,0),'request_timeout':(10,600,90)}

def execution_parameters(values):
    result={}
    for name,(low,high,default) in PARAMETERS.items():
        try:value=int(values.get(name,default))
        except (ValueError,TypeError):raise ValueError(name.upper()+' precisa ser um número inteiro.') from None
        if not low<=value<=high:raise ValueError(name.upper()+f' precisa estar entre {low} e {high}.')
        result[name]=value
    return result

def export_env(values,provider):
    name=provider_name(provider);parameters=execution_parameters(values)
    fields=[('OPENAI_BASE_URL','openai_base'),('OPENAI_MODEL','openai_model'),('CODEX_MODEL','codex_model'),('LUNA_TRANSLATION_MODEL','openai_model'),('SOL_REVIEW_MODEL','codex_model')] if name=='openai' else [('ANTHROPIC_BASE_URL','claude_base'),('ANTHROPIC_MODEL','claude_model')] if name=='claude' else [('GEMINI_BASE_URL','gemini_base'),('GEMINI_MODEL','gemini_model')]
    lines=['# Parâmetros Dublaskizon. Exportado sem chaves secretas.','# MAX_BATCHES=0: sem limite; MAX_RETRIES=0: sem repetir chamadas de geração.']
    key='OPENAI_API_KEY' if name=='openai' else 'ANTHROPIC_API_KEY' if name=='claude' else 'GEMINI_API_KEY'
    lines.append(key+'=')
    for env,field in fields:lines.append(env+'='+shlex.quote(str(values.get(field,''))))
    for field,value in parameters.items():lines.append(field.upper()+'='+str(value))
    return '\n'.join(lines)+'\n'
