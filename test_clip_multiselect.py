from types import SimpleNamespace
from audio_player import AudioPlayerManager
from audio_clip_timeline import AudioClip,render_clips
m=AudioPlayerManager(None);m.stop=lambda **kw:None;m._set_audio_edit_status=lambda text:None
m._draw_waveform=lambda *a:None;m._draw_clip_timeline=lambda *a:None;m._refresh_waveforms=lambda:None
layout=tuple(AudioClip(i+1,i*10,bytes([i+1,0])*10) for i in range(5))
raw=render_clips(layout,2,2);track=dict(frames=raw,channels=1,sample_width=2,sample_rate=10,clips=layout)
m.audio_edit_working={'dubbed':track};m.audio_edit_base_frames={'dubbed':raw};m.audio_edit_mode=True
m._select_clip(layout[0]);m._select_clip(layout[2],4)
assert m.selected_clip_ids=={1,3} and m._clip_is_selected(layout[2],track) and not m._clip_is_selected(layout[1],track)
m._select_clip(layout[0],4);assert m.selected_clip_ids=={3}
m._select_clip(layout[0]);m._select_clip(layout[3],1);assert m.selected_clip_ids=={1,2,3,4}
m._select_clip(layout[4]);m._select_clip(layout[1],1);assert m.selected_clip_ids=={2,3,4,5}
assert m._select_all_dubbed_clips()=='break' and m.selected_clip_ids=={1,2,3,4,5}
m._select_clip(layout[0]);m._select_clip(layout[2],4)
m._copy_audio_selection();assert m.audio_clip_buffer['frames']==layout[0].pcm+layout[2].pcm
m._delete_audio_selection();assert [c.id for c in track['clips']]==[2,4,5]
assert track['frames']==layout[1].pcm+layout[3].pcm+layout[4].pcm
m._undo_audio_edit();assert track['frames']==raw and track['clips']==layout
m._select_all_dubbed_clips();m._delete_audio_selection();assert track['frames']==b''
m._undo_audio_edit();assert track['clips']==layout
m._select_clip(layout[0]);m._select_clip(layout[2],4)
m._focused_waveform_kind=lambda:'dubbed'
m._paste_audio_clip()
assert any(c.id==2 and c.pcm==layout[1].pcm for c in track['clips'])
m._undo_audio_edit();assert track['frames']==raw
before=set(m.selected_clip_ids)
assert m._select_all_dubbed_clips(SimpleNamespace(widget=SimpleNamespace(winfo_class=lambda:'Text'))) is None
assert m.selected_clip_ids==before
m.audio_edit_mode=False;assert m._select_all_dubbed_clips() is None
print('OK: Ctrl+A, Ctrl toggle, Shift forward/reverse, exact highlighting, disjoint copy/delete/paste, all-delete, undo and text-focus guard.')
