import math,struct,os,ast
from pathlib import Path
import audio_player as player
import duration_converter_tab as converter
ff=Path(os.environ['VIDEO_TEST_FFMPEG'])
converter.executable_path=lambda name, root=None: str(ff.with_name(name+'.exe')) if name in ('ffmpeg','ffprobe') else None
rate=24000
tone=b''.join(struct.pack('<h',int(12000*math.sin(2*math.pi*440*i/rate))) for i in range(rate*3))
track=dict(frames=tone,channels=1,sample_width=2,sample_rate=rate)
for factor in (0.99,1.01):
 raw=player.process_scene_audio(track,None,factor)
 duration=len(raw)/2/rate
 assert abs(duration-3*factor)<0.07,(duration,factor)
 samples=struct.unpack('<'+'h'*(len(raw)//2),raw)[rate//2:rate*2]
 crossings=sum(a<=0<b for a,b in zip(samples,samples[1:]))
 frequency=crossings/(len(samples)/rate)
 assert abs(frequency-440)<3,frequency
 assert track['frames']==tone
silence=b'\0'*(rate*2)
raw=player.process_scene_audio(dict(track,frames=silence+tone+silence+tone+silence),None)
assert 6.9<len(raw)/2/rate<7.1,len(raw)/2/rate
manager=player.AudioPlayerManager.__new__(player.AudioPlayerManager)
manager.audio_edit_mode=True
manager.audio_edit_working={'dubbed':dict(track)}
manager.audio_edit_base_frames={'dubbed':tone}
manager.audio_edit_undo_stack=[];manager.audio_edit_redo_stack=[]
manager.waveform_selection_ranges={};manager.waveform_selection_kind=None
manager.stop=lambda **kw:None
manager._remove_audio_edit_preview=lambda:None
manager._refresh_waveforms=lambda:None
manager._update_audio_edit_buttons=lambda:None
manager._set_audio_edit_status=lambda text:None
manager._set_edit_frames('dubbed',manager.audio_edit_working['dubbed'],raw)
assert manager.audio_edit_dirty
manager._undo_audio_edit();assert manager.audio_edit_working['dubbed']['frames']==tone
manager._redo_audio_edit();assert manager.audio_edit_working['dubbed']['frames']==raw
manager.audio_edit_mode=False
manager._process_scene_audio_edit(1.05)
assert manager.audio_edit_working['dubbed']['frames']==raw
for name in ('audio_player.py','voice_clone_tab.py'):
 ast.parse(Path(__file__).with_name(name).read_text(encoding='utf-8-sig'))
print('OK: duration +/-, pitch 440Hz preserved, edge silence removed, internal pause preserved, undo/redo, edit mode guard, syntax.')

# Whole-track duration/silence controls must preserve independent clips and their IDs.
from audio_clip_timeline import AudioClip, render_clips
import tempfile
layout=(AudioClip(7,0,silence+tone), AudioClip(12,rate*5,tone+silence))
segmented=dict(track,frames=render_clips(layout,2,2),clips=layout)
for factor in (0.99,1.01,None):
    processed, kept=player.process_scene_audio(segmented,None,factor,preserve_clips=True)
    assert [c.id for c in kept]==[7,12]
    assert all(a.end(2)<=b.start for a,b in zip(kept,kept[1:]))
    assert render_clips(kept,2,2,len(processed)//2)==processed
    gap=processed[kept[0].end(2)*2:kept[1].start*2]
    assert len(gap)>0 and not any(gap)
    if factor is None:
        assert abs(len(processed)/2/rate-7)<0.03
        assert kept[0].start==0
    manager.audio_edit_mode=True
    manager.audio_edit_working={'dubbed':dict(segmented)}
    manager.audio_edit_base_frames={'dubbed':segmented['frames']}
    manager.audio_edit_undo_stack=[];manager.audio_edit_redo_stack=[]
    edited=manager.audio_edit_working['dubbed']
    manager._set_edit_frames('dubbed',edited,processed,clips=kept)
    manager._undo_audio_edit()
    assert edited['frames']==segmented['frames'] and edited['clips']==layout
    manager._redo_audio_edit()
    assert edited['frames']==processed and edited['clips']==kept
    with tempfile.TemporaryDirectory() as folder:
        manager.project_root=Path(folder)
        edited['path']=Path(folder)/'cena.wav'
        manager._save_clip_layout(edited)
        reopened=dict(edited);reopened.pop('clips')
        manager._load_clip_layout(reopened)
        assert reopened['clips']==kept
print('OK: +/- 1% and edge trimming preserve clip IDs, internal silence, undo/redo and saved layouts.')
