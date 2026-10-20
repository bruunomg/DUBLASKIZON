"""Bounded public-web discovery; snippets are attributed, never treated as official localization."""
import datetime,html,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from html.parser import HTMLParser

class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)

def plain(value):
    parser=PlainText();parser.feed(str(value));return ' '.join(' '.join(parser.parts).split())

def search(title,opener=None,cancelled=lambda:False,queries=None,max_documents=8):
    opener=opener or urllib.request.urlopen;documents=[];seen=set();errors=[]
    queries=queries or [title+' official story characters terminology',title+' português localização glossário termos']
    for query in queries:
        if cancelled():raise RuntimeError('Pesquisa cancelada.')
        url='https://www.bing.com/search?format=rss&'+urllib.parse.urlencode({'q':query})
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'Dublaskizon/87.98 contextual research'})
            with opener(request,timeout=15) as response:raw=response.read(500001)
            if len(raw)>500000:raise ValueError('Resposta extensa')
            root=ET.fromstring(raw)
            for item in root.findall('./channel/item')[:6]:
                link=(item.findtext('link') or '').strip();heading=plain(item.findtext('title') or '');description=plain(item.findtext('description') or '')
                parsed=urllib.parse.urlsplit(link)
                if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or link in seen:continue
                # Require meaningful title overlap, retaining edition ambiguity for AI review.
                words=set(re.findall(r'\w{3,}',title.casefold()))-{'the','and','jogo','game','filme','book'}
                if not relevant(title,heading+' '+description):continue
                if len(description)<35:continue
                seen.add(link);documents.append(heading+'\n'+link+'\n[Resumo do mecanismo de busca, não página integral; não comprova tradução oficial.]\n'+description[:1000])
        except (OSError,ValueError,ET.ParseError):errors.append('Busca web indisponível para uma consulta.')
    return documents[:max_documents],errors

def collect(title,cancelled=lambda:False,opener=None):
    from translation_context import research_theme
    documents,errors=search(title,opener,cancelled)
    try:wiki=research_theme(title,opener=opener)
    except RuntimeError as exc:wiki='';errors.append(str(exc))
    if cancelled():raise RuntimeError('Pesquisa cancelada.')
    if not documents and not wiki:raise RuntimeError('Nenhuma fonte acessível. Confira o título e a conexão; nenhuma regra foi alterada.')
    header='Pesquisa multifuente: '+title+'\nConsulta UTC: '+datetime.datetime.now(datetime.timezone.utc).isoformat()+'\nCompare obra/edição e sentidos. Resumos web e fontes comunitárias não comprovam localização oficial.\n\n'
    # Reserve room for both discovery and encyclopedic references within the existing model budget.
    return header+'\n\n'.join(documents)[:6500]+('\n\n'+wiki[:3000] if wiki else '')+('\n\nLimitações: '+' '.join(errors) if errors else '')


def collect_deep(title,cancelled=lambda:False,emit=lambda text:None,opener=None,focus=None):
    """Search independent categories rather than relying on a single generic synopsis."""
    from translation_context import research_theme
    aspects=focus or ['official exact edition setting dialogue terminology','gameplay transcript subtitles enemies recurring dialogue names','items objects materials abilities glossary meanings','localização português brasileiro legendas termos do jogo','terminology differences adaptations game television book localization','glossary ambiguous words in universe dialogue' ]
    documents=[];errors=[];seen=set()
    for index,aspect in enumerate(aspects[:6]):
        if cancelled():raise RuntimeError('Pesquisa cancelada.')
        emit(f'PESQUISA: fontes {index+1}/{min(6,len(aspects))} — '+aspect)
        items,failures=search(title,opener,cancelled,queries=['"'+title+'" '+aspect],max_documents=5)
        for item in items:
            url=item.split('\n')[1]
            if url not in seen:seen.add(url);documents.append(item)
        errors.extend(failures)
    if focus is None:
        try:
            wiki=research_theme(title,opener=opener)
            documents.extend(part for part in wiki.split('\n\n') if 'https://' in part)
        except RuntimeError:errors.append('Referências Wikipedia indisponíveis.')
    if not documents:raise RuntimeError('Nenhuma fonte acessível para aprofundar o tema. Confira título/edição e conexão.')
    documents=read_documents(title,documents,cancelled,emit,opener)
    header='Pesquisa aprofundada: '+title+'\nConsulta UTC: '+datetime.datetime.now(datetime.timezone.utc).isoformat()+'\nResumos web são referências parciais; não comprovam localização oficial.'
    return header+'\n\n'+'\n\n'.join(documents[:24])+('\n\nLimitações: '+'; '.join(sorted(set(errors))) if errors else '')


def relevant(title,text):
    words=set(re.findall(r'\w{3,}',title.casefold()))-{'the','and','jogo','game','filme','book'}
    found=set(re.findall(r'\w{3,}',text.casefold()))
    return not words or len(words & found)/len(words)>=.6

class ArticleText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','nav','footer','header','noscript'):self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','nav','footer','header','noscript'):self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden and data.strip():self.parts.append(data.strip())

def public_url(url):
    import socket,ipaddress
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):raise ValueError('Endereço público HTTPS inválido.')
    addresses=socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):raise ValueError('Endereço não público recusado.')
    return url

class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def read_documents(title,documents,cancelled,emit,opener=None):
    # Small bounded retrieval; keep attributed summaries when a site refuses reading.
    result=[];read=0
    page_opener=opener or urllib.request.build_opener(PublicRedirect()).open
    for document in documents:
        if cancelled():raise RuntimeError('Pesquisa cancelada.')
        if read>=6:result.append(document);continue
        lines=document.split('\n');url=lines[1] if len(lines)>1 else ''
        if not url.startswith('https://'):result.append(document);continue
        read+=1
        try:
            public_url(url)
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Dublaskizon contextual research'})
            with page_opener(request,timeout=10) as response:
                public_url(response.geturl() if hasattr(response,'geturl') else url)
                raw=response.read(350001)
            if len(raw)>350000:raise ValueError('Página extensa demais.')
            parser=ArticleText();parser.feed(raw.decode('utf-8',errors='replace'));text=' '.join(parser.parts)
            if len(text)<150 or not relevant(title,text):raise ValueError('Conteúdo não corresponde à obra.')
            # Keep excerpts around the work name and terminology, not only the site navigation.
            anchors=[m.start() for m in re.finditer(re.escape(title.split(':')[0]),text,re.I)][:3]
            excerpt=' […] '.join(text[max(0,i-180):i+1600] for i in anchors) if anchors else text[:4200]
            result.append(lines[0]+'\n'+url+'\n[Extrato da página lida; pode ser fonte comunitária e não comprova localização oficial por si só.]\n'+excerpt[:4500])
            emit('PESQUISA: página lida — '+url)
        except (OSError,ValueError):result.append(document)
    return result
