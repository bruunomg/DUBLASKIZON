from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import struct, wave, random
from audio_clip_timeline import AudioClip,split_clip,move_clip,render_clips
from audio_player import AudioPlayerManager

# Split is sample-exact and never removes audio, including stereo frame boundaries.
for channels in (1,2):
 for width in (1,2,3,4):
  fb=channels*width
  raw=bytes(range(1,81))*fb
  whole=(AudioClip(1,0,raw),)
  split=split_clip(whole,23,fb)
  assert render_clips(split,fb,width)==raw
  for bad in (0,80,100):
   try:split_clip(whole,bad,fb)
   except ValueError:pass
   else:raise AssertionError('invalid split accepted')
  moved=move_clip(split,split[1].id,40,fb)
  result=render_clips(moved,fb,width)
  assert result[23*fb:40*fb]==(b'\x80' if width==1 else b'\x00')*(17*fb)
  assert result[:23*fb]==raw[:23*fb] and result[40*fb:]==raw[23*fb:]

# Cross a neighbor in both directions, preserving bytes and unique IDs.
clips=tuple(AudioClip(i+1,i*10,bytes([i+1])*10) for i in range(3))
right=move_clip(clips,1,20,1)
assert [c.id for c in right]==[2,3,1]
left=move_clip(clips,3,0,1)
assert [c.id for c in left]==[3,1,2]
unequal=(AudioClip(1,0,b"a"), AudioClip(2,1,b"b"*100))
assert [c.id for c in move_clip(unequal,2,0,1)]==[2,1]
rng=random.Random(1234)
for _ in range(200):
 clips=move_clip(clips,rng.choice(clips).id,rng.randrange(0,80),1)
 assert sorted((c.id,c.pcm) for c in clips)==[(1,b'\x01'*10),(2,b'\x02'*10),(3,b'\x03'*10)]
 assert all(a.end(1)<=b.start for a,b in zip(clips,clips[1:]))
 render_clips(clips,1,1)
try:render_clips((AudioClip(1,10000,b'x'),),1,1,maximum_bytes=100)
except ValueError:pass
else:raise AssertionError('memory guard failed')

class Canvas:
 def winfo_width(self):return 1004
 def focus_set(self):pass
 def delete(self,*a):pass
 def configure(self,**kw):pass
 def create_rectangle(self,*a,**kw):pass
 def create_text(self,*a,**kw):pass

with TemporaryDirectory() as tmp:
 root=Path(tmp)
 audio=root/'dublado'/'cena.wav';audio.parent.mkdir()
 raw=b''.join(struct.pack('<h',i%30000) for i in range(4000))
 with wave.open(str(audio),'wb') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(1000);w.writeframes(raw)
 m=AudioPlayerManager(None,root)
 m.stop=lambda **kw:None
 m._set_audio_edit_status=lambda text:None
 m._update_mode_buttons=lambda:None
 m._current_audio_path=lambda kind:audio if kind=='dubbed' else None
 track=m._load_edit_track('dubbed')
 m.audio_edit_base_frames={'dubbed':raw}
 m.audio_edit_mode=True
 m._refresh_waveforms()
 m.waveform_selection_kind='dubbed';m.waveform_selection_ranges['dubbed']=(2,2)
 m._split_dubbed_clip()
 assert len(m._track_clips(track))==2 and track['frames']==raw and m.audio_edit_dirty
 m._undo_audio_edit();assert len(m._track_clips(track))==1 and not m.audio_edit_dirty
 m._redo_audio_edit();assert len(m._track_clips(track))==2 and m.audio_edit_dirty
 m.clip_timeline_canvas=Canvas()
 # 4 sec content -> 5 sec visible. Grab second part at 2.5 s and move +1 s.
 m._clip_drag_press(SimpleNamespace(x=502))
 assert m.clip_drag is not None
 m._clip_drag_motion(SimpleNamespace(x=702))
 m._clip_drag_release(SimpleNamespace(x=702))
 assert track['frames']==raw[:4000]+b'\x00'*2000+raw[4000:]
 assert m.audio_edit_dirty
 final=track['frames'];layout=m._track_clips(track)
 m._undo_audio_edit();assert track['frames']==raw and len(m._track_clips(track))==2
 m._redo_audio_edit();assert track['frames']==final and m._track_clips(track)==layout
 m._save_audio_edit()
 assert not m.audio_edit_dirty
 with wave.open(str(audio),'rb') as w:assert w.readframes(w.getnframes())==final
 assert (root/'revisoes'/'.dublaskizon_trechos.json').is_file()
 m.audio_edit_working={}
 loaded=m._load_edit_track('dubbed')
 assert m._track_clips(loaded)==layout
 # Existing cut/paste operations retain undo of clip boundaries and protect ORIGINAL.
 m._focused_waveform_kind=lambda:'dubbed'
 m.waveform_selection_kind='dubbed';m.waveform_selection_ranges['dubbed']=(0,0.5)
 m._cut_audio_selection()
 assert len(loaded['frames'])==len(final)-1000
 m._undo_audio_edit();assert loaded['frames']==final and m._track_clips(loaded)==layout
 m.waveform_selection_kind='dubbed';m.waveform_selection_ranges['dubbed']=(0,0)
 m._paste_audio_clip();assert len(loaded['frames'])==len(final)+1000
 assert len(m._track_clips(loaded))==len(layout)+1
 assert all(any(c.id==old.id and c.pcm==old.pcm for c in m._track_clips(loaded)) for old in layout)
 pasted_layout=m._track_clips(loaded)
 m._save_clip_layout(loaded)
 restored=dict(loaded);restored.pop('clips',None)
 m._load_clip_layout(restored);assert m._track_clips(restored)==pasted_layout
 m._undo_audio_edit();assert loaded['frames']==final and m._track_clips(loaded)==layout
 # PCM changes invalidate stale metadata; untrusted non-object JSON is ignored.
 changed=dict(loaded,frames=b'\x00'*len(final));changed.pop('clips',None)
 m._load_clip_layout(changed);assert 'clips' not in changed
 metadata=root/'revisoes'/'.dublaskizon_trechos.json'
 metadata.write_text('[]',encoding='utf-8')
 changed=dict(loaded);changed.pop('clips',None)
 m._load_clip_layout(changed);assert 'clips' not in changed
 m.audio_edit_mode=False
 before=loaded['frames'];m._split_dubbed_clip();m._clip_drag_press(SimpleNamespace(x=400))
 assert loaded['frames']==before and m.clip_drag is None
