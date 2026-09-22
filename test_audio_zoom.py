from types import SimpleNamespace
from audio_player import AudioPlayerManager
from audio_clip_timeline import AudioClip

class Canvas:
 def __init__(self):self.left=0.;self.extent=1004;self.rectangles=[]
 def winfo_width(self):return 1004
 def winfo_height(self):return 62
 def configure(self,**kw):
  if 'scrollregion' in kw:self.extent=kw['scrollregion'][2]
 def canvasx(self,x):return self.left*self.extent+x
 def xview_moveto(self,fraction):self.left=max(0,min(fraction,1-1004/self.extent))
 def xview(self,*args):
  if args and args[0]=='moveto':self.xview_moveto(float(args[1]))
  return self.left,min(1,self.left+1004/self.extent)
 def delete(self,*args):pass
 def create_line(self,*args,**kw):pass
 def create_text(self,*args,**kw):pass
 def create_rectangle(self,*args,**kw):self.rectangles.append(args)
 def create_oval(self,*args,**kw):pass
 def tag_lower(self,*args):pass
 def focus_set(self):pass

m=AudioPlayerManager(None)
m._set_audio_edit_status=lambda text:None;m.stop=lambda **kw:None
m.waveform_canvases={'original':Canvas(),'dubbed':Canvas()};m.clip_timeline_canvas=Canvas()
m.waveform_data={k:{'duration':10.,'samples':[.2]*5600} for k in ('original','dubbed')}
m.waveform_reference_duration=10
assert m._waveform_x_to_seconds('dubbed',502)==5
m._set_waveform_zoom(4,m.waveform_canvases['dubbed'],502)
assert abs(m._waveform_x_to_seconds('dubbed',502)-5)<.01
assert m._waveform_plot_width('dubbed',1004)==4000
assert len({round(c.xview()[0],6) for c in m._audio_view_canvases()})==1
m._scroll_audio_views('moveto',.5)
assert abs(m._waveform_x_to_seconds('dubbed',2)-5.005)<.01
m.audio_edit_mode=True
clips=(AudioClip(1,0,b'\x01\x00'*5000),AudioClip(2,5000,b'\x02\x00'*5000))
track=dict(frames=clips[0].pcm+clips[1].pcm,channels=1,sample_width=2,sample_rate=1000,clips=clips)
m.audio_edit_working={'dubbed':track};m.audio_edit_base_frames={'dubbed':track['frames']}
# Under zoom and scroll, click at six seconds, split there, and grab that exact clip.
m._on_waveform_press('dubbed',SimpleNamespace(x=400))
assert abs(m.waveform_selection_ranges['dubbed'][0]-6)<.01
m._on_waveform_release('dubbed',SimpleNamespace(x=400))
m._split_dubbed_clip()
assert len(track['clips'])==3
assert abs(track['clips'][2].start-6000)<3
m._clip_drag_press(SimpleNamespace(x=450))
assert m.clip_drag['id']==track['clips'][2].id
clip_id=m.clip_drag['id'];old_start=track['clips'][2].start;shift=round(40*m.clip_drag['scale'])
m._clip_drag_release(SimpleNamespace(x=490))
assert next(c.start for c in track['clips'] if c.id==clip_id)==old_start+shift
m._undo_audio_edit()
original=track['frames']
m._zoom_audio_wheel(SimpleNamespace(widget=m.waveform_canvases['dubbed'],x=400,delta=120))
assert m.waveform_zoom==5 and track['frames']==original
m._set_waveform_zoom(1);assert m.waveform_scroll==0
before=m._waveform_plot_width('dubbed',1004)
m._set_waveform_zoom(.5);assert m._waveform_plot_width('dubbed',1004)==before*.5
m._set_waveform_zoom(999);assert m.waveform_zoom==8
m._set_waveform_zoom(.001);assert m.waveform_zoom==.125
print('OK: synchronized zoom and scroll, pointer anchor, time mapping, split/clip picking after scrolling, Ctrl+wheel, reset/limits; PCM unchanged.')

m.waveform_zoom_slider=Canvas()
m._zoom_slider_pointer(SimpleNamespace(widget=m.waveform_zoom_slider,x=502))
assert m.waveform_zoom==1
m._zoom_slider_pointer(SimpleNamespace(widget=m.waveform_zoom_slider,x=990))
assert m.waveform_zoom==8
m._zoom_slider_pointer(SimpleNamespace(widget=m.waveform_zoom_slider,x=14))
assert m.waveform_zoom==.125
print('OK: circular slider center=100%, right=increase, left=decrease.')
