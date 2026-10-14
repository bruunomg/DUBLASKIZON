import math
import numpy as np
import audio_player as player
from audio_clip_timeline import AudioClip,render_clips
from types import SimpleNamespace
from unittest.mock import patch

def encode(a,width):
 a=np.asarray(a,dtype=np.int64)
 if width==1:return (a+128).astype('u1').tobytes()
 if width==3:return np.stack([((a>>(8*b))&255) for b in range(3)],axis=1).astype('u1').tobytes()
 return a.astype('<i'+str(width)).tobytes()
def decode(raw,width):
 if width==1:return np.frombuffer(raw,'u1').astype('i8')-128
 if width==3:
  a=np.frombuffer(raw,'u1').reshape(-1,3).astype('i8');v=a[:,0]|a[:,1]<<8|a[:,2]<<16
  return (v^0x800000)-0x800000
 return np.frombuffer(raw,'<i'+str(width)).astype('i8')
for width in (1,2,3,4):
 maximum=2**(width*8-1)-1
 a=np.rint(np.sin(np.arange(4800)*2*np.pi*440/24000)*maximum*.2).astype('i8')
 samples=np.stack((a,a//2),axis=1).ravel();raw=encode(samples,width)
 track=dict(frames=raw,channels=2,sample_width=width,sample_rate=24000)
 for db in (-1,1):
  out,clips,applied=player.process_scene_volume(track,db)
  assert len(out)==len(raw) and track['frames']==raw
  assert abs(applied-db)<1e-8
  assert np.max(abs(decode(out,width)-samples*10**(db/20)))<=.501
 # Saturation protection and silent input.
 near=dict(track,frames=encode([-maximum//2,maximum//2]*100,width))
 out,_,applied=player.process_scene_volume(near,24)
 assert 0<applied<24 and max(abs(decode(out,width)))<=math.floor(maximum*10**(-1/20))
 loud=dict(track,frames=encode([-maximum,maximum]*10,width))
 out,_,applied=player.process_scene_volume(loud,1);assert out==loud['frames'] and applied==0
 silent=dict(track,frames=encode([0]*20,width))
 out,_,applied=player.process_scene_volume(silent,1);assert out==silent['frames'] and applied==0
for invalid in (float('nan'),float('inf'),25):
 try:player.process_scene_volume(track,invalid)
 except ValueError:pass
 else:raise AssertionError(invalid)
width=2;raw=encode([0,2000,-2000,0]*100,2)
layout=(AudioClip(7,0,raw),AudioClip(19,600,raw))
segmented=dict(frames=render_clips(layout,2,2),clips=layout,channels=1,sample_width=2,sample_rate=24000)
out,clips,applied=player.process_scene_volume(segmented,1)
assert [(c.id,c.start,len(c.pcm)) for c in clips]==[(c.id,c.start,len(c.pcm)) for c in layout]
assert out[800:1200]==b'\0'*400
manager=player.AudioPlayerManager.__new__(player.AudioPlayerManager)
manager.audio_edit_mode=True;manager.audio_edit_working={'dubbed':dict(segmented),'original':dict(segmented)}
manager.audio_edit_base_frames={'dubbed':segmented['frames']};manager.audio_edit_undo_stack=[];manager.audio_edit_redo_stack=[]
manager.waveform_selection_ranges={};manager.waveform_selection_kind=None
manager.stop=lambda **kw:None;manager._remove_audio_edit_preview=lambda:None;manager._refresh_waveforms=lambda:None;manager._update_audio_edit_buttons=lambda:None
messages=[];manager._set_audio_edit_status=messages.append
manager.project_root=None;manager.window=object();jobs=[];manager.parent=SimpleNamespace(after=lambda ms,fn:jobs.append(fn))
class Thread:
 def __init__(self,target,**kw):self.target=target
 def start(self):self.target()
with patch.object(player.threading,'Thread',Thread):
 manager._process_scene_audio_edit(volume_db=1)
 assert manager.audio_transform_busy
 jobs.pop()()
assert manager.audio_edit_working['dubbed']['frames']==out
assert manager.audio_edit_working['original']==segmented
manager._undo_audio_edit();assert manager.audio_edit_working['dubbed']['frames']==segmented['frames']
manager._redo_audio_edit();assert manager.audio_edit_working['dubbed']['frames']==out
assert manager.audio_edit_working['dubbed']['clips']==clips
manager.audio_edit_mode=False;manager._process_scene_audio_edit(volume_db=1);assert not jobs
print('OK: 8/16/24/32-bit stereo PCM, +/-1dB, peak ceiling, silence, exact timing, clip IDs/gaps, original isolation, async apply, undo/redo and edit guard.')
