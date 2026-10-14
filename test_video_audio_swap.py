from pathlib import Path
import ast,hashlib,json,os,queue,subprocess,tempfile,threading,wave
from unittest.mock import patch
import video_audio_swap_tab as swap

ffmpeg=os.environ['VIDEO_TEST_FFMPEG'];ffprobe=str(Path(ffmpeg).with_name('ffprobe.exe'))
def run(args):
    r=subprocess.run([ffmpeg,'-v','error',*args],capture_output=True,timeout=60)
    assert r.returncode==0,r.stderr.decode(errors='replace')[-1500:]
    return r.stdout

def frames(path):
    raw=run(['-i',str(path),'-map','0:v:0','-f','framemd5','-'])
    return [line.split(b',')[-1].strip() for line in raw.splitlines() if line and not line.startswith(b'#')]

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);video=root/'cena.mp4';dub=root/'cena.wav';backups=root/'backups'
    run(['-f','lavfi','-i','testsrc2=size=128x72:rate=10:duration=1','-f','lavfi','-i','sine=frequency=330:duration=1','-f','lavfi','-i','sine=frequency=550:duration=1','-map','0:v','-map','1:a','-map','2:a','-c:v','libx264','-c:a','aac',str(video)])
    run(['-f','lavfi','-i','sine=frequency=880:duration=1',str(dub)])
    before=video.read_bytes();pictures=frames(video)
    original_pcm=run(['-i',str(video),'-map','0:a:0','-f','s16le','-c:a','pcm_s16le','-'])
    wav=swap.ensure_backup(backups,video,ffmpeg,ffprobe)
    assert wav.suffix=='.wav' and not list(backups.rglob('*.bin'))
    with wave.open(str(wav),'rb') as w:assert w.readframes(w.getnframes())==original_pcm
    original_hash=swap.file_hash(wav)
    app=swap.VideoAudioSwapApp.__new__(swap.VideoAudioSwapApp);app.events=queue.Queue();app.process=None;app.cancel_event=threading.Event()
    app.worker('apply',[(video,dub)],backups,ffmpeg,ffprobe)
    assert frames(video)==pictures and len(swap.audio_streams(ffprobe,video))==1
    swap.ensure_backup(backups,video,ffmpeg,ffprobe);assert swap.file_hash(wav)==original_hash
    swap.restore_backup(backups,video,ffmpeg,ffprobe)
    assert frames(video)==pictures and len(swap.audio_streams(ffprobe,video))==2
    restored=run(['-i',str(video),'-map','0:a:0','-f','s16le','-c:a','pcm_s16le','-'])
    import numpy as np
    samples=np.frombuffer(restored,dtype=np.int16).astype(float)
    frequency=np.argmax(abs(np.fft.rfft(samples)))*44100/len(samples)
    assert abs(frequency-330)<5,frequency
    # Legacy BIN is migrated using original bytes, never the already-dubbed video.
    legacy_root=root/'legacy';folder=legacy_root/swap.backup_key(video);folder.mkdir(parents=True)
    binary=folder/'original.bin';binary.write_bytes(before)
    (folder/'manifest.json').write_text(json.dumps({'path':str(video.resolve()),'sha256':swap.file_hash(binary)}))
    migrated=swap.ensure_backup(legacy_root,video,ffmpeg,ffprobe)
    assert migrated.is_file() and not binary.exists()
    with wave.open(str(migrated),'rb') as w:assert w.readframes(w.getnframes())==original_pcm
    # Corrupt WAV is rejected and video is untouched.
    snapshot=video.read_bytes();wav.write_bytes(b'bad')
    try:swap.restore_backup(backups,video,ffmpeg,ffprobe)
    except RuntimeError:pass
    else:raise AssertionError('invalid backup accepted')
    assert video.read_bytes()==snapshot
    for folder in backups.rglob('*'):
        if folder.is_dir():assert len([p for p in folder.iterdir() if p.is_file()])<=100
    silent=root/'silent.mkv';run(['-i',str(video),'-an','-c:v','copy',str(silent)])
    app.worker('apply',[(silent,dub)],backups,ffmpeg,ffprobe)
    swap.restore_backup(backups,silent,ffmpeg,ffprobe)
    assert not swap.audio_streams(ffprobe,silent)
base=Path(__file__).parent
for name in ('Dublaskizon.py','video_audio_swap_tab.py'):ast.parse((base/name).read_text(encoding='utf-8'))
s=(base/'Dublaskizon.py').read_text(encoding='utf-8')
assert 'tools_bar = tabs_bar' in s and 'height=2, padx=7, pady=6' in s
assert 'tools_bar.pack(' not in s
print('v13 OK: WAV extraction matches decoded original, repeat apply, multi-track restore, same video frames, BIN migration, corrupted backup rejected, no-audio restore, one-row uniform tabs')
