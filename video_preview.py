"""Player integrado ao Tk no Windows; FFplay embutido e busca visual via FFmpeg."""
from __future__ import annotations
import base64
import ctypes
import os
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
import tkinter as tk
try:
    from .duration_converter_tab import executable_path
    from .ui_theme import apply_button_style
except ImportError:
    from duration_converter_tab import executable_path
    from ui_theme import apply_button_style


def clock_text(seconds):
    seconds=max(0,int(seconds));hours,rest=divmod(seconds,3600);minutes,seconds=divmod(rest,60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'


def timeline_position(x,width,duration):
    return max(0.0,min(1.0,(x-12)/max(1,width-24)))*max(0,duration)


def frame_command(ffmpeg,path,seconds,width,height):
    return [str(ffmpeg),'-hide_banner','-loglevel','error','-nostdin','-ss',str(max(0,seconds)),'-i',str(path),
            '-an','-sn','-frames:v','1','-vf',f'scale={max(2,width)}:{max(2,height)}:force_original_aspect_ratio=decrease',
            '-f','image2pipe','-c:v','png','pipe:1']


class WindowsVideoHost:
    """Não altera janelas alheias: somente o PID iniciado por este player."""
    def __init__(self):
        if os.name!='nt':raise RuntimeError('O player integrado requer Windows.')
        from ctypes import wintypes as w
        self.w=w;self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.callback=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
        signatures={'EnumWindows':([self.callback,w.LPARAM],w.BOOL),
            'GetWindowThreadProcessId':([w.HWND,ctypes.POINTER(w.DWORD)],w.DWORD),
            'SetParent':([w.HWND,w.HWND],w.HWND),'GetParent':([w.HWND],w.HWND),
            'GetWindowTextW':([w.HWND,w.LPWSTR,ctypes.c_int],ctypes.c_int),
            'SetWindowPos':([w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT],w.BOOL),
            'MoveWindow':([w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.BOOL],w.BOOL),
            'ShowWindow':([w.HWND,ctypes.c_int],w.BOOL),
            'PostMessageW':([w.HWND,w.UINT,w.WPARAM,w.LPARAM],w.BOOL),
            'IsWindow':([w.HWND],w.BOOL)}
        for name,(args,result) in signatures.items():
            fn=getattr(self.user,name);fn.argtypes=args;fn.restype=result
        long_type=ctypes.c_ssize_t
        suffix='PtrW' if ctypes.sizeof(ctypes.c_void_p)==8 else 'W'
        self.get_style=getattr(self.user,'GetWindowLong'+suffix);self.get_style.argtypes=[w.HWND,ctypes.c_int];self.get_style.restype=long_type
        self.set_style=getattr(self.user,'SetWindowLong'+suffix);self.set_style.argtypes=[w.HWND,ctypes.c_int,long_type];self.set_style.restype=long_type
    def find(self,pid):
        found=[]
        @self.callback
        def visit(hwnd,param):
            current=self.w.DWORD();self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(current))
            if current.value==pid:
                title=ctypes.create_unicode_buffer(512);self.user.GetWindowTextW(hwnd,title,512)
                if title.value.startswith('Dublaskizon integrado '):found.append(hwnd);return False
            return True
        self.user.EnumWindows(visit,0)
        return found[0] if found else None
    def embed(self,hwnd,parent,width,height):
        self.user.ShowWindow(hwnd,0)
        style=self.get_style(hwnd,-16)
        # WS_CHILD, retirando borda, legenda, WS_POPUP e moldura redimensionável.
        self.set_style(hwnd,-16,(style & ~0x80CF0000) | 0x40000000)
        self.user.SetParent(hwnd,parent)
        if self.user.GetParent(hwnd)!=parent:raise OSError('Não foi possível integrar a tela do vídeo.')
        self.user.SetWindowPos(hwnd,None,0,0,max(2,width),max(2,height),0x0034)
        self.resize(hwnd,width,height);self.user.ShowWindow(hwnd,5)
    def resize(self,hwnd,width,height):
        if hwnd and self.user.IsWindow(hwnd):self.user.MoveWindow(hwnd,0,0,max(2,width),max(2,height),True)
    def pause(self,hwnd):
        if not hwnd or not self.user.IsWindow(hwnd):return False
        result=self.user.PostMessageW(hwnd,0x100,ord('P'),1)
        self.user.PostMessageW(hwnd,0x101,ord('P'),0xC0000001)
        return bool(result)


