import ast,os,subprocess,tempfile
from pathlib import Path
from audio_clone_preprocessor import AudioCloneProcessor,AudioProcessingError
ffmpeg=os.environ['VIDEO_TEST_FFMPEG'];ffprobe=str(Path(ffmpeg).with_name('ffprobe.exe'))
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);source=root/'audio.wav'
    subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','sine=frequency=440:duration=6',str(source)],check=True,capture_output=True)
    processor=AudioCloneProcessor(ffmpeg=ffmpeg,ffprobe=ffprobe)
    report=processor.process([source],'omnivoice',root/'duration',normalize=False,custom_seconds=2.5)
    assert abs(processor.probe(report.outputs[0]).duration-2.5)<.03
    for fmt in ('wav','mp3','flac','m4a','ogg'):
        maximum=90000
        result=processor.process([source],'omnivoice',root/fmt,output_format=fmt,normalize=False,custom_seconds=4,custom_max_bytes=maximum)
        assert result.outputs[0].stat().st_size<=maximum,(fmt,result.outputs[0].stat().st_size)
        assert processor.probe(result.outputs[0]).duration<=4.1
    result=processor.process([source],'eleven_pro',root/'long',normalize=False,custom_seconds=999)
    assert abs(processor.probe(result.outputs[0]).duration-6)<.1
    assert processor.custom_duration(600,120,None)==120
    for invalid in (0,-1,float('nan'),float('inf')):
        try:processor.custom_duration(20,invalid)
        except AudioProcessingError:pass
        else:raise AssertionError(invalid)
base=Path(__file__).parent
for name in ('Dublaskizon.py','voice_clone_tab.py','audio_clone_preprocessor.py'):
    ast.parse((base/name).read_text(encoding='utf-8'))
print('v14 OK: real duration trim, maximum bytes in WAV/MP3/FLAC/M4A/OGG, shorter input preserved, validation, syntax')
