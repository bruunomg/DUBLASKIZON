import ast
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
import video_converter_tab as video

FFMPEG=os.environ['VIDEO_TEST_FFMPEG']
FFPROBE=str(Path(FFMPEG).with_name('ffprobe.exe'))

def run(cmd):
    result=subprocess.run(cmd,capture_output=True,timeout=90,**video.hidden_kwargs())
    assert result.returncode==0,result.stderr.decode(errors='replace')[-3000:]
    return result.stdout

assert video.parse_position('01:02:03.5')==3723.5
assert video.parse_position('12,5')==12.5
for invalid in ('-2','nan','inf','1:2:3:4','abc'):
    try:video.parse_position(invalid)
    except ValueError:pass
    else:raise AssertionError(invalid)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);source=root/'vídeo com espaços.mp4'
    run([FFMPEG,'-y','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=12:duration=1',
         '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-crf','12','-c:a','aac',str(source)])
    original_bytes=source.read_bytes();info=video.probe_video(FFPROBE,source)
    assert info['video']['width']==160 and info['duration']>0
    for number,format_name in enumerate(video.FORMATS):
        output=root/f'output_{number}{video.FORMATS[format_name][0]}'
        command=video.conversion_command(FFMPEG,source,output,format_name,video.DEFAULT_QUALITY)
        run(command)
        result=video.probe_video(FFPROBE,output)
        assert (result['video']['width'],result['video']['height'])==(160,90)
        assert result['video']['r_frame_rate']=='12/1'
        if video.FORMATS[format_name][1]=='ffv1':
            before=run([FFMPEG,'-v','error','-i',str(source),'-map','0:v:0','-f','framemd5','-'])
            after=run([FFMPEG,'-v','error','-i',str(output),'-map','0:v:0','-f','framemd5','-'])
            hashes=lambda raw:[line.split(b',')[-1].strip() for line in raw.splitlines() if line and not line.startswith(b'#')]
            assert hashes(before)==hashes(after),'lossless frame hashes differ'
    silent=root/'silent.mkv'
    run([FFMPEG,'-v','error','-i',str(source),'-an','-c:v','copy',str(silent)])
    run(video.conversion_command(FFMPEG,silent,root/'silent-out.mp4',video.DEFAULT_FORMAT,video.DEFAULT_QUALITY))
    bad=root/'not-video.txt';bad.write_text('invalid video')
    app=video.VideoConverterApp.__new__(video.VideoConverterApp)
    app.events=queue.Queue();app.cancel_event=threading.Event();app.process=None
    folder=root/'results'
    app.worker([source,source,bad],folder,video.DEFAULT_FORMAT,video.DEFAULT_QUALITY,FFMPEG,FFPROBE)
    events=[]
    while not app.events.empty():events.append(app.events.get())
    assert events[-1]==('done',2,1,False),events
    assert len(list(folder.glob('*.mp4')))==2
    assert not list(folder.glob('.dublaskizon*'))
    assert source.read_bytes()==original_bytes
    # Cancel after synthesis begins: no partial output should be left behind.
    original_popen=video.subprocess.Popen
    def cancel_popen(command,**kwargs):
        process=original_popen(command,**kwargs)
        if '-progress' in command:app.cancel_event.set()
        return process
    app.events=queue.Queue();app.cancel_event.clear()
    with patch.object(video.subprocess,'Popen',side_effect=cancel_popen):
        app.worker([source],root/'cancelled',video.DEFAULT_FORMAT,video.DEFAULT_QUALITY,FFMPEG,FFPROBE)
    assert not list((root/'cancelled').iterdir())
    assert app.events.get()[0]=='log'
    final=None
    while not app.events.empty():final=app.events.get()
    assert final[-1] is True
for name in ('video_converter_tab.py','Dublaskizon.py'):
    ast.parse((Path(__file__).parent/name).read_text(encoding='utf-8-sig'))
print('VIDEO OK: six real encodes, frame sizes/rates, lossless hashes, no-audio input, queue failure recovery, collisions, cancellation and original preservation')