print('OK: sample-exact split, stereo/8-32bit, silence, reordering, drag handlers, undo/redo, WAV save, persistent layout, stale metadata, edit-mode and memory guards.')

# A bar click selects without moving; Delete and Cut preserve all remaining IDs.
m=AudioPlayerManager(None)
m.stop=lambda **kw:None
m._set_audio_edit_status=lambda text:None
layout=tuple(AudioClip(i+1,i*10,bytes([i+1,0])*10) for i in range(3))
raw=render_clips(layout,2,2)
track=dict(frames=raw,channels=1,sample_width=2,sample_rate=10,clips=layout,saved_clips=layout)
m.audio_edit_working={'dubbed':track};m.audio_edit_base_frames={'dubbed':raw}
m.audio_edit_mode=True;m.waveform_reference_duration=3.75
m.clip_timeline_canvas=Canvas()
m._refresh_waveforms=lambda:None
m._clip_drag_press(SimpleNamespace(x=402))
assert m._clip_is_selected(layout[1],track)
assert not m._clip_is_selected(layout[0],track)
m._clip_drag_release(SimpleNamespace(x=403))
assert track['frames']==raw and not m.audio_edit_dirty
assert m._clip_is_selected(layout[1],track)
assert m._selection_dark_color('#15803D')=='#0a401e'
m._copy_audio_selection();assert m.audio_clip_buffer['frames']==layout[1].pcm
m._delete_audio_selection()
assert [c.id for c in track['clips']]==[1,3]
assert track['frames']==layout[0].pcm+layout[2].pcm
assert m.audio_clip_buffer['frames']==layout[1].pcm
m._undo_audio_edit();assert track['clips']==layout and track['frames']==raw
m._redo_audio_edit();assert [c.id for c in track['clips']]==[1,3]
m._undo_audio_edit()
m.waveform_selection_kind='dubbed';m.waveform_selection_ranges['dubbed']=(1.2,1.6)
m._delete_audio_selection()
assert len(track['clips'])==4
assert track['clips'][0]==layout[0] and track['clips'][-1].id==3
assert render_clips(track['clips'],2,2)==track['frames']
m._undo_audio_edit();assert track['clips']==layout
m.waveform_selection_kind='dubbed';m.waveform_selection_ranges['dubbed']=(1,2)
m._cut_audio_selection();assert [c.id for c in track['clips']]==[1,3]
assert m.audio_clip_buffer['frames']==layout[1].pcm
print('OK: click selects/darkens, mouse jitter does not move, selected-clip Delete, partial Delete, Cut, clipboard and undo/redo preserve boundaries.')
