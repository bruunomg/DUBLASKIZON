import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import batch_text_preparation as preparation

class PreparationTests(unittest.TestCase):
 def test_scans_only_missing_and_transcribes_all_before_translation_then_reuses_cache(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);texts=root/'TXT TEXTO PORTUGUES';texts.mkdir();(texts/'existing.txt').write_text('Texto do usuário')
   audios={}
   for stem in ('existing','a','b'):
    audios[stem]=root/(stem+'.wav');audios[stem].write_bytes(b'audio')
   order=[]
   def transcribe(paths,config,emit,cancelled,on_result):
    for i,path in enumerate(paths):order.append('asr:'+path.stem);on_result(i,{'transcript':'Hello '+path.stem,'source_language':'en'})
   def translate(audio,text_path,project,stem,config,*args,**kw):
    self.assertTrue(config['_prepared_transcription']['transcript']);order.append('translate:'+stem);return 'Olá '+stem,'Portuguese'
   with patch('transcription_backend.run_local_batch',side_effect=transcribe) as asr,patch('audio_translation.generate_text',side_effect=translate) as translator:
    ready,errors=preparation.prepare_missing_texts(list(audios),audios,{},texts,root,{},lambda x:None,lambda:False)
    self.assertEqual(order,['asr:a','asr:b','translate:a','translate:b']);self.assertFalse(errors);self.assertEqual(set(ready),{'a','b'})
    preparation.prepare_missing_texts(list(audios),audios,{},texts,root,{},lambda x:None,lambda:False)
    self.assertEqual(asr.call_count,1);self.assertEqual(translator.call_count,2)
   self.assertEqual((texts/'existing.txt').read_text(),'Texto do usuário')
 def test_theme_is_applied_between_transcription_and_translation(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);audio=root/'a.wav';audio.write_bytes(b'audio');seen=[]
   def transcribe(paths,config,emit,cancelled,on_result):on_result(0,{'transcript':'Hello world','source_language':'en'})
   def translate(*args,**kwargs):self.assertEqual(args[4]['context_profile']['instructions'],'Updated context');return 'Olá','Portuguese'
   with patch('transcription_backend.run_local_batch',side_effect=transcribe),patch('theme_research.enrich_from_transcripts',return_value={'title':'Game','instructions':'Updated context'}) as research,patch('audio_translation.generate_text',side_effect=translate):
    ready,errors=preparation.prepare_missing_texts(['a'],{'a':audio},{},root/'TXT',root,{'context_profile':{'title':'Game'}},lambda x:None,lambda:False,on_theme=seen.append)
   self.assertTrue(ready);research.assert_called_once();self.assertEqual(seen[0]['title'],'Game')
 def test_cancellation_preserves_completed_transcript_for_resume(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);audio=root/'a.wav';audio.write_bytes(b'audio');cancel=[False]
   def transcribe(paths,config,emit,cancelled,on_result):on_result(0,{'transcript':'Hello world'});cancel[0]=True
   with patch('transcription_backend.run_local_batch',side_effect=transcribe),patch('audio_translation.generate_text') as translate:
    with self.assertRaises(RuntimeError):preparation.prepare_missing_texts(['a'],{'a':audio},{},root/'TXT',root,{},lambda x:None,lambda:cancel[0])
   translate.assert_not_called();self.assertEqual(len(list((root/'revisoes'/'preparacao_textos').glob('*.json'))),1)
 def test_prepared_transcript_is_translated_without_repeating_asr(self):
  import audio_translation as translation
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);audio=root/'a.wav';audio.write_bytes(b'audio')
   config={'translator':'argos','source':'en','context_profile':{},'_prepared_transcription':{'transcript':'Hello world','source_language':'en'}}
   with patch('transcription_backend.run_local',return_value={'translation':'Olá mundo'}) as run:
    text,language=translation._generate_text(audio,root/'TXT'/'a.txt',root,'a',config,lambda x:None)
   self.assertEqual(text,'Olá mundo');self.assertIsNone(run.call_args.args[0]);self.assertEqual(run.call_args.args[1],'Hello world');self.assertFalse(run.call_args.args[3])
 def test_existing_texts_emit_explicit_reason_without_asr(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'a.txt').write_text('Texto existente');audio=root/'a.wav';audio.write_bytes(b'audio');logs=[]
   with patch('transcription_backend.run_local_batch') as run:
    preparation.prepare_missing_texts(['a'],{'a':audio},{'a':root/'a.txt'},root,root,{},logs.append,lambda:False)
   run.assert_not_called();self.assertTrue(any('NENHUM TXT AUSENTE' in line for line in logs))
 def test_apply_settings_enables_missing_audio_scan(self):
  from types import SimpleNamespace
  from unittest.mock import Mock
  import batch_tab
  class Var:
   def __init__(self,value):self.value=value
   def get(self):return self.value
   def set(self,value):self.value=value
  app=SimpleNamespace(running=False,root=None,auto_translation_settings={},prepare_texts_first_var=Var('1'),auto_translation_var=Var('0'),speech_language_var=Var(''),stems=['existing'],statuses={},available_translation_stems=lambda:['existing','missing'],populate_queue=Mock(),save_voice_settings=Mock(),emit_log=Mock())
  with patch('audio_translation.choose_settings',return_value={'language':'Português (Brasil)','prepare_before_dubbing':True}):batch_tab.BatchApp.configure_auto_translation(app)
  self.assertEqual(app.auto_translation_var.get(),'1');self.assertIn('missing',app.stems);app.populate_queue.assert_called_once()
if __name__=='__main__':unittest.main()
