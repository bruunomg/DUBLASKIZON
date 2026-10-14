from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import threading,subprocess,sys,os,wave,json
import scene_parts
import duration_converter_tab
from audio_player import AudioPlayerManager
from audio_clip_timeline import AudioClip
from review_tab import ReviewApp

ffmpeg=Path(os.environ['VIDEO_TEST_FFMPEG'])
duration_converter_tab.executable_path=lambda name,root=None:str(ffmpeg.with_name(name+'.exe')) if name in ('ffmpeg','ffprobe') else None

def make_wav(path,rate=24000,channels=1):
 with wave.open(str(path),'wb') as wav:
  wav.setnchannels(channels);wav.setsampwidth(2);wav.setframerate(rate)
  wav.writeframes((b'\x01\x01'*channels)*(rate//5))

with TemporaryDirectory() as directory:
 root=Path(directory);reference=root/'referencia.wav';make_wav(reference)
 original=root/'original.wav';make_wav(original)
 dubbed=root/'dublado.wav';make_wav(dubbed,48000,2)
 maintext=root/'cena.txt';maintext.write_text('Frase completa que deve continuar intacta.',encoding='utf-8')
 preserved={p:p.read_bytes() for p in (reference,original,dubbed,maintext)}
 commands=[]
 def runner(command,cancel):
  commands.append(command)
  if command[0]=='fake-infer':make_wav(Path(command[command.index('--output')+1]))
  else:
   subprocess.run(command,check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 config={'model':'modelo','language':'pt','instruct':'portuguese accent'}
 context={'root':root,'scene':'capitulo/cena','source':'dublado','config':config,'format':(2,2,48000),'infer_prefix':['fake-infer']}
 first=scene_parts.generate_part(context,'Somente a primeira parte.',reference,threading.Event(),runner)
 second=scene_parts.generate_part(context,'Outra frase.',reference,threading.Event(),runner)
 assert [p['number'] for p in scene_parts.list_parts(first['audio'].parent.parent)]==[1,2]
 assert first['text'].read_text(encoding='utf-8').strip()=='Somente a primeira parte.'
 assert commands[0][commands[0].index('--text')+1]=='Somente a primeira parte.'
 assert commands[0][commands[0].index('--ref_audio')+1]==str(reference)
 with wave.open(str(first['audio']),'rb') as wav:assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(2,2,48000)
 custom=scene_parts.generate_part(dict(context,source='dublados personalizados'),'Personalizada.',reference,threading.Event(),runner)
 assert custom['number']==1 and custom['audio'].parent.parent!=first['audio'].parent.parent
 assert all(p.read_bytes()==data for p,data in preserved.items())
 def failing(command,cancel):raise RuntimeError('erro simulado')
 try:scene_parts.generate_part(context,'Falha.',reference,threading.Event(),failing)
 except RuntimeError:pass
 else:raise AssertionError('failure hidden')
 cancel=threading.Event();cancel.set()
 try:scene_parts.generate_part(context,'Cancelar.',reference,cancel,runner)
 except RuntimeError:pass
 else:raise AssertionError('cancel ignored')
 assert len(scene_parts.list_parts(first['audio'].parent.parent))==2
 assert not list(first['audio'].parent.parent.glob('.gerando_*'))
 # Float WAV from inference is normalized to the main editor format too.
 def float_runner(command,cancel):
  if command[0]=='fake-infer':
   output=command[command.index('--output')+1]
   command=[str(ffmpeg),'-y','-f','lavfi','-i','sine=frequency=440:duration=0.15','-c:a','pcm_f32le',output]
  subprocess.run(command,check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 floated=scene_parts.generate_part(context,'Formato float.',reference,threading.Event(),float_runner)
 with wave.open(str(floated['audio']),'rb') as wav:assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(2,2,48000)
 # Clipboard bridges the independent part window into main editing without touching source.
 parent=AudioPlayerManager(None,root);child=AudioPlayerManager(None,root)
 parent.audio_edit_mode=True;child.audio_edit_mode=True;child.clipboard_target=parent
 parent.stop=lambda **kw:None;child.stop=lambda **kw:None
 mainframes=b'\x01\x00'*10
 clips=(AudioClip(1,0,mainframes[:10]),AudioClip(2,5,mainframes[10:]))
 parent.audio_edit_working={'dubbed':dict(frames=mainframes,channels=1,sample_width=2,sample_rate=10,clips=clips)}
 parent.audio_edit_base_frames={'dubbed':mainframes}
 child.audio_edit_working={'dubbed':dict(frames=b'\x02\x00'*4,channels=1,sample_width=2,sample_rate=10)}
 child._copy_whole_part()
 assert parent.audio_clip_buffer['frames']==b'\x02\x00'*4
 parent.waveform_selection_kind='dubbed';parent.waveform_selection_ranges['dubbed']=(.5,.5)
 parent._paste_audio_clip()
 assert len(parent.audio_edit_working['dubbed']['clips'])==3
 parent._undo_audio_edit();assert parent.audio_edit_working['dubbed']['frames']==mainframes
 assert all(p.read_bytes()==data for p,data in preserved.items())
 # Context selection cannot substitute normal dubbing for a personalized reference.
 review=ReviewApp.__new__(ReviewApp);review.config=config;review.audio_by_stem={'scene':original}
 review.audio_player=SimpleNamespace(dubbed_folder_name='dublado');review._fixed_r_pronunciation=lambda:'unchanged'
 review._custom_model_for_stem=lambda stem:reference
 assert review.part_generation_context('scene')['reference']==original
 review.audio_player.dubbed_folder_name='dublados personalizados'
 assert review.part_generation_context('scene')['reference']==reference
 # The actual subprocess runner terminates on cancel and reports nonzero exits.
 cancel=threading.Event();timer=threading.Timer(.2,cancel.set);timer.start()
 try:scene_parts.run_command([sys.executable,'-c','import time; time.sleep(30)'],cancel)
 except RuntimeError as exc:assert 'cancelada' in str(exc)
 else:raise AssertionError('cancel failed')
 timer.join()
 try:scene_parts.run_command([sys.executable,'-c','raise SystemExit(3)'],threading.Event())
 except RuntimeError as exc:assert '3' in str(exc)
 else:raise AssertionError('exit code ignored')
print('OK: isolated files/text, sequential parts, separate custom source, reference routing, real PCM conversion, cross-window copy/paste preserving clips, undo, failure and cancellation. Inference itself simulated.')
