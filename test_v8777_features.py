import sys,unittest,queue,threading,tempfile,types
from pathlib import Path
sys.path.insert(0,str(Path('build_vendor').resolve()))
from unittest.mock import patch,Mock
from test_audio_player_live_follow import LiveFollowTests,make_audio
from background_audio import BackgroundEditor

class BackgroundControlTests(unittest.TestCase):
 setUp=LiveFollowTests.setUp
 def test_selection_volume_and_all_four_play_buttons_use_clicked_position(self):
  target=self.project/'dublado'/(self.keys[0]+'.wav');make_audio(target)
  self.manager.play_one(self.originals[0],playlist=self.originals,index=0,scene_key=self.keys[0],scene_keys=self.keys);self.root.update()
  editor=BackgroundEditor(self.manager);self.root.update()
  original=editor.background.raw_data
  editor.selection=(200,500);editor.gain_selection(-6)
  self.assertEqual(editor.background[:200].raw_data,original[:len(editor.background[:200].raw_data)])
  self.assertLess(editor.background[200:500].rms,editor.original[200:500].rms)
  editor.undo_edit();self.assertEqual(editor.background.raw_data,original)
  for canvas in editor.canvases:
   editor.seek(types.SimpleNamespace(x=canvas.winfo_width()//2,widget=canvas))
   selected=editor.seek_ms/1000
   with patch.object(self.manager,'_start_paths') as start:
    for kind in ('original','background','dub'):editor.play_selected(kind);self.assertAlmostEqual(start.call_args.kwargs['start_seconds'],selected,places=2)
    editor.play_mix();self.assertAlmostEqual(start.call_args.kwargs['start_seconds'],selected,places=2)
  editor.close()

class RejectedOptionTests(unittest.TestCase):
 def test_batch_applies_shared_flags_reference_and_r_to_each_scene(self):
  from review_tab import ReviewApp
  value=types.SimpleNamespace(set=Mock())
  app=types.SimpleNamespace(busy=False,_rejected_queue=['scene'],stems=['scene'],root=types.SimpleNamespace(after=Mock()),_next_rejected=Mock(),select_scene=Mock(),regenerate_scene=Mock(),config={},align_original_var=value,_rejected_reference=Path('voice.wav'),_rejected_run_options={'align_original_var':'1','request_r_var':'1','r_mode':'unchanged'},request_r_var=types.SimpleNamespace(set=Mock()))
  ReviewApp._next_rejected(app)
  value.set.assert_called_once_with('1');app.regenerate_scene.assert_called_once()
  self.assertEqual(app.alternate_reference_audio,Path('voice.wav'))
  self.assertEqual(app.regen_r_override,'unchanged')

class TextMemoryTests(unittest.TestCase):
 def test_text_tab_counts_as_active_context(self):
  from review_memory_ui import context_active
  self.assertTrue(context_active(types.SimpleNamespace(current_tab_key=lambda:'text_to_speech')))
 def test_text_synthesis_reuses_cache_worker(self):
  from warm_inference import ReviewMemoryCache,SERVER_CODE,WarmInference
  from test_warm_inference import FAKE_ENGINE
  from text_to_speech_tab import TextToSpeechApp
  cache=ReviewMemoryCache();self.addCleanup(cache.shutdown);cache.set_enabled(True)
  app=types.SimpleNamespace(cancel_event=threading.Event(),events=queue.Queue(),process=None)
  command=[sys.executable,'-u','-c',"from omnivoice.models.omnivoice import OmniVoice;OmniVoice.from_pretrained('same');print('Generated audio',flush=True)"]
  with patch('warm_inference.review_memory_cache',cache),patch('warm_inference.SERVER_CODE',FAKE_ENGINE+SERVER_CODE),patch.object(WarmInference,'eligible',return_value=True),patch('warm_inference.available_memory',return_value=(8*1024**3,16*1024**3)),patch('batch_tab.find_ffmpeg_directory',return_value=None):
   TextToSpeechApp._run_emotional_command(app,command);pid=cache.pool.process.pid
   TextToSpeechApp._run_emotional_command(app,command)
   self.assertEqual(pid,cache.pool.process.pid);self.assertTrue(cache.snapshot()['model_ready'])
