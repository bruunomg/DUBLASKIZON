import tempfile,wave,unittest,math
from pathlib import Path
from unittest.mock import patch
import numpy as np
import audio_player as player

class FinishingTests(unittest.TestCase):
 def write(self,path,values):
  path.parent.mkdir(parents=True,exist_ok=True)
  with wave.open(str(path),'wb') as wav:
   wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(np.array(values,dtype='<i2').tobytes())
 def test_peak_limit_idempotency_and_previous_version(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/'dublado'/'chapter'/'a.wav';self.write(target,[0,1,-1,100,-100]*100)
   original=target.read_bytes();result=player.apply_dubbed_finishing(target,root,max_volume=True)
   self.assertTrue(result['changed']);self.assertGreater(result['gain_db'],24)
   with wave.open(str(target)) as wav:
    self.assertEqual(wav.getnframes(),500);peak=max(abs(np.frombuffer(wav.readframes(500),'<i2').astype('i4')))
   self.assertLessEqual(peak,math.floor(32767*10**(-1/20)));self.assertGreater(peak,29000)
   backups=list((root/'revisoes').rglob('*.wav'));self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),original)
   self.assertFalse(player.apply_dubbed_finishing(target,root,max_volume=True)['changed']);self.assertEqual(len(list((root/'revisoes').rglob('*.wav'))),1)
 def test_trim_uses_scene_engine_and_preserves_middle(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/'dublado'/'a.wav';self.write(target,[0,0,200,0,200,0,0])
   def trim(track,project,**kwargs):
    self.assertTrue(kwargs['preserve_clips']);return track['frames'][4:-4],()
   with patch('audio_player.process_scene_audio',side_effect=trim):result=player.apply_dubbed_finishing(target,root,trim=True)
   with wave.open(str(target)) as wav:self.assertEqual(np.frombuffer(wav.readframes(wav.getnframes()),'<i2').tolist(),[200,0,200])
   self.assertAlmostEqual(result['removed_seconds'],4/24000)
 def test_no_change_silent_and_no_original_modification(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/'dublado'/'a.wav';self.write(target,[0]*100)
   before=target.read_bytes();self.assertFalse(player.apply_dubbed_finishing(target,root,max_volume=True)['changed']);self.assertEqual(target.read_bytes(),before)
   original=root/'WAV ORIGINAIS'/'a.wav';self.write(original,[100]*20)
   before=original.read_bytes()
   with self.assertRaises(ValueError):player.apply_dubbed_finishing(original,root,max_volume=True)
   self.assertEqual(original.read_bytes(),before)
 def test_processing_failure_preserves_target(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/'dublado'/'a.wav';self.write(target,[100]*20);before=target.read_bytes()
   with patch('audio_player.process_scene_audio',side_effect=RuntimeError('FFmpeg indisponível')):
    with self.assertRaises(RuntimeError):player.apply_dubbed_finishing(target,root,trim=True)
   self.assertEqual(target.read_bytes(),before);self.assertFalse(list(target.parent.glob('.__acabamento_*')))
class ReviewFinishingIntegration(unittest.TestCase):
 write=FinishingTests.write
 def test_review_applies_all_in_background_and_archives(self):
  import tkinter as tk,time
  from tkinter import ttk
  from types import SimpleNamespace
  import review_tab
  with tempfile.TemporaryDirectory() as folder:
   project=Path(folder);a=project/'dublado'/'a.wav';b=project/'dublado'/'sub'/'b.wav'
   self.write(a,[10,-10]*100);self.write(b,[100,-100]*100)
   root=tk.Tk();root.withdraw()
   try:
    logs=[];app=SimpleNamespace(root=root,busy=False,stems=['a','sub/b'],default_stems=['a','sub/b'],current_output=lambda stem:project/'dublado'/(stem+'.wav'),audio_player=SimpleNamespace(window=None,stop=lambda **kw:None),status_var=tk.StringVar(root),finishing_progress=ttk.Progressbar(root),_log_central=logs.append,refresh_scene_list=lambda:None)
    with patch('review_tab.ROOT',project),patch('review_tab.messagebox.askyesno',return_value=True):
     review_tab.ReviewApp.finish_all_audio(app,max_volume=True)
     deadline=time.monotonic()+5
     while app.busy and time.monotonic()<deadline:root.update();time.sleep(.02)
    self.assertFalse(app.busy);self.assertIn('2/2 processados',app.status_var.get());self.assertEqual(len(list((project/'revisoes').rglob('*.wav'))),2)
   finally:root.destroy()
if __name__=='__main__':unittest.main()
