"""Shared scene ruler and bounded mouse-wheel navigation."""
import math
import tkinter as tk

class WaveformNavigation:
    def __init__(self, player, parent):
        self.player=player;self.seconds=None;self.scene=player.current_context_key
        self.canvas=tk.Canvas(parent,height=27,highlightthickness=0,bg=player.theme.get('input','#FFFFFF'),cursor='crosshair')
        self.canvas.pack(fill='x',pady=(1,0))
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<Button-1>',self.select)
        self.canvas.bind('<B1-Motion>',self.select)
        player._bind_audio_zoom(self.canvas)
    def extent(self):
        return max(.001,float(self.player.waveform_reference_duration or 0))
    def select(self,event):
        p=self.player;c=self.canvas
        width=max(180,c.winfo_width())
        scale=(width-4)*getattr(p,'waveform_zoom',1)
        self.seconds=min(self.extent(),max(0,(c.canvasx(event.x)-2)/scale*self.extent()))
        p.stop(announce=False)
        if p.audio_edit_mode:
            p.waveform_selection_kind='dubbed'
            p.waveform_selection_ranges['dubbed']=(self.seconds,self.seconds)
            p.selected_clip_ids=set()
            p._update_audio_edit_buttons()
        for kind in p.waveform_canvases:p._draw_waveform(kind)
        self.draw()
        return 'break'
    def draw(self):
        p=self.player;c=self.canvas
        if self.scene!=p.current_context_key:self.scene=p.current_context_key;self.seconds=None
        p._configure_audio_view(c);c.delete('all')
        width=max(180,c.winfo_width());scale=(width-4)*getattr(p,'waveform_zoom',1)/self.extent()
        desired=65/max(scale,.001);power=10**math.floor(math.log10(max(desired,.001)))
        step=next(v*power for v in (1,2,5,10) if v*power>=desired)
        start=max(0,c.canvasx(0)-2)/scale;end=min(self.extent(),max(0,c.canvasx(width)-2)/scale)
        fg=p.theme.get('text','#FFFFFF')
        for i in range(max(0,math.floor(start/step)),math.ceil(end/step)+1):
            sec=i*step;x=2+sec*scale
            c.create_line(x,18,x,27,fill=fg)
            label=f'{sec:.1f}s' if step<1 else f'{int(sec)//60:02d}:{int(sec)%60:02d}'
            c.create_text(x+3,8,text=label,fill=fg,anchor='w',font=('Segoe UI',7))
        if self.seconds is not None:
            x=2+self.seconds*scale
            c.create_line(x,0,x,27,fill='#F97316',width=2,tags='scene_cursor')
            c.create_polygon(x-5,0,x+5,0,x,6,fill='#F97316',tags='scene_cursor')
    def mark(self,kind):
        p=self.player;c=p.waveform_canvases.get(kind)
        if c is None:return
        c.delete('scene_cursor')
        if self.seconds is None:return
        width=max(180,c.winfo_width());x=2+self.seconds/self.extent()*(width-4)*getattr(p,'waveform_zoom',1)
        c.create_line(x,0,x,c.winfo_height(),fill='#F97316',width=2,dash=(4,2),tags='scene_cursor')

def scroll_vertical(player,*args):
    view=getattr(player,'waveform_vertical_view',None)
    if view is None or not view.winfo_exists():return
    bounds=view.bbox('all')
    # Canvas can scroll even when its contents fit: explicitly pin it to the top.
    if not bounds or bounds[3]-bounds[1] <= max(1,view.winfo_height())+1:
        view.yview_moveto(0)
    elif args:
        view.yview(*args)


def wheel(player,event):
    if getattr(event,'state',0)&4:return player._zoom_audio_wheel(event)
    delta=getattr(event,'delta',0)
    direction=(-1 if delta>0 else 1) if delta else (-1 if getattr(event,'num',0)==4 else 1)
    if getattr(event,'state',0)&1:
        player._scroll_audio_views('scroll',direction*3,'units')
    else:
        scroll_vertical(player,'scroll',direction*3,'units')
    return 'break'

def bind_wheel(player,widget):
    for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):
        widget.bind(sequence,lambda event:wheel(player,event))
    for child in widget.winfo_children():bind_wheel(player,child)
