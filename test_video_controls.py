import ast
import os
from pathlib import Path
import queue
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import video_preview as preview

assert preview.timeline_position(12,1024,100)==0
assert preview.timeline_position(512,1024,100)==50
assert preview.timeline_position(1012,1024,100)==100
assert preview.timeline_position(-100,1024,100)==0
assert preview.clock_text(3723)=='01:02:03'
# API signatures resolve on the target Windows runtime.
if os.name=='nt':preview.WindowsVideoHost()
app=preview.VideoPreview.__new__(preview.VideoPreview)
app.duration=100;app.current=12;app.paused=False;app.dragging=False;app.frame_serial=0
calls=[]
app.stop=lambda:calls.append('stop')
app.draw_timeline=lambda:None
app.request_frame=lambda value:calls.append(('frame',value))
app.start_playback=lambda value:calls.append(('play',value))
app.status=SimpleNamespace(set=lambda text:None)
app.timeline=SimpleNamespace(winfo_width=lambda:1024,grab_set=lambda:None,grab_release=lambda:None)
app.begin_seek(SimpleNamespace(x=512));assert app.current==50 and app.dragging
app.drag_seek(SimpleNamespace(x=762));assert app.current==75
app.end_seek(SimpleNamespace(x=812));assert app.current==80 and not app.dragging
assert calls[-1]==('play',80)
app.paused=True;calls.clear();app.begin_seek(SimpleNamespace(x=212));app.end_seek(SimpleNamespace(x=312))
assert app.current==30 and not any(isinstance(c,tuple) and c[0]=='play' for c in calls)
app.playlist=[Path('A'),Path('B'),Path('C')];app.index=1;app.load=lambda index:calls.append(('load',index))
app.navigate(-1);assert calls[-1]==('load',0)
app.navigate(1);assert calls[-1]==('load',2)
app.index=0;before=len(calls);app.navigate(-1);assert len(calls)==before
# PNG extraction at distinct positions, using real FFmpeg.
ffmpeg=os.environ['VIDEO_TEST_FFMPEG']
with tempfile.TemporaryDirectory() as tmp:
    source=Path(tmp)/'test.mp4'
    subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=12:duration=2','-c:v','libx264',str(source)],check=True,capture_output=True)
    frames=[]
    for seconds in (0,.8,1.5):
        result=subprocess.run(preview.frame_command(ffmpeg,source,seconds,320,180),check=True,capture_output=True)
        assert result.stdout.startswith(b'\x89PNG\r\n\x1a\n')
        frames.append(result.stdout)
    assert len(set(frames))==3
for name in ('video_preview.py','video_converter_tab.py'):
    ast.parse((Path(__file__).parent/name).read_text(encoding='utf-8-sig'))
print('v11 OK: Windows API signatures, timeline click/drag, paused/playing seek, playlist boundaries, real PNG seek frames, syntax')
