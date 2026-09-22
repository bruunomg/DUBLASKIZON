from types import SimpleNamespace
from unittest.mock import patch
import audio_player as player
import test_scene_duration_controls as baseline
manager=baseline.manager
track=dict(baseline.segmented)
manager.audio_edit_working={'dubbed':track,'original':dict(baseline.segmented)}
manager.audio_edit_base_frames={'dubbed':track['frames']}
manager.audio_edit_undo_stack=[];manager.audio_edit_redo_stack=[];manager.audio_edit_mode=True
manager.window=object();manager.project_root=None;jobs=[]
manager.parent=SimpleNamespace(after=lambda delay,fn:jobs.append(fn))
def click(factor):
 import time
 manager._process_scene_audio_edit(factor)
 deadline=time.monotonic()+30
 while jobs:
  assert time.monotonic()<deadline
  time.sleep(.01)
  jobs.pop(0)()
 assert not manager.audio_transform_busy
base=track['frames'];layout=track['clips']
click(1.01);once=track['frames'];assert track['duration_ratio']==1.01
click(1.01);assert track['duration_ratio']==1.02
expected,clips=player.process_scene_audio(baseline.segmented,None,1.02,True)
assert track['frames']==expected and track['clips']==clips
assert track['duration_base']['frames']==base
manager._undo_audio_edit();assert track['frames']==once and track['duration_ratio']==1.01
manager._redo_audio_edit();assert track['frames']==expected and track['duration_ratio']==1.02
click(.99);assert track['frames']==once
click(.99);assert track['frames']==base and track['clips']==layout
assert manager.audio_edit_working['original']==baseline.segmented
# A different edit becomes the next duration base.
raw,changed,_=player.process_scene_volume(track,-1)
manager._set_edit_frames('dubbed',track,raw,clips=changed)
assert 'duration_base' not in track
click(1.01);assert track['duration_base']['frames']==raw
# Each rendered clip matches the converter applied to that clip alone.
for source,result in zip(layout,clips):
 converted=player.process_scene_audio(dict(baseline.track,frames=source.pcm),None,1.02)
 n=min(len(converted),len(result.pcm))
 assert result.pcm[:n]==converted[:n]
print('OK: repeated clicks use pristine base; 2 clicks equal one pass; +/− exact PCM restoration; undo/redo includes base; volume resets base; independent clips use identical converter output.')
