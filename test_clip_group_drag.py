from types import SimpleNamespace
from audio_clip_timeline import AudioClip,move_clip_group,render_clips
from audio_player import AudioPlayerManager
layout=tuple(AudioClip(i+1,i*20,b'\1\0'*10) for i in range(4))
for ids in ({1,2,3,4},{1,3}):
 for delta in (-100,-5,5,35):
  result=move_clip_group(layout,ids,delta,2);render_clips(result,2,2)
  applied=max(delta,-min(c.start for c in layout if c.id in ids))
  for c in result:
   original=next(v for v in layout if v.id==c.id)
   assert c.pcm==original.pcm
   if c.id in ids:assert c.start==original.start+applied
class Canvas:
 def winfo_width(self):return 804
 def focus_set(self):pass
 def canvasx(self,x):return x+100
m=AudioPlayerManager(None);m.stop=lambda **kw:None;m._draw_waveform=lambda *a:None;m._draw_clip_timeline=lambda *a:None;m._refresh_waveforms=lambda:None;m._set_audio_edit_status=lambda *a:None
m.audio_edit_mode=True;raw=render_clips(layout,2,2);track=dict(frames=raw,clips=layout,channels=1,sample_width=2,sample_rate=10)
m.audio_edit_working={'dubbed':track};m.audio_edit_base_frames={'dubbed':raw};m.clip_timeline_canvas=Canvas();m.waveform_zoom=2;m._clip_timeline_seconds=lambda:8
m._select_all_dubbed_clips()
m._clip_drag_press(SimpleNamespace(x=-48,state=0))
assert m.selected_clip_ids=={1,2,3,4}
m._clip_drag_release(SimpleNamespace(x=152,state=0))
assert [c.start for c in track['clips']]==[10,30,50,70]
assert m.selected_clip_ids=={1,2,3,4}
m._undo_audio_edit();assert track['clips']==layout and track['frames']==raw
m._redo_audio_edit();assert [c.start for c in track['clips']]==[10,30,50,70]
print('OK: group direction, spacing, zero boundary, noncontiguous selection, collisions, zoom/scroll drag, retained selection and undo/redo.')
