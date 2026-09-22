from pathlib import Path
from types import SimpleNamespace
import time
from audio_player import AudioPlayerManager
m=AudioPlayerManager(None)
m.audio_edit_mode=True
m.audio_edit_working={'dubbed':dict(frames=b'\x00'*20000,channels=1,sample_width=2,sample_rate=1000)}
m._set_audio_edit_status=lambda text:None
calls=[]
m._play_edit_preview=lambda kind,start: calls.append((kind,start)) or True
for selection in ((3.25,3.25),(2,5),(7,4)):
 m.waveform_selection_kind='dubbed';m.waveform_selection_ranges['dubbed']=selection
 m.start_pending();assert calls[-1]==('dubbed',min(selection))
 m._toggle_edit_play_pause();assert calls[-1]==('dubbed',min(selection))
# Space pauses/resumes at the current playback position, not the old selection.
m.waveform_active_kind='dubbed';m.waveform_active_path=Path('preview.wav')
m.waveform_active_started_at=time.monotonic();m.waveform_active_duration=10;m.waveform_active_offset=6
m.stop=lambda **kw: (setattr(m,'waveform_active_kind',None),setattr(m,'waveform_active_path',None))
m._toggle_edit_play_pause();assert 6<=m.audio_paused_seconds<6.1
assert m.audio_paused_path==Path('preview.wav')
m._toggle_edit_play_pause();assert 6<=calls[-1][1]<6.1
# Clicking a new waveform point clears the previous pause before starting.
m.audio_paused_kind='dubbed';m.audio_paused_seconds=8
m.stop=lambda **kw: (setattr(m,'audio_paused_kind',None),setattr(m,'audio_paused_seconds',0))
m._waveform_x_to_seconds=lambda kind,x:x/100
m._draw_waveform=lambda kind:None;m._draw_clip_timeline=lambda:None
m._on_waveform_press('dubbed',SimpleNamespace(x=150))
m._toggle_edit_play_pause();assert calls[-1]==('dubbed',1.5)
# No selection and playback outside EDITAR keep their original behavior.
m.waveform_selection_ranges={'dubbed':None,'original':None};m.waveform_selection_kind=None
m.start_pending();assert calls[-1]==('dubbed',0)
m.audio_edit_mode=False;m.pending_paths=[Path('scene.wav')]
m._start_paths=lambda paths,kind: calls.append((paths,kind))
m.start_pending();assert calls[-1]==([Path('scene.wav')],'dublada')
print('OK: point/range selection, reversed selection, button/Space, pause/resume, new click clears pause and non-edit playback unchanged.')