class VideoPreview:
    def __init__(self,owner,path):
        self.owner=owner;self.path=Path(path);self.playlist=list(owner.files)
        if self.path not in self.playlist:self.playlist.append(self.path)
        self.index=self.playlist.index(self.path);self.process=None;self.hwnd=None;self.closed=False
        self.paused=True;self.duration=0.;self.current=0.;self.start_time=0.;self.dragging=False
        self.serial=0;self.media_serial=0;self.frame_serial=0;self.resume_after_seek=False
        self.events=queue.Queue();self.frame_requests=queue.Queue(maxsize=1);self.decoder=None;self.decoder_lock=threading.Lock()
        self.ffmpeg=executable_path('ffmpeg',owner.project_root);self.ffprobe=executable_path('ffprobe',owner.project_root)
        self.ffplay=executable_path('ffplay',owner.project_root)
        self.native=WindowsVideoHost()
        self.window=tk.Toplevel(owner.root);self.window.title('VISUALIZAR VÍDEO');self.window.geometry('1060x740');self.window.minsize(640,420)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.title=tk.Label(self.window,font=('Segoe UI',11,'bold'),anchor='w',padx=16,pady=12)
        self.title.pack(fill='x')
        self.surface=tk.Frame(self.window,bg='#000000');self.surface.pack(fill='both',expand=True,padx=12)
        self.canvas=tk.Canvas(self.surface,bg='#000000',highlightthickness=0)
        self.canvas.place(relwidth=1,relheight=1)
        self.surface.bind('<Configure>',self.resize)
        self.timeline=tk.Canvas(self.window,height=36,highlightthickness=0,cursor='hand2');self.timeline.pack(fill='x',padx=12,pady=(10,0))
        self.timeline.bind('<Button-1>',self.begin_seek);self.timeline.bind('<B1-Motion>',self.drag_seek);self.timeline.bind('<ButtonRelease-1>',self.end_seek)
        self.timeline.bind('<Configure>',lambda event:self.draw_timeline())
        self.time_var=tk.StringVar(value='00:00:00 / 00:00:00');self.status=tk.StringVar(value='Carregando vídeo...')
        self.times=tk.Label(self.window,textvariable=self.time_var,anchor='e',padx=18);self.times.pack(fill='x')
        self.controls=tk.Frame(self.window);self.controls.pack(fill='x',padx=12,pady=10)
        self.buttons=[]
        def button(text,command,role='secondary'):
            widget=tk.Button(self.controls,text=text,command=command,relief='flat',padx=14,pady=9,cursor='hand2')
            widget.pack(side='left',padx=3);self.buttons.append((widget,role));return widget
        self.previous_button=button('◀ ANTERIOR',lambda:self.navigate(-1))
        self.play_button=button('▶ PLAY',self.play,'success');button('Ⅱ PAUSE',self.pause,'teal')
        self.next_button=button('PRÓXIMO ▶',lambda:self.navigate(1))
        button('FECHAR',self.close,'danger')
        self.status_label=tk.Label(self.window,textvariable=self.status,anchor='w',padx=16,pady=6);self.status_label.pack(fill='x')
        self.window.bind('<space>',lambda event:self.toggle())
        self.window.bind('<Left>',lambda event:self.seek_to(self.current-5,not self.paused))
        self.window.bind('<Right>',lambda event:self.seek_to(self.current+5,not self.paused))
        self.apply_theme(owner.theme)
        threading.Thread(target=self.frame_worker,daemon=True).start()
        self.window.update_idletasks()
        self.load(self.index)
        self.window.after(30,self.poll)
    def apply_theme(self,theme):
        self.theme=theme or {};bg=self.theme.get('surface','#172033');fg=self.theme.get('text','#F1F5F9')
        self.window.configure(bg=bg);self.controls.configure(bg=bg);self.timeline.configure(bg=bg)
        for widget in (self.title,self.times,self.status_label):widget.configure(bg=bg,fg=fg)
        for button,role in self.buttons:apply_button_style(button,self.theme,role)
        self.draw_timeline()
    def load(self,index):
        with self.decoder_lock:
            if self.decoder is not None and self.decoder.poll() is None:self.decoder.kill()
        self.stop();self.media_serial+=1;self.frame_serial+=1;self.index=index;self.path=self.playlist[index]
        self.duration=0.;self.current=0.;self.start_time=0.;self.paused=True;self.dragging=False
        self.canvas.delete('all');self.image=None
        self.title.configure(text=f'{index+1}/{len(self.playlist)}   {self.path.name}')
        self.window.title('VISUALIZAR VÍDEO — '+self.path.name)
        self.previous_button.configure(state='normal' if index>0 else 'disabled')
        self.next_button.configure(state='normal' if index+1<len(self.playlist) else 'disabled')
        self.status.set('Carregando vídeo...');self.draw_timeline()
        generation=self.media_serial;path=self.path
        threading.Thread(target=self.probe,args=(generation,path),daemon=True).start()
        self.request_frame(0)
    def probe(self,generation,path):
        try:
            if not self.ffprobe:raise RuntimeError('Use PREPARAR FERRAMENTAS para instalar FFprobe.')
            try:from .video_converter_tab import probe_video
            except ImportError:from video_converter_tab import probe_video
            data=probe_video(self.ffprobe,path)
            self.events.put(('probe',generation,data))
        except Exception as exc:self.events.put(('error',generation,str(exc)))
    def navigate(self,offset):
        index=self.index+offset
        if 0<=index<len(self.playlist):self.load(index)
    def stop(self):
        self.serial+=1;process=self.process;self.process=None;self.hwnd=None
        if process is not None:
            if process.poll() is None:process.kill()
            threading.Thread(target=process.wait,daemon=True).start()
        self.paused=True
    def play(self):
        if self.dragging:return
        if self.process is not None and self.process.poll() is None:
            if self.paused and self.hwnd and self.native.pause(self.hwnd):self.paused=False;self.status.set('Reproduzindo')
            return
        self.start_playback(0 if self.duration and self.current>=self.duration-.05 else self.current)
    def start_playback(self,seconds):
        if not self.ffplay:self.status.set('Use PREPARAR FERRAMENTAS para instalar FFplay.');return
        self.stop();self.current=self.clamp(seconds);self.paused=False
        try:
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
            command=[str(self.ffplay),'-hide_banner','-loglevel','info','-stats','-autoexit','-noborder',
                '-ss',str(self.current),'-window_title',f'Dublaskizon integrado {id(self)}',
                '-x',str(max(2,self.surface.winfo_width())),'-y',str(max(2,self.surface.winfo_height())),str(self.path)]
            self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW,bufsize=0)
            self.attach_deadline=time.monotonic()+12
            threading.Thread(target=self.read_player,args=(self.process,self.serial),daemon=True).start()
            self.status.set('Abrindo vídeo integrado...')
        except Exception as exc:self.stop();self.status.set(str(exc))
    def read_player(self,process,generation):
        buffer='';last=''
        try:
            while True:
                raw=process.stderr.read(1024)
                if not raw:break
                buffer+=raw.decode('utf-8',errors='replace')
                parts=re.split('[\r\n]',buffer);buffer=parts.pop()
                for line in parts:
                    match=re.match(r'\s*(-?\d+\.\d+)\s+[AMV]-[AVM]:',line)
                    if match:self.events.put(('clock',generation,float(match.group(1))))
                    elif line.strip():last=line[-700:]
            code=process.wait();self.events.put(('exit',generation,code,last))
        finally:process.stderr.close()
    def pause(self):
        if self.process is not None and not self.paused and self.hwnd and self.native.pause(self.hwnd):
            self.paused=True;self.status.set('Pausado')
    def toggle(self):
        if self.paused:self.play()
        else:self.pause()
        return 'break'
    def clamp(self,seconds):
        return max(0,min(float(seconds),max(0,self.duration-.025))) if self.duration else max(0,float(seconds))
    def seek_to(self,seconds,resume=False):
        self.stop();self.current=self.clamp(seconds);self.frame_serial+=1;self.draw_timeline()
        self.request_frame(self.current)
        if resume:self.start_playback(self.current)
        else:self.status.set('Pausado — '+clock_text(self.current))
    def begin_seek(self,event):
        if not self.duration:return 'break'
        self.resume_after_seek=not self.paused;self.dragging=True;self.stop();self.timeline.grab_set()
        self.drag_seek(event);return 'break'
    def drag_seek(self,event):
        if not self.dragging:return 'break'
        self.current=self.clamp(timeline_position(event.x,self.timeline.winfo_width(),self.duration))
        self.draw_timeline();self.request_frame(self.current);self.status.set('Buscando — '+clock_text(self.current))
        return 'break'
    def end_seek(self,event):
        if not self.dragging:return 'break'
        self.drag_seek(event);self.dragging=False;self.timeline.grab_release()
        self.seek_to(self.current,self.resume_after_seek);return 'break'
    def request_frame(self,seconds):
        if not self.ffmpeg:return
        request=(self.media_serial,self.frame_serial,self.path,seconds,min(1280,max(320,self.surface.winfo_width())),min(720,max(180,self.surface.winfo_height())))
        try:self.frame_requests.get_nowait()
        except queue.Empty:pass
        try:self.frame_requests.put_nowait(request)
        except queue.Full:pass
    def frame_worker(self):
        while not self.closed:
            try:request=self.frame_requests.get(timeout=.2)
            except queue.Empty:continue
            media,frame,path,seconds,width,height=request
            try:
                with self.decoder_lock:
                    if self.closed:return
                    process=subprocess.Popen(frame_command(self.ffmpeg,path,seconds,width,height),stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    self.decoder=process
                try:data,error=process.communicate(timeout=12)
                except subprocess.TimeoutExpired:process.kill();process.communicate();continue
                finally:
                    with self.decoder_lock:
                        if self.decoder is process:self.decoder=None
                if process.returncode==0 and data:self.events.put(('frame',media,frame,data))
            except Exception as exc:self.events.put(('error',media,str(exc)))
    def resize(self,event=None):
        if self.hwnd:self.native.resize(self.hwnd,self.surface.winfo_width(),self.surface.winfo_height())
        elif getattr(self,'image',None) is not None:
            self.canvas.coords('image',self.surface.winfo_width()/2,self.surface.winfo_height()/2)
    def draw_timeline(self):
        if not hasattr(self,'timeline'):return
        width=max(24,self.timeline.winfo_width());fraction=min(1,self.current/self.duration) if self.duration else 0
        x=12+(width-24)*fraction;self.timeline.delete('all')
        self.timeline.create_line(12,18,width-12,18,fill=self.theme.get('border','#475569'),width=6,capstyle='round')
        self.timeline.create_line(12,18,x,18,fill='#38BDF8',width=6,capstyle='round')
        self.timeline.create_oval(x-7,11,x+7,25,fill='#38BDF8',outline='')
        self.time_var.set(f'{clock_text(self.current)} / {clock_text(self.duration)}')
    def poll(self):
        if self.closed:return
        try:
            while True:
                item=self.events.get_nowait();kind=item[0]
                if kind=='probe' and item[1]==self.media_serial:
                    self.duration=item[2]['duration']
                    try:self.start_time=float(item[2]['video'].get('start_time',0))
                    except (ValueError,TypeError):self.start_time=0.
                    self.status.set('Pronto — PLAY para reproduzir; clique ou arraste a linha para buscar.');self.draw_timeline()
                elif kind=='frame' and item[1]==self.media_serial and item[2]==self.frame_serial and self.hwnd is None:
                    self.image=tk.PhotoImage(data=base64.b64encode(item[3]).decode('ascii'),format='png')
                    self.canvas.delete('all');self.canvas.create_image(self.surface.winfo_width()/2,self.surface.winfo_height()/2,image=self.image,tags='image')
                elif kind=='clock' and item[1]==self.serial and not self.dragging:
                    self.current=max(0,min(self.duration or float('inf'),item[2]-self.start_time));self.draw_timeline()
                elif kind=='exit' and item[1]==self.serial:
                    self.process=None;self.hwnd=None;self.paused=True
                    self.status.set('Reprodução encerrada.' if item[2]==0 else 'Erro: '+item[3]);self.request_frame(self.current)
                elif kind=='error' and item[1]==self.media_serial:self.status.set(item[2])
        except queue.Empty:pass
        if self.process is not None and self.hwnd is None:
            hwnd=self.native.find(self.process.pid)
            if hwnd:
                try:
                    self.native.embed(hwnd,self.surface.winfo_id(),self.surface.winfo_width(),self.surface.winfo_height())
                    self.hwnd=hwnd;self.status.set('Reproduzindo');self.window.focus_set()
                except Exception as exc:self.stop();self.status.set(str(exc))
            elif time.monotonic()>self.attach_deadline:self.stop();self.status.set('Não foi possível integrar o vídeo. Verifique o FFplay em PREPARAR FERRAMENTAS.')
        self.window.after(30,self.poll)
    def close(self):
        if self.closed:return
        self.closed=True;self.stop()
        with self.decoder_lock:
            if self.decoder is not None and self.decoder.poll() is None:self.decoder.kill()
        self.window.destroy()
