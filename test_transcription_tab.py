import tempfile,tkinter as tk,time,unittest
from pathlib import Path
from unittest.mock import patch
from transcription_tab import TranscriptionApp
import audio_translation

class WorkspaceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=tk.Tk();self.root.geometry('1500x850+20+20');self.addCleanup(self.root.destroy)
  self.base=Path(self.temp.name);self.parent=tk.Frame(self.root);self.parent.pack(fill='both',expand=True)
  with patch('audio_translation.load_last_settings',return_value=audio_translation.settings()):self.app=TranscriptionApp(self.parent,self.base,theme={'surface':'#202B3B','text':'#F8FAFC','input':'#111827','input_text':'#F8FAFC'})
  self.app.confirm_theme.set(False)
  self.root.update()
 def wait_done(self):
  deadline=time.monotonic()+8
  while self.app.running and time.monotonic()<deadline:self.root.update();time.sleep(.03)
  self.root.update();self.assertFalse(self.app.running)
 def test_pause_and_resume_after_reopening_skips_finished_files(self):
  import json
  a=self.base/'one.wav';b=self.base/'two.wav'
  a.write_bytes(b'a');b.write_bytes(b'b');self.app.add_paths([a,b])
  def transcribe(path,*args,**kwargs):
   if path==a:self.app.pause_event.set()
   return {'transcript':'Hello '+path.stem,'source_language':'en'}
  with patch('audio_translation.save_last_settings'),patch('transcription_backend.run_local_batch') as batch,patch('transcription_backend.run_local',side_effect=transcribe):
   # Per-file path exercises pause at the boundary without an external worker.
   self.app.start('both',order='per_file')
   deadline=time.monotonic()+4
   while (not self.app.checkpoint_path.exists() or not json.loads(self.app.checkpoint_path.read_text()).get('transcribed')) and time.monotonic()<deadline:self.root.update();time.sleep(.02)
   state=json.loads(self.app.checkpoint_path.read_text());self.assertEqual(state['transcribed'],[str(a)]);self.assertTrue(self.app.running)
   self.app.cancel();self.wait_done()
  old=self.parent;old.destroy();self.parent=tk.Frame(self.root);self.parent.pack()
  with patch('audio_translation.load_last_settings',return_value=audio_translation.settings()):self.app=TranscriptionApp(self.parent,self.base)
  self.app.confirm_theme.set(False)
  with patch('audio_translation.save_last_settings'),patch('transcription_backend.run_local',return_value={'transcript':'Hello two','source_language':'en'}) as run,patch('semantic_review.ready',return_value=True),patch('transcription_backend.translate_api',return_value='Olá'),patch('transcription_backend.load_key',return_value='fake'):
   # The original translator is local; stub both worker modes safely.
   run.side_effect=lambda path,text,*args,**kwargs: {'transcript':'Hello two','source_language':'en'} if path else {'translation':'Olá'}
   self.app.resume_saved();self.wait_done()
  state=json.loads(self.app.checkpoint_path.read_text());self.assertTrue(state['complete']);self.assertEqual(set(state['completed']),{str(a),str(b)})
  self.assertEqual(sum(call.args[0]==a for call in run.call_args_list),0)
 def test_completed_theme_job_blinks_and_opening_theme_acknowledges(self):
  self.app.blink_theme();self.assertTrue(self.app.theme_unread)
  self.app.configure_context();self.assertFalse(self.app.theme_unread);self.assertEqual(self.app.theme_button.cget('bg'),'#2DD4BF')
 def test_glossary_rules_green_filter_preserves_full_text_and_edits(self):
  from transcription_tab import GlossaryView
  header=tk.Frame(self.parent);box=tk.Text(self.parent)
  original='# IA — proposta contextual\nWalker => errante\n\n# Justificativa preservada\nCrystal => Cristal'
  box.insert('1.0',original);view=GlossaryView(box,header);self.root.update()
  self.assertEqual(str(box.tag_cget('glossary_rule','foreground')),'#4ADE80')
  self.assertIn('glossary_rule',box.tag_names('2.0'))
  view.toggle.invoke();self.root.update()
  self.assertIn('glossary_hidden',box.tag_names('1.0'));self.assertNotIn('glossary_hidden',box.tag_names('2.0'))
  self.assertEqual(box.get('1.0','end-1c'),original)
  box.insert('end','\nNew => Novo');self.root.update()
  self.assertIn('glossary_rule',box.tag_names('6.0'))
  view.toggle.invoke();self.root.update();self.assertFalse(box.tag_ranges('glossary_hidden'))
  self.assertIn('# Justificativa preservada',box.get('1.0','end-1c'))
 def test_glossary_add_fields_create_manual_rule_with_filter(self):
  from transcription_tab import GlossaryView
  pane=tk.Frame(self.parent);pane.pack();header=tk.Frame(pane);header.pack();box=tk.Text(pane);box.pack()
  box.insert('1.0','# Explicação antiga\nOld => Antigo');view=GlossaryView(box,header)
  view.create_adder(pane,box,self.app.button,'#202B3B','#FFFFFF','#111827')
  view.toggle.invoke();view.new_text.insert('1.0','Long original\nphrase');view.new_reference.insert('1.0','Referência longa')
  view.add_button.invoke();self.root.update()
  text=box.get('1.0','end-1c');self.assertIn('Long original phrase => Referência longa',text);self.assertIn('# USUÁRIO —',text);self.assertIn('# Explicação antiga',text)
  self.assertEqual(view.new_text.get('1.0','end-1c'),'')
  with self.assertRaises(ValueError):view.add_rule('Old','Outro')
  with self.assertRaises(ValueError):view.add_rule('','Outro')
 def test_saved_translation_cleanup_preserves_backup(self):
  audio=self.base/'old.wav';audio.write_bytes(b'audio');self.app.add_paths([audio]);self.app.list.selection_set(0)
  self.app.write_final(self.app.final_path(audio),'Hello')
  self.app.write_final(self.app.final_path(audio,True),'"Hello" translates to "Olá"')
  self.app.selected();self.app.clean_saved_translation(audio)
  self.assertEqual(self.app.final_path(audio,True).read_text().strip(),'Olá')
  self.assertEqual(self.app.texts['translation'].get('1.0','end-1c'),'Olá')
  self.assertIn('translates to',next((self.base/'revisoes'/'limpeza_traducao').rglob('*.txt')).read_text())
 def test_context_menu_and_review_theme(self):
  from types import SimpleNamespace
  audio=self.base/'a.wav';audio.write_bytes(b'audio');self.app.add_paths([audio]);self.root.update()
  with patch('tkinter.Menu.tk_popup'),patch('tkinter.Menu.grab_release'):
   self.app.context_menu(SimpleNamespace(y=self.app.list.bbox(0)[1]+1,x_root=10,y_root=10))
  self.assertEqual(self.app.shown,audio)
  with patch('semantic_review.load_key',return_value=''):
   self.app.configure_review_apis();self.root.update()
  windows=[w for w in self.parent.winfo_children() if isinstance(w,tk.Toplevel)]
  self.assertTrue(windows);self.assertEqual(windows[-1].cget('bg'),'#202B3B')
 def test_invalid_translation_preserves_final(self):
  audio=self.base/'a.wav';audio.write_bytes(b'audio');self.app.add_paths([audio]);self.app.list.selection_set(0)
  self.app.results[audio]={'transcript':'Hello'};self.app.selected();self.app.provider.set('Luna — API');self.app.review.set(False)
  target=self.app.final_path(audio,True);self.app.write_final(target,'Anterior válido')
  with patch('transcription_backend.load_key',return_value='fake'),patch('audio_translation.save_last_settings'),patch('transcription_backend.translate_api',return_value='Here is the translation: Olá'):
   self.app.start('translate');self.wait_done()
  self.assertEqual(target.read_text().strip(),'Anterior válido')
 def test_double_click_opens_clicked_media_during_processing(self):
  from types import SimpleNamespace
  audio=self.base/'a.wav';video=self.base/'b.mp4';audio.write_bytes(b'a');video.write_bytes(b'v');self.app.add_paths([audio,video]);self.root.update()
  self.app.list.selection_set(0);self.app.audio_player.set_playback_mode('windows');self.app.running=True
  with patch('transcription_tab.os.startfile') as launch:
   self.app.play_file(SimpleNamespace(y=self.app.list.bbox(1)[1]+1))
  launch.assert_called_once_with(str(video));self.app.running=False
 def test_double_click_ignores_blank_and_text(self):
  from types import SimpleNamespace
  path=self.base/'a.txt';path.write_text('text');self.app.add_paths([path]);self.root.update()
  with patch('transcription_tab.os.startfile') as launch:
   self.app.play_file(SimpleNamespace(y=self.app.list.bbox(0)[1]+1));self.app.play_file(SimpleNamespace(y=9999))
  launch.assert_not_called()
 def test_ffplay_double_click_routes_audio_and_video_internally(self):
  from types import SimpleNamespace
  audio=self.base/'a.wav';video=self.base/'v.mp4';text=self.base/'x.txt'
  for path in (audio,video,text):path.write_bytes(b'content')
  self.app.add_paths([audio,video,text]);self.root.update()
  self.app.audio_player.set_playback_mode('ffplay')
  with patch.object(self.app.audio_player,'play_one') as play,patch('transcription_tab.os.startfile') as external:
   self.app.play_file(SimpleNamespace(y=self.app.list.bbox(0)[1]+1))
   self.assertEqual(play.call_args.args[0],audio);self.assertEqual(play.call_args.kwargs['playlist'],[audio]);external.assert_not_called()
  preview=SimpleNamespace(closed=False,close=lambda:None)
  with patch('video_preview.VideoPreview',return_value=preview) as view,patch('transcription_tab.os.startfile') as external:
   self.app.play_file(SimpleNamespace(y=self.app.list.bbox(1)[1]+1))
   self.assertEqual(view.call_args.args[1],video);self.assertEqual(view.call_args.args[0].files,[video]);external.assert_not_called()
  self.app.previews.clear()
 def test_inline_asr_settings_and_local_dialog_stay_in_sync(self):
  self.app.transcriber.set('Whisper (OpenAI)');self.app.asr_model.set('large-v3');self.app.processing.set('GPU (CUDA)');self.app.source.set('de')
  self.assertEqual(self.app.config['engine'],'openai-whisper');self.assertEqual(self.app.config['whisper_model'],'large-v3');self.assertEqual(self.app.config['device'],'cuda')
  self.app.transcriber.set('Whisper-WebUI / large-v3 (local)')
  self.assertEqual(self.app.config['transcription_profile'],'whisper-webui-large-v3');self.assertEqual(self.app.asr_model.get(),'large-v3');self.assertEqual(str(self.app.asr_model_combo.cget('state')),'disabled')
  value=audio_translation.settings({'engine':'openai-whisper','whisper_model':'tiny','device':'cpu','source':'en'})
  with patch('audio_translation.choose_settings',return_value=value),patch('audio_translation.save_last_settings'):self.app.configure_local()
  self.assertEqual(self.app.transcriber.get(),'Whisper (OpenAI)');self.assertEqual(self.app.asr_model.get(),'tiny');self.assertEqual(self.app.processing.get(),'CPU');self.assertEqual(self.app.source.get(),'en')
 def test_extended_translator_runs_from_main_tab(self):
  self.app.texts['source'].insert('1.0','Hello');self.app.provider.set('Gemini — API')
  with patch('semantic_review.ready',return_value=True),patch('semantic_review.translate',return_value='Olá') as translate,patch('audio_translation.save_last_settings'):
   self.app.start('translate');self.wait_done()
  self.assertEqual(translate.call_args.args[2],'gemini-api');self.assertEqual(self.app.results[None]['translation'],'Olá')
 def test_real_player_navigation_syncs_list_and_three_texts(self):
  from types import SimpleNamespace
  import wave
  a=self.base/'a.wav';b=self.base/'b.wav';txt=self.base/'extra.txt';txt.write_text('other')
  for path in (a,b):
   with wave.open(str(path),'wb') as wav:wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000);wav.writeframes(bytes(1600))
  self.app.add_paths([a,txt,b])
  for path,source,target in [(a,'First','Primeiro'),(b,'Second','Segundo')]:
   self.app.write_final(self.app.final_path(path),source);self.app.write_final(self.app.final_path(path,True),target)
  self.app.list.selection_set(0);self.app.selected();self.root.update()
  with patch.object(self.app.audio_player,'_refresh_waveforms'):
   self.app.play_file(SimpleNamespace(y=self.app.list.bbox(0)[1]+1));self.root.update()
   self.assertIsNotNone(self.app.scene_editor);self.assertEqual(len(self.app.scene_editor.notebook.tabs()),3)
   self.app.audio_player.navigate(1);self.root.update()
   self.assertEqual(self.app.list.curselection(),(2,));self.assertEqual(self.app.shown,b)
   self.assertEqual(self.app.scene_editor.texts['source'].get('1.0','end-1c').strip(),'Second')
   box=self.app.scene_editor.texts['translation'];box.delete('1.0','end');box.insert('1.0','Segundo editado');self.root.update()
   self.assertEqual(self.app.texts['translation'].get('1.0','end-1c'),'Segundo editado')
   self.app.save_scene_editor('translation');self.assertEqual(self.app.final_path(b,True).read_text().strip(),'Segundo editado')
   self.app.audio_player.navigate(-1);self.root.update();self.assertEqual(self.app.list.curselection(),(0,))
   self.assertEqual(self.app.scene_editor.texts['translation'].get('1.0','end-1c').strip(),'Primeiro')
  self.app.audio_player.close_window()
 def test_scene_editor_preserves_unsaved_edits_and_receives_main_edits(self):
  a=self.base/'a.wav';b=self.base/'b.wav'
  for path in (a,b):path.write_bytes(b'audio')
  self.app.add_paths([a,b]);self.app.results[a]={'transcript':'Origin A','translation':'A'};self.app.results[b]={'transcript':'Origin B','translation':'B'}
  host=tk.Toplevel(self.parent);self.app.audio_player.current_context_key=str(a);self.app.build_scene_editor(host)
  self.app.select_from_player(str(a),0);self.root.update()
  box=self.app.scene_editor.texts['translation'];box.delete('1.0','end');box.insert('1.0','Unsaved A')
  self.app.audio_player.current_context_key=str(b);self.app.refresh_scene_editor();self.app.select_from_player(str(b),1);self.root.update()
  self.app.audio_player.current_context_key=str(a);self.app.select_from_player(str(a),0);self.root.update()
  self.assertEqual(self.app.scene_editor.texts['translation'].get('1.0','end-1c'),'Unsaved A')
  box=self.app.texts['source'];box.delete('1.0','end');box.insert('1.0','Main edited');self.root.update()
  self.assertEqual(self.app.scene_editor.texts['source'].get('1.0','end-1c'),'Main edited');host.destroy()
 def test_compact_translator_and_key_portals(self):
  from unittest.mock import patch
  self.root.update()
  self.assertFalse(bool(self.app.provider_combo.pack_info()['expand']))
  self.assertGreaterEqual(int(self.app.provider_combo.cget('width')),max(map(len,audio_translation.TRANSLATOR_LABELS.values())))
  self.assertGreater(self.app.target_combo.winfo_rootx(),self.app.provider_combo.winfo_rootx()+self.app.provider_combo.winfo_width())
  with patch('webbrowser.open') as open_url:
   for provider in ('OpenAI / ChatGPT','OpenAI / Codex','Luna','Sol','Claude','Gemini'):self.app.open_key_portal(provider)
  self.assertEqual([call.args[0] for call in open_url.call_args_list],['https://platform.openai.com/api-keys']*4+['https://platform.claude.com/settings/keys','https://aistudio.google.com/apikey'])
 def test_theme_confirmation_cancels_all_four_actions_and_persists_toggle(self):
  self.app.context['title']='Meu tema';self.app.context_caption.set(self.app.theme_title());self.app.confirm_theme.set(True)
  with patch('transcription_tab.messagebox.askyesno',return_value=False) as ask,patch('transcription_backend.run_local') as run:
   for mode in ('transcribe','translate','both','review'):self.app.start(mode)
  self.assertEqual(ask.call_count,4);run.assert_not_called();self.assertFalse(self.app.running)
  self.assertIn('Meu tema',ask.call_args.args[1]);self.assertEqual(self.app.theme_headline.get(),'Tema: Meu tema')
  self.app.confirm_theme.set(False);self.app.save_ui_preferences();self.assertFalse(self.app.load_ui_preferences()['confirm_theme'])
 def test_theme_button_header_order_and_translation_processing_fit(self):
  self.root.update()
  self.assertEqual(self.app.theme_button.cget('bg'),'#2DD4BF');self.assertEqual(int(self.app.theme_button.grid_info()['rowspan']),2)
  self.assertLess(self.app.local_tools_button.winfo_rootx(),self.app.review_api_button.winfo_rootx())
  self.app.provider.set(audio_translation.TRANSLATOR_LABELS['qwen-game-local']);self.app.translation_processing.set('CPU')
  self.assertEqual(self.app.config['translation_device'],'cpu')
  self.app.provider.set('Gemini — API');self.assertEqual(self.app.translation_processing.get(),'API — remoto');self.assertEqual(str(self.app.translation_processing_combo.cget('state')),'disabled')
  self.app.provider.set(audio_translation.TRANSLATOR_LABELS['qwen-game-local']);self.assertEqual(self.app.translation_processing.get(),'CPU')
  self.root.update();box=self.app.translation_processing_combo
  self.assertTrue(box.winfo_ismapped());self.assertLessEqual(box.winfo_rootx()+box.winfo_width(),self.parent.winfo_rootx()+self.parent.winfo_width())
 def test_register_key_opens_configuration_not_browser_and_activation_saves(self):
  import semantic_review
  from tkinter import ttk
  with patch('semantic_review.load_key',return_value=''),patch('semantic_review.settings',return_value=dict(semantic_review.DEFAULTS)),patch('webbrowser.open') as browser:
   window=self.app.configure_provider_key('Gemini — API');self.root.update();browser.assert_not_called()
  notebook=next(w for w in self.descendants(window) if isinstance(w,ttk.Notebook));page=window.nametowidget(notebook.select())
  widgets=list(self.descendants(page));key=next(w for w in widgets if isinstance(w,ttk.Entry) and w.cget('show'));model=next(w for w in widgets if isinstance(w,ttk.Combobox))
  key.insert(0,'test-not-real-key');activate=next(w for w in widgets if isinstance(w,tk.Button) and w.cget('text')=='ATIVAR CHAVE')
  with patch('semantic_review.save_settings') as save:
   activate.invoke();self.assertEqual(save.call_args.args[3],'test-not-real-key');model.set('gemini-test');activate.invoke()
  self.assertEqual(save.call_args.args[3],'test-not-real-key');self.assertEqual(save.call_args.args[0]['gemini_model'],'gemini-test');window.destroy()
 @staticmethod
 def descendants(widget):
  for child in widget.winfo_children():
   yield child
   yield from WorkspaceTests.descendants(child)
 def test_api_dialog_imports_env_and_saves_exact_fields(self):
  import semantic_review
  from tkinter import ttk
  env=self.base/'config.env';content='OPENAI_API_KEY=test-secret-value\nOPENAI_BASE_URL=https://api.openai.com/v1\nOPENAI_MODEL=gpt-4.1-mini\nCODEX_MODEL=gpt-5-codex\n';env.write_text(content)
  with patch('semantic_review.load_key',return_value=''),patch('semantic_review.settings',return_value=dict(semantic_review.DEFAULTS)):
   window=self.app.configure_provider_key('OpenAI / Codex');self.root.update()
  notebook=next(w for w in self.descendants(window) if isinstance(w,ttk.Notebook));page=window.nametowidget(notebook.select());widgets=list(self.descendants(page))
  import_button=next(w for w in widgets if isinstance(w,tk.Button) and w.cget('text')=='IMPORTAR .env')
  with patch('api_settings_ui.filedialog.askopenfilename',return_value=str(env)),patch('semantic_review.save_settings') as save:
   import_button.invoke();save.assert_not_called()
   combos=[w for w in widgets if isinstance(w,ttk.Combobox)];self.assertEqual([w.get() for w in combos],['gpt-4.1-mini','gpt-5-codex']);self.assertTrue(combos[0].cget('values'))
   key=next(w for w in widgets if isinstance(w,ttk.Entry) and w.cget('show'));self.assertEqual(key.get(),'test-secret-value')
   save_button=next(w for w in self.descendants(window) if isinstance(w,tk.Button) and w.cget('text')=='SALVAR E ATIVAR');save_button.invoke()
  self.assertEqual(save.call_args.args[1],'test-secret-value');self.assertEqual(save.call_args.args[0]['codex_model'],'gpt-5-codex');self.assertEqual(env.read_text(),content)
 def test_api_query_fills_models_and_tests_selected_model(self):
  import semantic_review
  from tkinter import ttk
  with patch('semantic_review.load_key',return_value='test-secret'),patch('semantic_review.settings',return_value=dict(semantic_review.DEFAULTS)):
   window=self.app.configure_provider_key('OpenAI / Codex');self.root.update()
  notebook=next(w for w in self.descendants(window) if isinstance(w,ttk.Notebook));page=window.nametowidget(notebook.select());widgets=list(self.descendants(page))
  query=next(w for w in widgets if isinstance(w,tk.Button) and w.cget('text')=='CONSULTAR MODELOS')
  with patch('api_configuration.list_models',return_value={'models':['gpt-4.1-mini','gpt-5-codex'],'partial':False}):
   query.invoke();deadline=time.monotonic()+2
   while str(query.cget('state'))=='disabled' and time.monotonic()<deadline:self.root.update();time.sleep(.02)
  combos=[w for w in widgets if isinstance(w,ttk.Combobox)];self.assertIn('gpt-5-codex',combos[1].cget('values'));combos[1].set('gpt-5-codex')
  checks=[w for w in widgets if isinstance(w,tk.Button) and w.cget('text')=='TESTAR ESTE MODELO']
  with patch('api_configuration.test_model',return_value='Consulta aceita') as test:
   checks[1].invoke();deadline=time.monotonic()+2
   while str(checks[1].cget('state'))=='disabled' and time.monotonic()<deadline:self.root.update();time.sleep(.02)
  self.assertEqual(test.call_args.args[3],'gpt-5-codex');window.destroy()
 def test_invalid_model_blocks_before_transcribing_audio(self):
  import semantic_review
  audio=self.base/'a.wav';audio.write_bytes(b'audio');self.app.add_paths([audio]);self.app.list.selection_set(0);self.app.provider.set('OpenAI / Codex — API')
  with patch('semantic_review.settings',return_value={**semantic_review.DEFAULTS,'codex_model':'AbCdEfGhIjKlMnOp'}),patch('semantic_review.load_key',return_value='test-secret'),patch('transcription_tab.messagebox.showwarning') as warning,patch('transcription_backend.run_local') as run:
   self.app.start('both')
  run.assert_not_called();self.assertFalse(self.app.running);self.assertIn('identificador',warning.call_args.args[1])
 def test_long_file_notes_do_not_shrink_file_list_and_follow_selection(self):
  a=self.base/'a.wav';b=self.base/'b.mp4'
  for file in (a,b):file.write_bytes(b'data')
  self.app.add_paths([a,b]);self.root.update();height=self.app.list.winfo_height()
  self.app.results[a]={'quality_warnings':['Long observation '*200]};self.app.results[b]={'quality_warnings':['Video warning']}
  self.app.list.selection_set(0);self.app.selected();self.root.update()
  self.assertEqual(self.app.list.winfo_height(),height);self.assertIn('Long observation',self.app.file_notes.get('1.0','end'))
  self.assertGreater(self.app.file_notes.winfo_rootx(),self.app.log_box.winfo_rootx());self.assertTrue(self.app.file_notes.cget('yscrollcommand'))
  self.app.list.selection_clear(0,'end');self.app.list.selection_set(1);self.app.selected();self.root.update()
  self.assertEqual(self.app.file_notes.get('1.0','end-1c'),'Video warning');self.assertEqual(self.app.notes_caption.get(),'b.mp4')
 def test_theme_api_research_previews_and_applies_only_after_click(self):
  from tkinter import ttk
  self.app.context['title']='My Game';self.app.configure_context();self.root.update()
  window=next(w for w in self.parent.winfo_children() if isinstance(w,tk.Toplevel));widgets=list(self.descendants(window))
  selector=next(w for w in widgets if isinstance(w,ttk.Combobox) and 'Claude — API' in w.cget('values'));selector.set('Claude — API')
  result={'facts':[],'instructions':'Specific fantasy context','terms':[{'source':'Crystal','preferred':'Cristal','status':'proposed','reason':'Item','url':'https://example.test','quote':'Crystal is an item'}],'asr_hints':['Crystal'],'uncertainties':[]}
  button=next(w for w in widgets if isinstance(w,tk.Button) and w.cget('text')=='PESQUISAR TEMA\nNA INTERNET')
  with patch('semantic_review.ready',return_value=True),patch('theme_research.deep_research',return_value=('Retrieved sources',result)) as analyze:
   button.invoke();self.wait_done()
  self.assertEqual(analyze.call_args.args[2],'Claude — API');self.assertNotIn('Specific fantasy context',self.app.context['instructions'])
  preview=next(w for w in window.winfo_children() if isinstance(w,tk.Toplevel));apply=next(w for w in self.descendants(preview) if isinstance(w,tk.Button) and w.cget('text')=='APLICAR CONTEXTO E GLOSSÁRIO');apply.invoke()
  save=next(w for w in widgets if isinstance(w,tk.Button) and w.cget('text')=='SALVAR TEMA');save.invoke()
  self.assertIn('Specific fantasy context',self.app.context['instructions']);self.assertIn('Crystal => Cristal',self.app.context['glossary']);self.assertEqual(self.app.context['research_provider'],'Claude — API')
  self.assertTrue(list((self.base/'revisoes'/'pesquisa_tema').glob('*.json')))
 def test_theme_mode_is_exclusive_scrollbars_and_buttons_aligned(self):
  from tkinter import ttk
  self.app.configure_context();self.root.update();window=next(w for w in self.parent.winfo_children() if isinstance(w,tk.Toplevel));widgets=list(self.descendants(window))
  radios=[w for w in widgets if isinstance(w,ttk.Radiobutton) and str(w.cget('value')) in ('local','api')];self.assertEqual(len(radios),2);self.assertEqual(str(radios[0].cget('variable')),str(radios[1].cget('variable')))
  local=next(w for w in radios if w.cget('value')=='local');local.invoke();self.root.update()
  combo=next(w for w in widgets if isinstance(w,ttk.Combobox) and 'Claude — API' in w.cget('values'));self.assertEqual(str(combo.cget('state')),'disabled')
  api=next(w for w in radios if w.cget('value')=='api');api.invoke();self.assertEqual(str(combo.cget('state')),'readonly')
  boxes=[w for w in widgets if isinstance(w,tk.Text)];self.assertEqual(len(boxes),5);self.assertEqual(sum(bool(w.cget('yscrollcommand')) for w in boxes),3)
  buttons=[next(w for w in widgets if isinstance(w,tk.Button) and w.cget('text')==label) for label in ('CADASTRAR / ATIVAR API','PESQUISAR TEMA\nNA INTERNET','CANCELAR\nPESQUISA')]
  self.assertEqual(buttons[1].cget('bg'),'#22C55E');self.assertLess(buttons[0].winfo_rootx(),buttons[1].winfo_rootx());self.assertLess(buttons[1].winfo_rootx(),buttons[2].winfo_rootx());window.destroy()
 def test_theme_glossary_height_and_unsaved_close_yes_no(self):
  self.app.configure_context();self.root.update();window=next(w for w in self.parent.winfo_children() if isinstance(w,tk.Toplevel));widgets=list(self.descendants(window));boxes=[w for w in widgets if isinstance(w,tk.Text)]
  self.assertGreater(boxes[1].winfo_height(),70)
  self.assertFalse(any(w.cget('text')=='SALVAR E USAR IA LOCAL' for w in widgets if isinstance(w,tk.Button)))
  boxes[1].insert('end','Crystal => Cristal')
  with patch('transcription_tab.messagebox.askyesno',return_value=True) as ask:window.tk.call(window.protocol('WM_DELETE_WINDOW'))
  self.assertTrue(ask.called);self.assertIn('Crystal => Cristal',self.app.context['glossary'])
  self.app.configure_context();self.root.update();window=next(w for w in self.parent.winfo_children() if isinstance(w,tk.Toplevel));boxes=[w for w in self.descendants(window) if isinstance(w,tk.Text)];boxes[1].insert('end','\nOther => Outro')
  with patch('transcription_tab.messagebox.askyesno',return_value=False):window.tk.call(window.protocol('WM_DELETE_WINDOW'))
  self.assertNotIn('Other',self.app.context['glossary'])
 def test_export_current_text_copy_and_handled_write_error(self):
  self.app.texts['translation'].insert('1.0','Tradução editada');self.app.notebook.select(1);target=self.base/'exported.txt'
  with patch('transcription_tab.filedialog.asksaveasfilename',return_value=str(target)):self.app.export()
  self.assertEqual(target.read_text().strip(),'Tradução editada');self.assertIn('TXT exportado',self.app.status.get())
  with patch('transcription_tab.filedialog.asksaveasfilename',return_value=str(target)),patch.object(self.app,'write_final',side_effect=PermissionError('Acesso negado')),patch('transcription_tab.messagebox.showerror') as error:self.app.export()
  error.assert_called_once();self.assertEqual(target.read_text().strip(),'Tradução editada')
 def test_no_theme_ignores_all_context_and_colors_header(self):
  self.app.context.update(title='Game',instructions='Context',glossary='glass => Cristal',asr_hints='glass',research='Sources');self.app.context_caption.set('Game');self.app.update_theme_heading()
  self.assertEqual(str(self.app.theme_heading.cget('foreground')),'#2DD4BF');self.assertEqual(self.app.effective_context()['title'],'Game')
  self.app.no_theme.set(True);self.app.toggle_no_theme();self.assertEqual(self.app.effective_context(),{});self.assertEqual(self.app.theme_headline.get(),'Sem tema');self.assertEqual(str(self.app.theme_heading.cget('foreground')),'#FB923C');self.assertTrue(self.app.load_ui_preferences()['no_theme']);self.assertEqual(self.app.context['title'],'Game')
 def test_theme_export_import_and_reset(self):
  self.app.context.update(title='Exported Game',glossary='glass => Cristal');self.app.configure_context();self.root.update();window=next(w for w in self.parent.winfo_children() if isinstance(w,tk.Toplevel));widgets=list(self.descendants(window))
  def button(label):return next(w for w in widgets if isinstance(w,tk.Button) and w.cget('text')==label)
  file=self.base/'theme.json'
  with patch('transcription_tab.filedialog.asksaveasfilename',return_value=str(file)):button('EXPORTAR TEMA PRESENTE').invoke()
  import json
  self.assertEqual(json.loads(file.read_text())['theme']['title'],'Exported Game')
  with patch('transcription_tab.messagebox.askyesno',return_value=True):button('RESETAR TEMA SALVO').invoke()
  self.assertFalse(self.app.has_theme());self.assertEqual(self.app.theme_headline.get(),'Sem tema')
  with patch('transcription_tab.filedialog.askopenfilename',return_value=str(file)):button('IMPORTAR TEMA').invoke()
  self.assertFalse(self.app.has_theme());button('SALVAR TEMA').invoke();self.assertEqual(self.app.context['title'],'Exported Game');self.assertFalse(self.app.no_theme.get())
 def test_audio_translation_revision_and_original_preservation(self):
  original=self.base/'example.wav';original.write_bytes(b'original');self.app.add_paths([original]);self.app.list.selection_set(0);self.app.selected()
  self.app.provider.set('Luna — API');self.app.review.set(True)
  def translate(text,target,config,key,emit,cancelled,draft=None,**kwargs):return 'Revisão final' if draft is not None else 'Olá mundo'
  with patch('transcription_backend.load_key',return_value='fake-key'),patch('audio_translation.save_last_settings'),patch('transcription_backend.run_local',return_value={'transcript':'Hello world','source_language':'en','translation':''}),patch('transcription_backend.translate_api',side_effect=translate),patch('semantic_review.review',return_value={'evaluated':True,'needs_review':True,'issues':['Sugestão do revisor'],'corrected_translation':'Revisão final'}):
   self.app.start('both');self.wait_done()
  self.assertEqual(original.read_bytes(),b'original')
  self.assertEqual(self.app.results[original]['revision'],'Revisão final')
  self.assertEqual((self.app.last_output/'TRANSCRIÇÕES'/'example.txt').read_text().strip(),'Hello world')
  self.assertEqual((self.app.last_output/'TRADUÇÕES'/'example.txt').read_text().strip(),'Revisão final')
  self.assertEqual(len(list(self.app.last_output.rglob('*.*'))),2)
  metadata=next((self.base/'revisoes'/'transcricoes_traducoes').rglob('*.json')).read_text();self.assertNotIn('fake-key',metadata)
 def test_text_translation_without_audio(self):
  self.app.texts['source'].insert('1.0','Hello');self.app.provider.set('Luna — API')
  with patch('transcription_backend.load_key',return_value='fake'),patch('audio_translation.save_last_settings'),patch('transcription_backend.translate_api',return_value='Olá'):
   self.app.start('translate');self.wait_done()
  self.assertEqual(self.app.texts['translation'].get('1.0','end-1c'),'Olá')
 def test_api_settings_mask_key_and_keep_actions_visible(self):
  with patch('transcription_backend.load_key',return_value='test-only-not-real'):
   self.app.configure_api();self.root.update()
  window=next(child for child in self.parent.winfo_children() if isinstance(child,tk.Toplevel))
  widgets=[]
  def visit(parent):
   for child in parent.winfo_children():widgets.append(child);visit(child)
  visit(window)
  self.assertTrue(any(isinstance(widget,tk.Entry) and widget.cget('show') for widget in widgets))
  for button in (widget for widget in widgets if isinstance(widget,tk.Button)):
   self.assertTrue(button.winfo_ismapped());self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),window.winfo_rootx()+window.winfo_width())
  window.destroy()

 def test_context_dialog_presets_and_large_v3_profile(self):
  from tkinter import ttk
  self.app.configure_context();self.root.update()
  window=next(child for child in self.parent.winfo_children() if isinstance(child,tk.Toplevel))
  widgets=[]
  def visit(parent):
   for child in parent.winfo_children():widgets.append(child);visit(child)
  visit(window)
  preset=next(widget for widget in widgets if isinstance(widget,ttk.Combobox) and 'Moss 1 VR' in widget.cget('values'))
  preset.set('Moss 1 VR');preset.event_generate('<<ComboboxSelected>>');self.root.update()
  save=next(widget for widget in widgets if isinstance(widget,tk.Button) and widget.cget('text')=='SALVAR TEMA')
  self.assertLessEqual(save.winfo_rooty()+save.winfo_height(),window.winfo_rooty()+window.winfo_height())
  save.invoke();self.root.update()
  self.assertEqual(self.app.context['title'],'Moss 1 VR')
  with patch('audio_translation.save_last_settings'):self.app.use_large_v3()
  self.assertEqual(self.app.config['faster_model'],'large-v3')
 def test_local_revision_does_not_require_api_key(self):
  self.app.texts['source'].insert('1.0','Take the glass.')
  self.app.texts['translation'].insert('1.0','Pegue o vidro.')
  self.app.reviewer.set('IA local — Ollama')
  with patch('transcription_backend.load_key',return_value=''),patch('audio_translation.save_last_settings'),patch('semantic_review.review',return_value={'evaluated':True,'needs_review':True,'issues':['Termo ajustado'],'corrected_translation':'Pegue o Cristal.'}):
   self.app.start('review');self.wait_done()
  self.assertEqual(self.app.results[None]['revision_engine'],'local')
  self.assertEqual((self.app.last_output/'TRADUÇÕES'/'texto_editavel.txt').read_text().strip(),'Pegue o Cristal.')

 def test_all_actions_fit_normal_viewport(self):
  for button in self.app.job_buttons:
   self.assertTrue(button.winfo_ismapped());self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),self.root.winfo_rootx()+self.root.winfo_width())

 def test_hierarchy_collision_save_and_remove(self):
  one=self.base/'voices'/'actor'/'line.wav';one.parent.mkdir(parents=True);one.write_bytes(b'a')
  other=self.base/'elsewhere'/'line.mp3';other.parent.mkdir();other.write_bytes(b'b')
  self.app.add_paths([one],self.base/'voices');self.app.add_paths([other])
  final=self.app.final_path(one);self.assertEqual(final.relative_to(self.app.last_output or self.base),Path('TRANSCRIÇÕES E TRADUÇÕES/TRANSCRIÇÕES/actor/line.txt'))
  self.app.write_final(final,'Before');self.app.results[one]={'transcript':'Before','paths':{'source':str(final)}}
  self.app.list.selection_set(0);self.app.selected();self.app.texts['source'].delete('1.0','end');self.app.texts['source'].insert('1.0','Edited');self.app.save_current()
  self.assertEqual(final.read_text().strip(),'Edited');self.assertEqual(one.read_bytes(),b'a')
  self.app.remove_selected();self.assertEqual(self.app.files,[other]);self.assertTrue(final.is_file())
  self.app.clear();self.assertFalse(self.app.results);self.assertEqual(self.app.texts['source'].get('1.0','end-1c'),'')
 def test_progress_never_goes_back_or_animates(self):
  self.app.advance_progress('transcribe',60);self.app.advance_progress('transcribe',30)
  self.assertEqual(self.app.progress_values['transcribe'],60)
  self.app.advance_progress('translate',20);self.assertEqual(self.app.progress_values['translate'],20)
  self.assertEqual(str(self.app.bars['transcribe'].cget('mode')),'determinate')
 def test_automatic_research_is_cached_for_project(self):
  self.app.context.update(title='A distinct documentary',domain='Documentário')
  self.app.texts['source'].insert('1.0','Hello');self.app.provider.set('Luna — API')
  with patch('theme_research.enrich_from_transcripts',return_value={'title':'A distinct documentary','research':'Sourced context'}),patch('transcription_backend.load_key',return_value='fake'),patch('audio_translation.save_last_settings'),patch('transcription_backend.translate_api',return_value='Olá') as translate:
   self.app.start('translate');self.wait_done()
  self.assertEqual(self.app.context['research'],'Sourced context')
  self.assertEqual(translate.call_args.kwargs['context']['research'],'Sourced context')
 def test_file_collision_cannot_overwrite_other_input(self):
  a=self.base/'first'/'line.wav';b=self.base/'second'/'line.wav'
  for path in (a,b):path.parent.mkdir();path.write_bytes(b'a')
  self.app.add_paths([a,b]);self.assertNotEqual(self.app.final_path(a),self.app.final_path(b))
 def test_split_panels_preserve_edits_and_allow_resize(self):
  self.app.texts['source'].insert('1.0','Source edit')
  self.app.texts['translation'].insert('1.0','Translation edit')
  self.app.texts['revision'].insert('1.0','Revision edit')
  self.app.notebook.select(1);self.app.split_texts.set(True);self.app.rebuild_editors();self.root.update()
  self.assertIsNone(self.app.notebook);self.assertEqual(len(self.app.text_stack.panes()),3)
  self.assertEqual(self.app.current_text_key(),'translation')
  for key in ('source','translation','revision'):self.assertTrue(self.app.texts[key].winfo_ismapped());self.assertEqual(self.app.texts[key].cget('state'),'normal')
  self.app.text_stack.sashpos(0,80);self.app.texts['translation'].insert('end',' plus')
  self.app.split_texts.set(False);self.app.rebuild_editors();self.root.update()
  self.assertEqual(self.app.texts['translation'].get('1.0','end-1c'),'Translation edit plus')
  self.assertEqual(len(self.app.workspace.panes()),2)
 def test_editors_start_larger_and_manual_divider_is_preserved(self):
  self.root.update()
  self.assertTrue(self.app.initial_dividers_set)
  self.assertGreater(self.app.editor_host.winfo_width(),self.root.winfo_width()*.65)
  self.assertGreater(self.app.workspace.sashpos(0),self.app.workspace.winfo_height()*.55)
  self.assertLess(self.app.workspace.sashpos(0),self.app.workspace.winfo_height()*.65)
  self.app.file_text_pane.sashpos(0,400);self.app.position_initial_dividers();self.assertEqual(self.app.file_text_pane.sashpos(0),400)
 def test_each_panel_saves_its_own_final_txt(self):
  source=self.base/'transcribed.txt';translated=self.base/'translated.txt'
  self.app.results[None]={'paths':{'source':str(source),'translation':str(translated)}}
  self.app.split_texts.set(True);self.app.rebuild_editors()
  self.app.texts['source'].insert('1.0','Original text');self.app.texts['translation'].insert('1.0','Texto traduzido')
  self.app.save_current('translation');self.assertEqual(translated.read_text().strip(),'Texto traduzido');self.assertFalse(source.exists())
  self.app.save_current('source');self.assertEqual(source.read_text().strip(),'Original text')
 def test_progress_titles_have_separate_row_and_output_opens_before_job(self):
  self.app.advance_progress('translate',100);self.root.update()
  bar=self.app.bars['translate'];labels=[widget for widget in bar.master.winfo_children() if isinstance(widget,tk.ttk.Label)]
  self.assertEqual(len(labels),1);self.assertGreaterEqual(bar.winfo_y(),labels[0].winfo_y()+labels[0].winfo_height())
  with patch('transcription_tab.os.startfile') as opened:self.app.open_output()
  self.assertTrue((self.base/'TRANSCRIÇÕES E TRADUÇÕES').is_dir());opened.assert_called_once()
  button=self.app.output_button
  self.assertGreater(button.winfo_rootx(),bar.winfo_rootx()+bar.winfo_width())
  self.assertLessEqual(abs(button.winfo_rooty()+button.winfo_height()-bar.winfo_rooty()-bar.winfo_height()),5)
 def test_translator_selection_and_tools_dialog_are_synchronized(self):
  self.app.provider.set(audio_translation.TRANSLATOR_LABELS['translategemma-local'])
  self.assertEqual(self.app.config['translator'],'translategemma-local')
  with patch('audio_translation.save_last_settings') as saved,patch('audio_translation.choose_settings',return_value=audio_translation.settings({'translator':'qwen-game-local'})) as choose:
   self.app.configure_local()
  self.assertEqual(saved.call_args.args[0]['translator'],'translategemma-local')
  self.assertEqual(self.app.provider.get(),audio_translation.TRANSLATOR_LABELS['qwen-game-local'])
  self.assertEqual(self.app.config['translator'],'qwen-game-local')
 def test_drop_folder_with_spaces_preserves_hierarchy(self):
  import types
  directory=self.base/'Folder With Spaces';nested=directory/'Actor';nested.mkdir(parents=True);audio=nested/'line.wav';audio.write_bytes(b'a')
  self.app.drop(types.SimpleNamespace(data='{'+str(directory)+'}'))
  deadline=time.monotonic()+5
  while self.app.discovering and time.monotonic()<deadline:self.root.update();time.sleep(.03)
  self.assertIn(audio,self.app.files);self.assertEqual(self.app.relative_paths[audio],Path('Folder With Spaces/Actor/line.wav'))
 def test_stages_finish_all_transcriptions_before_translation_and_color_warnings(self):
  paths=[self.base/'one.wav',self.base/'two__DE.wav']
  for path in paths:path.write_bytes(b'a')
  self.app.add_paths(paths);order=[];self.app.review.set(True);self.app.reviewer.set('IA local — Ollama')
  def batch(files,config,emit,cancelled,on_result):
   for index,path in enumerate(files):order.append('asr'+str(index));on_result(index,{'transcript':'Hello world','source_language':'en','translation':''})
  def translate(audio,text,*args,**kwargs):order.append('translate');return {'translation':'Olá mundo'}
  with patch('transcription_backend.run_local_batch',side_effect=batch),patch('transcription_backend.run_local',side_effect=translate),patch('audio_translation.save_last_settings'),patch('semantic_review.review',return_value={'evaluated':True,'needs_review':False,'issues':[],'corrected_translation':'Olá mundo'}):
   self.app.start('both',order='stages');self.wait_done()
  self.assertEqual(order,['asr0','asr1','translate','translate'])
  self.assertTrue(self.app.list.get(0).startswith('[OK]'));self.assertEqual(self.app.list.itemcget(0,'foreground'),'#FFFFFF')
  self.assertTrue(self.app.list.get(1).startswith('[REVISAR]'));self.assertEqual(self.app.list.itemcget(1,'foreground'),'#FFD84D')
 def test_browse_other_texts_while_processing(self):
  import threading
  paths=[self.base/'one.wav',self.base/'two.wav']
  for path in paths:path.write_bytes(b'a')
  self.app.add_paths(paths);self.app.results[paths[1]]={'transcript':'Texto anterior disponível','translation':'Tradução disponível'}
  self.app.list.selection_set(0);self.app.selected();gate=threading.Event()
  def transcribe(*args,**kwargs):gate.wait(3);return {'transcript':'Fresh source','source_language':'en'}
  with patch('transcription_backend.run_local',side_effect=transcribe),patch('audio_translation.save_last_settings'):
   self.app.start('transcribe');self.root.update()
   self.assertEqual(self.app.list.cget('state'),'normal')
   self.app.list.selection_clear(0,'end');self.app.list.selection_set(1);self.app.selected()
   self.assertEqual(self.app.texts['source'].get('1.0','end-1c'),'Texto anterior disponível')
   gate.set();self.wait_done()
  self.assertEqual(self.app.texts['source'].get('1.0','end-1c'),'Texto anterior disponível')
 def test_stage_counts_are_actual_resolved_items_not_estimated_percentages(self):
  self.app.reset_progress({'transcribe':100,'translate':100})
  self.app.update_stage_item('transcribe',1,'active');self.app.advance_progress('transcribe',.5)
  self.assertIn('arquivo 1/100',self.app.bar_labels['transcribe'].get());self.assertIn('faltam 100',self.app.bar_labels['transcribe'].get())
  self.app.update_stage_item('transcribe',1,'done');self.app.update_stage_item('transcribe',1,'done');self.app.update_stage_item('transcribe',2,'active')
  self.assertIn('processados 1/100',self.app.bar_labels['transcribe'].get());self.assertIn('faltam 99',self.app.bar_labels['transcribe'].get())
  self.app.update_stage_item('translate',1,'failed');self.app.update_stage_item('translate',2,'skipped')
  self.assertIn('faltam 98',self.app.bar_labels['translate'].get());self.assertIn('falhas 1',self.app.bar_labels['translate'].get());self.assertIn('pulados 1',self.app.bar_labels['translate'].get())
 def test_load_originals_recurses_without_texts_and_preserves_subfolders(self):
  directory=self.base/'WAV ORIGINAIS'/'Actor';directory.mkdir(parents=True)
  audio=directory/'line.wav';audio.write_bytes(b'wave');(directory/'line.txt').write_text('Text');video=directory/'video.mp4';video.write_bytes(b'video')
  self.app.load_originals();deadline=time.monotonic()+5
  while self.app.discovering and time.monotonic()<deadline:self.root.update();time.sleep(.03)
  self.assertEqual(set(self.app.files),{audio,video});self.assertEqual(self.app.relative_paths[audio],Path('Actor/line.wav'))
 def test_translation_without_semantic_verdict_is_review_not_ok(self):
  self.app.texts['source'].insert('1.0','Kopf runter, verdammt!');self.app.source.set('de')
  with patch('audio_translation.save_last_settings'),patch('transcription_backend.run_local',return_value={'translation':'Cabeça para baixo, puta merda!'}):
   self.app.start('translate');self.wait_done()
  self.assertEqual(self.app.results[None]['status'],'review')
  self.assertTrue(any('sem avaliação semântica' in warning for warning in self.app.results[None]['quality_warnings']))
 def test_invalid_semantic_response_preserves_final_translation_and_flags_review(self):
  self.app.texts['source'].insert('1.0','Original');self.app.source.set('en');self.app.review.set(True);self.app.reviewer.set('IA local — Ollama')
  with patch('audio_translation.save_last_settings'),patch('transcription_backend.run_local',return_value={'translation':'Tradução original preservada'}),patch('semantic_review.review',side_effect=RuntimeError('Parecer inválido')):
   self.app.start('translate');self.wait_done()
  record=self.app.results[None];self.assertEqual(record['status'],'review')
  self.assertEqual(Path(record['paths']['translation']).read_text().strip(),'Tradução original preservada')
 def test_api_reviewer_settings_masks_keys_and_keeps_save_visible(self):
  with patch('semantic_review.load_key',return_value='test-private-key'):
   self.app.configure_review_apis();self.root.update()
  window=next(child for child in self.parent.winfo_children() if isinstance(child,tk.Toplevel))
  widgets=[]
  def visit(parent):
   for child in parent.winfo_children():widgets.append(child);visit(child)
  visit(window)
  entries=[widget for widget in widgets if isinstance(widget,tk.ttk.Entry)]
  masked=[widget for widget in entries if widget.get()=='test-private-key']
  self.assertEqual(len(masked),3);self.assertTrue(all(widget.cget('show') for widget in masked))
  save=next(widget for widget in widgets if isinstance(widget,tk.Button) and widget.cget('text')=='SALVAR E ATIVAR')
  self.assertTrue(save.winfo_ismapped());self.assertLessEqual(save.winfo_rooty()+save.winfo_height(),window.winfo_rooty()+window.winfo_height());window.destroy()
 def test_saving_edit_invalidates_semantic_verdict_in_memory_and_metadata(self):
  import json
  audio=self.base/'line.wav';audio.write_bytes(b'audio');self.app.add_paths([audio])
  translated=self.base/'translated.txt';translated.write_text('Texto anterior');metadata=self.base/'report.json'
  record={'transcript':'Original','translation':'Texto anterior','paths':{'translation':str(translated)},'status':'ok','metadata_path':str(metadata),'semantic_review':{'evaluated':True,'needs_review':False,'issues':[]}}
  metadata.write_text(json.dumps(record),encoding='utf-8');self.app.results[audio]=record
  self.app.list.selection_set(0);self.app.selected();self.app.texts['translation'].delete('1.0','end');self.app.texts['translation'].insert('1.0','Texto editado')
  self.app.save_current('translation')
  self.assertEqual(translated.read_text().strip(),'Texto editado');self.assertEqual(record['status'],'review');self.assertNotIn('semantic_review',record)
  saved=json.loads(metadata.read_text());self.assertEqual(saved['status'],'review');self.assertNotIn('semantic_review',saved)
