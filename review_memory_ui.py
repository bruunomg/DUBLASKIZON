"""Compact manual-review cache controls; status comes from the worker protocol."""
import tkinter as tk
from tkinter import ttk,messagebox


def context_active(app):
    try:
        if app.current_tab_key() in ('review','text_to_speech'):return True
    except (AttributeError,tk.TclError):pass
    for name in ('batch_app','review_app','personalized_app'):
        owner=getattr(app,name,None)
        for candidate in (owner,getattr(owner,'review_app',None),getattr(owner,'scene_review',None)):
            player=getattr(candidate,'audio_player',None)
            window=getattr(player,'window',None)
            if window is not None:
                try:
                    if window.winfo_exists():return True
                except tk.TclError:pass
    return False


def short_status(state):
    if not state['enabled']:return 'DESLIGANDO • APÓS ESTA FALA' if state['active'] else 'DESLIGADO'
    if state.get('preloading'):return 'PREPARANDO CLONAGEM + DUBLAGEM'
    if state['preparing']:return 'TRANSCRIÇÃO / TRADUÇÃO'
    if state.get('model_ready'):
        return ('EM USO' if state['active'] else ('PRONTO' if state.get('asr_ready') else 'SÍNTESE PRONTA'))+f" • PID {state['pid']}"
    if state['active']:return 'CARREGANDO / GERANDO'
    reason=state['reason'].lower()
    if 'falha na pré-carga' in reason:return 'PRÉ-CARGA INDISPONÍVEL • ⚙'
    if 'ram' in reason:return 'LIBERADO • POUCA RAM'
    if 'transcri' in reason:return 'LIBERADO • TRADUÇÃO'
    if 'inatividade' in reason:return 'LIBERADO • PRAZO'
    return 'AGUARDANDO REDUBLAGEM'


def mount_controls(app,parent,cache,before_refresh=True,scene=False):
    # cache is passed explicitly so tests and alternate hosts use the same owner.
    frame=tk.Frame(parent,bg='#172033')
    if before_refresh:frame.pack(side='left',before=app.refresh_screen_button,padx=(12,8))
    else:frame.pack(side='left',padx=(4,6))
    if not hasattr(app,'review_memory_var'):app.review_memory_var=tk.BooleanVar(master=app.root,value=cache.enabled)
    caption=tk.StringVar(value='MOTOR NA MEMÓRIA\n'+short_status(cache.snapshot()))
    def toggle():
        cache.set_enabled(app.review_memory_var.get())
        if app.review_memory_var.get():
            batch=getattr(app,'batch_app',None)
            provider=getattr(batch,'selected_model_id',None)
            if callable(provider):cache.preload(provider())
    memory_button=tk.Checkbutton(frame,textvariable=caption,variable=app.review_memory_var,
        command=toggle,bg='#172033',fg='white',selectcolor='#0F766E',
        activebackground='#172033',activeforeground='white',font=('Segoe UI',7,'bold'),padx=3,pady=2,
        wraplength=220,justify='left')
    memory_button.pack(side='left')
    memory_settings=tk.Button(frame,text='⚙',command=lambda:settings_window(app.root,cache),
        bg='#334155',fg='white',font=('Segoe UI',11,'bold'),relief='flat',padx=5)
    memory_settings.pack(side='left',padx=(4,0))
    frame.memory_button=memory_button;frame.memory_settings=memory_settings
    if before_refresh:app.review_memory_button=memory_button;app.review_memory_settings=memory_settings
    def poll():
        frame.memory_poll_job=None
        if not frame.winfo_exists():return
        cache.set_review_context(scene or context_active(app))
        if app.review_memory_var.get()!=cache.enabled:app.review_memory_var.set(cache.enabled)
        caption.set('MOTOR NA MEMÓRIA\n'+short_status(cache.snapshot()))
        frame.memory_poll_job=frame.after(1000,poll)
    frame.memory_poll_job=frame.after(250,poll)
    def cleanup(event):
        if event.widget is frame and frame.memory_poll_job is not None:
            try:frame.after_cancel(frame.memory_poll_job)
            except tk.TclError:pass
            frame.memory_poll_job=None
    frame.bind('<Destroy>',cleanup,add='+')
    return frame


