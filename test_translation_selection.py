import tempfile,unittest,tkinter as tk
from tkinter import ttk
from pathlib import Path
from unittest.mock import patch
import audio_translation as translation

def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)

class SelectionTests(unittest.TestCase):
    def test_webui_local_profile_resolves_to_native_large_v3(self):
        config=translation.settings({'engine':translation.WEBUI_LOCAL_PROFILE,'faster_model':'small'})
        self.assertEqual(config['engine'],'faster-whisper');self.assertEqual(config['faster_model'],'large-v3')
        self.assertEqual(config['transcription_profile'],'whisper-webui-large-v3')
        self.assertEqual(translation.settings(config),config)
    def test_api_choices_follow_key_and_single_model_is_applied(self):
        root=tk.Tk();root.withdraw();self.addCleanup(root.destroy);errors=[];key=['']
        def choose():
            window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
            try:
                widgets=list(descendants(window));combos=[w for w in widgets if isinstance(w,ttk.Combobox)]
                models=[w for w in combos if tuple(w.cget('values'))==tuple(translation.MODEL_LABELS.values())]
                self.assertEqual(len(models),1)
                engine=next(w for w in combos if translation.WEBUI_LOCAL_PROFILE in w.cget('values'))
                engine.set(translation.WEBUI_LOCAL_PROFILE)
                self.assertEqual(models[0].get(),'Whisper large-v3');self.assertEqual(str(models[0].cget('state')),'disabled')
                engine.set('faster-whisper');self.assertEqual(models[0].get(),'Whisper small')
                self.assertEqual(str(models[0].cget('state')),'readonly');models[0].set('Whisper large-v3')
                translator=next(w for w in combos if 'Argos — local' in w.cget('values'))
                self.assertNotIn(translation.TRANSLATOR_LABELS['luna-api'],translator.cget('values'))
                key[0]='test-credential'
                root.tk.call(translator.cget('postcommand'))
                self.assertIn(translation.TRANSLATOR_LABELS['luna-api'],translator.cget('values'));self.assertIn(translation.TRANSLATOR_LABELS['sol-api'],translator.cget('values'))
                translator.set(translation.TRANSLATOR_LABELS['sol-api'])
                apply=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='APLICAR')
                root.update_idletasks();self.assertLessEqual(apply.winfo_rooty()+apply.winfo_height(),window.winfo_rooty()+window.winfo_height())
                self.assertFalse(any('SELECIONAR PERFIL' in str(w.cget('text')) for w in widgets if isinstance(w,ttk.Button)))
                apply.invoke()
            except Exception as exc:errors.append(exc);window.destroy()
        with patch('transcription_backend.load_key',side_effect=lambda:key[0]),patch('audio_translation.load_last_settings',return_value=translation.settings()),patch('audio_translation.save_last_settings'):
            root.after(100,choose);result=translation.choose_settings(root)
        self.assertEqual(errors,[]);self.assertEqual(result['translator'],'sol-api');self.assertEqual(result['faster_model'],'large-v3')

    def test_api_translation_is_used_by_dubbing_without_exposing_key(self):
        for provider,expected in [('luna-api','model-luna'),('sol-api','model-sol')]:
            with self.subTest(provider=provider),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);target=root/'TXT TEXTO PORTUGUES'/'actor'/'scene.txt';calls=[]
                def translate(text,language,config,key,emit,cancelled,**kwargs):
                    calls.append(config['luna_model']);self.assertEqual(key,'private-test');return 'Texto traduzido completo.'
                with patch('transcription_backend.load_key',return_value='private-test'),patch('transcription_backend.api_settings',return_value={'luna_model':'model-luna','sol_model':'model-sol'}),patch('transcription_backend.run_local',return_value={'transcript':'Full source text.','source_language':'en'}) as transcribe,patch('transcription_backend.translate_api',side_effect=translate):
                    value=translation.generate_text('audio.wav',target,root,'actor/scene',{'translator':provider},lambda text:None)
                self.assertEqual(calls,[expected]);self.assertEqual(value[0],'Texto traduzido completo.');self.assertEqual(target.read_text().strip(),value[0]);self.assertFalse(transcribe.call_args.kwargs['manage_memory'])
                for record in root.rglob('*.json'):self.assertNotIn('private-test',record.read_text())

    def test_missing_key_stops_before_transcription(self):
        with tempfile.TemporaryDirectory() as directory,patch('transcription_backend.load_key',return_value=''),patch('transcription_backend.run_local') as transcribe:
            with self.assertRaisesRegex(RuntimeError,'Ative a chave'):translation.generate_text('audio',Path(directory)/'text.txt',directory,'scene',{'translator':'luna-api'},lambda text:None)
            transcribe.assert_not_called()
