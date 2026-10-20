"""Guided API setup shared by translation and semantic review."""
import queue,threading
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
import semantic_review as api
import api_configuration as config_tools
from ui_theme import theme_dialog,apply_button_style

KEY_PORTALS={'openai':'https://platform.openai.com/api-keys','claude':'https://platform.claude.com/settings/keys','gemini':'https://aistudio.google.com/apikey'}

def open_key_portal(provider):
    name='gemini' if provider.startswith('Gemini') else 'claude' if provider.startswith('Claude') else 'openai' if provider.startswith(('OpenAI','Luna','Sol','Codex','GPT')) else None
    if not name:return False
    import webbrowser
    webbrowser.open(KEY_PORTALS[name]);return True

def configure(parent,theme=None,on_saved=None,luna_callback=None,local_callback=None,context_callback=None,provider=None):
    window=tk.Toplevel(parent);window.title('Configurar APIs — importar .env, chave e modelos');window.geometry('1140x830');window.minsize(1000,760);window.transient(parent)
    frame=ttk.Frame(window,padding=14);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='TRADUÇÃO / REVISÃO — CONFIGURAÇÃO DAS APIs',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=6)
    ttk.Label(frame,text='1. Importe o .env ou cole a chave secreta completa.  2. Consulte os modelos da conta.  3. Teste o modelo e salve.\nNome/ID da chave não é modelo. Os campos abaixo mostram os nomes equivalentes das variáveis do .env.',wraplength=1020).pack(anchor='w',pady=5)
    values=api.settings();fields={key:tk.StringVar(window,value=values[key]) for key in api.DEFAULTS}
    for name,label in [('openai','OpenAI'),('claude','Claude'),('gemini','Gemini')]:fields[name+'_key']=tk.StringVar(window,value=api.load_key(label))
    status=tk.StringVar(window,value='Chave salva localmente não significa autenticação verificada. CONSULTAR MODELOS valida a consulta sem gerar texto.')
    # Reserve the footer before the notebook, so saving remains visible at smaller sizes.
    footer=ttk.Frame(frame);footer.pack(side='bottom',fill='x',pady=8)
    ttk.Label(frame,text='Chaves protegidas neste Windows, fora do projeto/ZIP. Consultas de modelos não geram tradução. O login dos aplicativos não configura a API.',wraplength=1020).pack(side='bottom',fill='x',pady=4)
    ttk.Label(frame,textvariable=status,wraplength=1020).pack(side='bottom',fill='x',pady=7)
    notebook=ttk.Notebook(frame);notebook.pack(fill='both',expand=True,pady=8)
    boxes={};pages={};operations={};after_ids=set()
    def button(parent,label,callback):
        widget=tk.Button(parent,text=label,command=callback,relief='flat',font=('Segoe UI',9),padx=9,pady=7);apply_button_style(widget,theme or {},'secondary');return widget
    def persist(clear_invalid=False):
        clean={key:fields[key].get() for key in api.DEFAULTS};removed=False
        for name in ('openai','claude','gemini'):
            clean[name+'_base']=config_tools.normalize_base(name,clean[name+'_base'])
            for field in (('openai_model','codex_model') if name=='openai' else (name+'_model',)):
                if not clean[field].strip():continue
                try:clean[field]=config_tools.validate_model(clean[field],fields[name+'_key'].get(),config_tools.official_base(clean[name+'_base']))
                except ValueError as exc:
                    if not clear_invalid:raise ValueError(('Modelo Codex' if field=='codex_model' else 'Modelo '+name)+': '+str(exc)) from None
                    fields[field].set('');clean[field]='';removed=True
        api.save_settings(clean,fields['openai_key'].get(),fields['claude_key'].get(),fields['gemini_key'].get())
        if on_saved:on_saved()
        return removed
    def activate(name):
        if not fields[name+'_key'].get().strip():status.set('Cole o valor secreto completo no campo de chave, ou importe o .env.');return
        try:removed=persist(True)
        except (ValueError,RuntimeError,OSError) as exc:status.set(str(exc));return
        status.set('Chave salva e ativada localmente; ainda não verificada. Clique em CONSULTAR MODELOS. '+('Um campo de modelo inválido foi limpo: escolha um nome de modelo, não o ID da chave.' if removed else ''))
    def import_file(name):
        file=filedialog.askopenfilename(parent=window,title='Importar configuração .env (o arquivo não será alterado)',filetypes=[('Configuração .env','*.env'),('Todos os arquivos','*.*')])
        if not file:return
        try:data=config_tools.import_env(file,name)
        except (ValueError,OSError,UnicodeError) as exc:status.set(str(exc));return
        for key,value in data.items():
            if key in fields:fields[key].set(value)
        status.set(f'{len(data)} campos importados do .env. Chaves continuam ocultas. Confira os modelos, consulte a conta e salve; o arquivo original não foi alterado.')
    def export_file(name):
        try:content=config_tools.export_env({key:fields[key].get() for key in api.DEFAULTS},name)
        except ValueError as exc:status.set(str(exc));return
        file=filedialog.asksaveasfilename(parent=window,title='Exportar parâmetros .env — sem chave secreta',initialfile=name+'.env',defaultextension='.env',filetypes=[('Configuração .env','*.env')])
        if not file:return
        try:
            from pathlib import Path
            Path(file).write_text(content,encoding='utf-8')
        except OSError:status.set('Não foi possível salvar o arquivo .env.');return
        status.set('Parâmetros exportados sem chave secreta. As credenciais continuam protegidas neste Windows.')

    def query(name,model_field=None):
        key=fields[name+'_key'].get().strip();base=fields[name+'_base'].get()
        try:
            base=config_tools.normalize_base(name,base)
            if not key:raise ValueError('Cole a chave secreta completa, ou importe o .env, antes de consultar.')
            model=config_tools.validate_model(fields[model_field].get(),key,config_tools.official_base(base)) if model_field else None
        except ValueError as exc:status.set(str(exc));return
        for widget in operations[name]:widget.configure(state='disabled')
        status.set('Testando conexão e modelo…' if model_field else 'Validando a chave e consultando os modelos da conta…')
        messages=queue.Queue()
        def worker():
            try:
                result=config_tools.test_model(name,base,key,model) if model_field else config_tools.list_models(name,base,key)
                messages.put(('ok',result))
            except (ValueError,RuntimeError) as exc:messages.put(('error',str(exc)))
            except Exception:messages.put(('error','Não foi possível concluir a consulta. Confira o endereço e a conexão; nenhuma tradução foi gerada.'))
        def poll():
            if not window.winfo_exists():return
            try:kind,result=messages.get_nowait()
            except queue.Empty:
                after_ids.add(window.after(100,poll));return
            for widget in operations[name]:widget.configure(state='normal')
            try:current_base=config_tools.normalize_base(name,fields[name+'_base'].get())
            except ValueError:current_base=''
            if fields[name+'_key'].get().strip()!=key or current_base!=base:
                status.set('A chave ou URL foi alterada durante a consulta. Consulte novamente a configuração atual.');return
            if kind=='error':status.set(result);return
            if model_field:status.set(result);return
            ids=result['models']
            for field in (('openai_model','codex_model') if name=='openai' else (name+'_model',)):
                candidates=[item for item in ids if 'codex' in item.lower()] if field=='codex_model' else ids
                boxes[field].configure(values=candidates or ids)
                if fields[field].get() and fields[field].get() not in ids:fields[field].set('')
            status.set(f'Consulta autenticada: {len(ids)} modelos retornados'+(' (lista parcial)' if result['partial'] else '')+'. Selecione o modelo na lista e use TESTAR ESTE MODELO. A listagem não comprova saldo nem suporte a geração de texto.')
        threading.Thread(target=worker,daemon=True).start();after_ids.add(window.after(100,poll))
    specs_by_provider={
        'openai':[('openai_base','URL base da API\nOPENAI_BASE_URL'),('openai_key','Chave secreta completa\nOPENAI_API_KEY'),('openai_model','Modelo GPT / ChatGPT\nOPENAI_MODEL'),('codex_model','Modelo da opção Codex\nCODEX_MODEL')],
        'claude':[('claude_base','URL base da API\nANTHROPIC_BASE_URL'),('claude_key','Chave secreta completa\nANTHROPIC_API_KEY'),('claude_model','Modelo Claude\nANTHROPIC_MODEL')],
        'gemini':[('gemini_base','URL base da API\nGEMINI_BASE_URL'),('gemini_key','Chave secreta completa\nGEMINI_API_KEY'),('gemini_model','Modelo Gemini\nGEMINI_MODEL')]}
    for name,label in [('openai','OpenAI / GPT / Codex'),('claude','Claude'),('gemini','Gemini')]:
        page=ttk.Frame(notebook,padding=12);notebook.add(page,text=label);pages[name]=page;operations[name]=[]
        specs=specs_by_provider[name]
        for index,(field,caption) in enumerate(specs):
            ttk.Label(page,text=caption,width=29).grid(row=index,column=0,sticky='w',pady=6)
            box=ttk.Combobox(page,textvariable=fields[field],values=config_tools.MODEL_EXAMPLES.get(field,()),width=43) if field.endswith('_model') else ttk.Entry(page,textvariable=fields[field],show='•' if field.endswith('_key') else '')
            box.grid(row=index,column=1,sticky='ew',padx=(0,8),pady=6);boxes[field]=box
            if field.endswith('_key'):button(page,'LINK ADQUIRIR CHAVE DA API',lambda p=label:open_key_portal(p)).grid(row=index,column=2,pady=6)
            elif field.endswith('_model'):
                check=button(page,'TESTAR ESTE MODELO',lambda n=name,f=field:query(n,f));check.grid(row=index,column=2,sticky='ew',pady=6);operations[name].append(check)
            else:button(page,'RESTAURAR URL PADRÃO',lambda n=name:fields[n+'_base'].set(api.DEFAULTS[n+'_base'])).grid(row=index,column=2,sticky='ew',pady=6)
        page.columnconfigure(1,weight=1)
        row=ttk.Frame(page);row.grid(row=len(specs),column=0,columnspan=3,sticky='ew',pady=10)
        button(row,'IMPORTAR .env',lambda n=name:import_file(n)).pack(side='left',padx=3)
        button(row,'EXPORTAR .env',lambda n=name:export_file(n)).pack(side='left',padx=3)
        button(row,'ATIVAR CHAVE',lambda n=name:activate(n)).pack(side='left',padx=3)
        check=button(row,'CONSULTAR MODELOS',lambda n=name:query(n));check.pack(side='left',padx=3);operations[name].append(check)
        button(row,'LIMPAR CHAVE',lambda n=name:fields[n+'_key'].set('')).pack(side='left',padx=3)
        controls=ttk.LabelFrame(page,text='Parâmetros de execução — compartilhados pelas APIs',padding=6);controls.grid(row=len(specs)+1,column=0,columnspan=3,sticky='ew',pady=4)
        for column,(field,label) in enumerate([('batch_size','Itens/lote BATCH_SIZE'),('max_batches','Limite MAX_BATCHES (0=livre)'),('max_retries','Repetições MAX_RETRIES'),('request_timeout','Tempo REQUEST_TIMEOUT (s)')]):
            cell=ttk.Frame(controls);cell.grid(row=0,column=column,sticky='ew',padx=4);controls.columnconfigure(column,weight=1)
            ttk.Label(cell,text=label).pack(anchor='w')
            low,high,default=config_tools.PARAMETERS[field];ttk.Spinbox(cell,textvariable=fields[field],from_=low,to=high,width=10).pack(fill='x')
        hint=('Exemplos de formato: OPENAI_MODEL=gpt-4.1-mini e CODEX_MODEL=gpt-5-codex. São exemplos, sem garantia de acesso na conta.\nTambém importa OPENAI_CODEX_MODEL, LUNA_TRANSLATION_MODEL e SOL_REVIEW_MODEL. Uma chave serve aos dois campos OpenAI; cada campo contém o nome de um modelo.' if name=='openai' else 'Importe as variáveis do provedor ou cole a chave secreta. Consulte a lista para preencher o modelo disponível na sua conta.')
        ttk.Label(page,text=hint,wraplength=940,justify='left').grid(row=len(specs)+2,column=0,columnspan=3,sticky='w',pady=8)
    for label,callback in [('CHAVE / LUNA / SOL',luna_callback),('FERRAMENTAS LOCAIS / BAIXAR',local_callback),('TEMA / CONTEXTO',context_callback)]:
        if callback:button(footer,label,callback).pack(side='left',padx=3)
    def save():
        try:persist()
        except (ValueError,RuntimeError,OSError) as exc:messagebox.showerror('Configuração de APIs',str(exc),parent=window);return
        window.destroy()
    button(footer,'SALVAR E ATIVAR',save).pack(side='right',padx=3)
    def destroyed(event):
        if event.widget is not window:return
        for timer in after_ids:
            try:window.after_cancel(timer)
            except tk.TclError:pass
    window.bind('<Destroy>',destroyed,add='+')
    if provider:notebook.select(2 if provider.startswith('Gemini') else 1 if provider.startswith('Claude') else 0)
    for field in ('openai_model','codex_model','claude_model','gemini_model'):
        if not fields[field].get():continue
        name='openai' if field=='codex_model' else field.split('_')[0]
        try:config_tools.validate_model(fields[field].get(),fields[name+'_key'].get(),config_tools.official_base(fields[name+'_base'].get()))
        except ValueError:status.set('A configuração anterior tem um campo de modelo inválido. Importe o .env ou selecione o nome do modelo; nome/ID da chave não é modelo.');break
    theme_dialog(window,theme)
    return window