def mount_scene_controls(player,parent):
    from warm_inference import review_memory_cache
    root=player.parent
    while getattr(root,'master',None) is not None:root=root.master
    app=getattr(root,'_dublaskizon_app',None)
    if app is None:
        from types import SimpleNamespace
        app=getattr(root,'_dublaskizon_memory_owner',None)
        if app is None:
            app=SimpleNamespace(root=root,batch_app=getattr(player,'translation_controller',None))
            root._dublaskizon_memory_owner=app
    return mount_controls(app,parent,review_memory_cache,before_refresh=False,scene=True)


def settings_window(parent,cache):
    window=tk.Toplevel(parent);window.title('Motor na memória — retenção e estado real')
    window.geometry('680x640');window.minsize(620,580)
    frame=ttk.Frame(window,padding=14);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='RETENÇÃO DO MOTOR OMNIVOICE',font=('Segoe UI',11,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Ao ativar, prepara síntese e conferência já instaladas, sem baixar novos modelos.\nPerfil pronto: sem prazo, desde a primeira fala e retenção durante a Revisão.',wraplength=600).pack(anchor='w',pady=8)
    form=ttk.Frame(frame);form.pack(fill='x')
    variables={}
    for row,(key,label,low,high) in enumerate([
        ('idle_minutes','Liberar após minutos sem uso (0 = sem prazo)',0,1440),
        ('min_scenes','Fora da Revisão: reconhecer sequência após N dublagens',1,100),
        ('reserve_mb','Reserva de RAM livre (MB; pressão passageira tem tolerância de 30 s)',1024,8192)]):
        variables[key]=tk.StringVar(value=str(cache.config[key]))
        ttk.Label(form,text=label,wraplength=430).grid(row=row,column=0,sticky='w',pady=5)
        ttk.Spinbox(form,from_=low,to=high,textvariable=variables[key],width=7).grid(row=row,column=1,padx=8)
    keep=tk.BooleanVar(value=cache.config['keep_while_review'])
    ttk.Checkbutton(frame,text='Não esvaziar por tempo enquanto a Revisão / Ouvir cena estiver aberta',variable=keep).pack(anchor='w',pady=10)
    state_var=tk.StringVar(window)
    ttk.Label(frame,textvariable=state_var,wraplength=600,justify='left').pack(fill='x',pady=10)
    ttk.Label(frame,text='Pouca RAM, desligamento, troca de motor e transcrição/tradução podem liberar o motor.\nA transcrição e o tradutor têm modelos próprios. Compare o PID do Python no Gerenciador;\nos valores GPU acima são do PyTorch, não o consumo total do sistema.',wraplength=620).pack(anchor='w')
    def save():
        try:
            cache.configure({**{key:value.get() for key,value in variables.items()},'keep_while_review':keep.get()})
            window.destroy()
        except (OSError,ValueError) as exc:messagebox.showerror('Motor na memória',str(exc),parent=window)
    ttk.Button(frame,text='SALVAR REGULAGENS',command=save).pack(side='bottom',anchor='e',pady=8)
    def poll():
        if not window.winfo_exists():return
        state=cache.snapshot()
        state_var.set(short_status(state)+f"\nRevisão detectada: {'SIM' if state['review_context'] else 'NÃO'} | Dublagens concluídas nesta sessão: {state['completed']}"+
                      f"\nSíntese: {'carregada' if state.get('model_ready') else 'não carregada'} | Conferência: {'carregada' if state.get('asr_ready') else 'sob demanda'}"+
                      f"\nGPU alocada: {state.get('gpu_allocated',0)/1024**2:.0f} MB | Reservada pelo PyTorch: {state.get('gpu_reserved',0)/1024**2:.0f} MB"+
                      '\nÚltima liberação: '+state['reason'])
        window.after(1000,poll)
    poll()
    return window
