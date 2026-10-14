import unittest
import tempfile
from pathlib import Path
from text_to_speech_tab import render_expression_text, output_location, generation_error, TextToSpeechApp, AVAILABLE_EXPRESSIONS, unavailable_emotions


class TextToSpeechTests(unittest.TestCase):
    def test_shared_expression_works_with_different_voices_and_import_copy_survives(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=TextToSpeechApp.__new__(TextToSpeechApp);app.project_root=root
            exported=root/'exported.wav';self._wav(exported)
            saved=app._share_emotion('alegre',exported)
            exported.unlink()
            self.assertTrue(saved.is_file())
            for mode,voice in [('original',root/'audio1.wav'),('personal',root/'model2.wav'),('system',None)]:
                self.assertEqual(app._emotional_references(mode,voice,'system voice').get('alegre'),str(saved))

    def test_use_in_shares_category_without_selecting_donor_as_voice(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            app=TextToSpeechApp.__new__(TextToSpeechApp);app.project_root=Path(folder)
            app._refresh_custom_expression_buttons=Mock();app.status=Mock();app.reference_mode=Mock()
            donor=Path(folder)/'expression.wav';self._wav(donor)
            app.share_expression('raiva',str(donor),'personal')
            app.reference_mode.set.assert_not_called()
            self.assertIn('raiva',app._emotional_references('personal',Path(folder)/'another.wav',''))
            self.assertNotIn('raiva',app._emotional_references('original',Path(folder)/'other.wav',''))

    def test_microphone_enumeration_includes_usb_and_headset_inputs(self):
        from text_to_speech_tab import MICROPHONE_CODE
        from unittest.mock import patch
        from types import SimpleNamespace
        from contextlib import redirect_stdout
        import io,json
        devices=[dict(name='FIFINE USB',max_input_channels=1,default_samplerate=48000,hostapi=0),
                 dict(name='Headset Microphone',max_input_channels=1,default_samplerate=48000,hostapi=0),
                 dict(name='Speakers',max_input_channels=0,default_samplerate=48000,hostapi=0)]
        sd=SimpleNamespace(query_devices=lambda:devices,query_hostapis=lambda:[{'name':'Windows WASAPI'}],default=SimpleNamespace(device=(0,2)))
        output=io.StringIO()
        with patch.dict('sys.modules',{'sounddevice':sd}),patch('sys.argv',['mic']),redirect_stdout(output):exec(MICROPHONE_CODE,{})
        result=json.loads(output.getvalue().split(' ',1)[1])
        self.assertEqual([d['name'] for d in result],['FIFINE USB','Headset Microphone'])
        self.assertTrue(result[0]['default'])
        self.assertEqual(result[0]['api'],'Windows WASAPI')

    def test_microphone_capture_limits_and_pcm_output(self):
        from text_to_speech_tab import MICROPHONE_CODE
        from unittest.mock import patch
        from types import SimpleNamespace
        import numpy as np, wave
        device=SimpleNamespace(query_devices=lambda *args:{'default_samplerate':1000},
                               rec=lambda frames,**kwargs:np.full((frames,1),.2,dtype=np.float32),wait=lambda:None)
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'mic.wav'
            with patch.dict('sys.modules',{'sounddevice':device}),patch('sys.argv',['mic','0','6',str(target)]):
                exec(MICROPHONE_CODE,{})
            with wave.open(str(target)) as audio:
                self.assertEqual(audio.getnframes(),6000)
                self.assertEqual(audio.getsampwidth(),2)
            with patch.dict('sys.modules',{'sounddevice':device}),patch('sys.argv',['mic','0','11',str(target)]),self.assertRaises(ValueError):
                exec(MICROPHONE_CODE,{})

    def test_every_visible_expression_has_native_preview_in_both_banks(self):
        from native_emotions import native_references
        self.assertEqual(len(AVAILABLE_EXPRESSIONS),6)
        for voice in ('masculina','feminina'):
            references=native_references(voice)
            for label,key in AVAILABLE_EXPRESSIONS:self.assertTrue(references[key].is_file(),(voice,key))

    def test_unavailable_tags_are_detected_with_current_configuration(self):
        self.assertEqual(unavailable_emotions('[grito] Socorro! [alegre] Olá',{},('alegre',)),['grito'])
        self.assertEqual(unavailable_emotions('[alegre] Olá',{}),['alegre'])
        self.assertEqual(unavailable_emotions('Olá',{}),[])

    def test_custom_references_and_supported_nonverbal_commands_remain_usable(self):
        with tempfile.TemporaryDirectory() as folder:
            reference=Path(folder)/'grito.wav';reference.write_bytes(b'reference')
            self.assertEqual(unavailable_emotions('[grito] Socorro!',{'grito':reference}),[])
            reference.unlink()
            self.assertEqual(unavailable_emotions('[grito] Socorro!',{'grito':reference}),['grito'])
        self.assertEqual(unavailable_emotions('[suspiro] Olá',{},allow_nonverbal=True),[])
        self.assertEqual(unavailable_emotions('[suspiro] Olá',{},allow_nonverbal=False),['suspiro'])

    def test_preview_does_not_insert_tags_and_uses_native_voice(self):
        from unittest.mock import Mock,patch
        app=TextToSpeechApp.__new__(TextToSpeechApp)
        app.preview_expressions=Mock();app.preview_expressions.get.return_value=True
        app.native_voice=Mock();app.native_voice.get.return_value='feminina'
        app.reference_mode=Mock();app._selection=Mock(return_value=(None,''));app._emotional_references=Mock(return_value={})
        app.status=Mock();app.text=Mock();app._open_audio=Mock()
        sample=Path('alegre.wav')
        with patch('native_emotions.native_references',return_value={'alegre':sample}) as refs,patch('audio_player.play_wav_with_winsound',return_value=True) as play:
            app.expression_action('alegre')
            refs.assert_called_once_with('feminina');play.assert_called_once_with(sample)
        app.text.insert.assert_not_called()

    def test_unavailable_preview_is_not_replaced_by_neutral(self):
        from unittest.mock import Mock,patch
        app=TextToSpeechApp.__new__(TextToSpeechApp)
        app.preview_expressions=Mock();app.preview_expressions.get.return_value=True
        app.native_voice=Mock();app.native_voice.get.return_value='masculina'
        app.reference_mode=Mock();app._selection=Mock(return_value=(None,''));app._emotional_references=Mock(return_value={})
        app.status=Mock();app.text=Mock();app._open_audio=Mock()
        with patch('native_emotions.native_references',return_value={'neutro':Path('neutro.wav')}):app.expression_action('choro')
        app.text.insert.assert_not_called();app._open_audio.assert_not_called()
        self.assertIn('Sem prévia',app.status.set.call_args.args[0])

    def test_preview_disabled_preserves_tag_insertion(self):
        from unittest.mock import Mock
        app=TextToSpeechApp.__new__(TextToSpeechApp)
        app.preview_expressions=Mock();app.preview_expressions.get.return_value=False
        app.text=Mock();app.expression_action('sussurro')
        app.text.insert.assert_called_once_with('insert','[sussurro] ')

    def test_own_expression_previews_registered_audio_and_inserts_same_tag(self):
        from unittest.mock import Mock
        app=TextToSpeechApp.__new__(TextToSpeechApp)
        app.preview_expressions=Mock();app.preview_expressions.get.return_value=True
        app.reference_mode=Mock();app.reference_mode.get.return_value='personal'
        app._selection=Mock(return_value=(Path('voice.wav'),''))
        app._emotional_references=Mock(return_value={'grito':'my_shout.wav'})
        app.status=Mock();app.text=Mock();app._open_audio=Mock()
        app.expression_action('grito')
        app._open_audio.assert_called_once_with(Path('my_shout.wav'))
        app.text.insert.assert_not_called()
        app.preview_expressions.get.return_value=False
        app.expression_action('grito')
        app.text.insert.assert_called_once_with('insert','[grito] ')

    def test_buttons_insert_new_tags_for_reference_engine(self):
        from unittest.mock import Mock
        app=TextToSpeechApp.__new__(TextToSpeechApp)
        app.engine=Mock();app.engine.get.return_value='OmniVoice / F5 — referências emocionais'
        app.text=Mock();app.insert_expression('sussurro')
        app.text.insert.assert_called_once_with('insert','[sussurro] ')

    def test_profiles_belong_to_selected_voice_and_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            app=TextToSpeechApp.__new__(TextToSpeechApp);app.project_root=Path(folder)
            first=app._profile_file('original',Path(folder)/'andre.wav','')
            second=app._profile_file('original',Path(folder)/'sally.wav','')
            self.assertNotEqual(first,second)
            self.assertNotEqual(first,app._profile_file('personal',Path(folder)/'andre.wav',''))

    def _worker_app(self,root):
        import queue, threading
        app=TextToSpeechApp.__new__(TextToSpeechApp)
        app.events=queue.Queue();app.cancel_event=threading.Event()
        app.pending_metadata={'text':'[alegre] Olá [sussurro] André','mode':'personal'}
        app.process=None
        return app

    def _wav(self,path,value=1):
        import wave
        with wave.open(str(path),'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(1000)
            audio.writeframes(bytes([value])*200)

    def test_worker_uses_selected_voice_and_emotional_reference_without_tags(self):
        import json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);neutral=root/'andre.wav';happy=root/'andre_alegre.wav'
            self._wav(neutral);self._wav(happy,2)
            adapted=root/'adapted.wav';self._wav(adapted,3)
            app=self._worker_app(root);calls=[]
            def run(args):
                ref=Path(args[args.index('--ref_audio')+1]);calls.append((args[args.index('--text')+1],ref.read_bytes()))
                self._wav(Path(args[args.index('--output')+1]))
            app._run_emotional_command=run
            output=root/'result.wav'
            with patch('batch_tab.find_ffmpeg_directory',return_value=None), patch('native_emotions.prepared',return_value=True), patch('native_emotions.converted_reference',return_value=adapted) as conversion:
                app._emotional_worker('[alegre] Olá [sussurro] André',neutral,'',{'alegre':str(happy)},['motor'],'modelo',output)
            self.assertEqual(conversion.call_count,1)
            self.assertEqual(conversion.call_args.args,('alegre',neutral,run))
            self.assertTrue(str(conversion.call_args.kwargs['donor']).endswith('.expressive.wav'))
            self.assertEqual(calls,[('Olá',happy.read_bytes()),('André',neutral.read_bytes())])
            metadata=json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
            self.assertEqual([s['used_emotion'] for s in metadata['segments']],['alegre','neutro'])
            self.assertFalse(list(root.glob('dublaskizon_*')))
            events=list(app.events.queue)
            self.assertEqual(events[-1],('done',output))
            self.assertTrue(any('sem referência para sussurro' in str(value) for kind,value in events))

    def test_system_voice_generates_one_fixed_reference_for_all_segments(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=self._worker_app(root);calls=[]
            def run(args):
                calls.append(args)
                self._wav(Path(args[args.index('--output')+1]))
            app._run_emotional_command=run
            with patch('batch_tab.find_ffmpeg_directory',return_value=None):
                app._emotional_worker('[alegre] Olá [triste] André',None,'male, young adult',{},['motor'],'modelo',root/'result.wav')
            self.assertEqual(len(calls),3)
            self.assertIn('--instruct',calls[0])
            first_ref=calls[1][calls[1].index('--ref_audio')+1]
            self.assertEqual(first_ref,calls[2][calls[2].index('--ref_audio')+1])
            self.assertEqual(list(app.events.queue)[-1][0],'done')

    def test_worker_failure_keeps_old_audio_and_reports_error(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);neutral=root/'andre.wav';self._wav(neutral)
            output=root/'result.wav';output.write_bytes(b'old')
            app=self._worker_app(root)
            def fail(args):raise RuntimeError('Erro simulado no motor')
            app._run_emotional_command=fail
            with patch('batch_tab.find_ffmpeg_directory',return_value=None):
                app._emotional_worker('[alegre] Olá',neutral,'',{},['motor'],'modelo',output)
            self.assertEqual(output.read_bytes(),b'old')
            self.assertEqual(list(app.events.queue)[-1][0],'error')
            self.assertFalse(list(root.glob('dublaskizon_*')))

    def test_results_preserve_review_warning_when_reloaded(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            audio=root/'TEXTO PARA FALA'/'VOZ MODELO TEXTO para FALA'/'voice.wav'
            audio.parent.mkdir(parents=True);audio.write_bytes(b'audio')
            audio.with_suffix('.json').write_text('{"needs_review": true}',encoding='utf-8')
            app=TextToSpeechApp.__new__(TextToSpeechApp)
            app.project_root=root;app.reference_mode=Mock();app.reference_mode.get.return_value='personal'
            app.result_tree=Mock();app.result_tree.get_children.return_value=[]
            app.refresh_results()
            self.assertEqual(app.result_tree.insert.call_args.kwargs['text'],'[CONFERIR] voice.wav')
            self.assertEqual(app.result_tree.insert.call_args.kwargs['values'],(str(audio),))
    def test_error_dialog_uses_final_diagnosis_without_progress_noise(self):
        report='FutureWarning: old API\n0%| | 0/4095\nTraceback (most recent call last):\nRuntimeError: A fala não foi confirmada.'
        result=generation_error(report,1)
        self.assertIn('A fala não foi confirmada.',result)
        self.assertNotIn('4095',result)
        self.assertIn('PROCESSOS E MENSAGENS',result)

    def test_markers_are_not_spoken_and_supported_instructions_are_deduplicated(self):
        text, instructions = render_expression_text("Olá [[EXPRESSAO:triste]] mundo [[EXPRESSAO:triste]]")
        self.assertEqual(text, "Olá mundo")
        self.assertEqual(instructions, [])

    def test_native_nonverbal_tags_stay_at_cursor_position(self):
        text,instructions=render_expression_text('Antes [[EXPRESSAO:rindo]] depois [[EXPRESSAO:suspiro]]')
        self.assertEqual(text,'Antes [laughter] depois [sigh]')
        self.assertEqual(instructions,[])

    def test_whisper_is_not_spoken_and_is_deduplicated(self):
        text,instructions=render_expression_text('[[EXPRESSAO:sussurro]] Olá [[EXPRESSAO:sussurro]]')
        self.assertEqual(text,'Olá')
        self.assertEqual(instructions,['whisper'])

    def test_hierarchy_categories_and_existing_audio_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'WAV ORIGINAIS'/'Ato 1'/'Sally'/'cena.ogg'
            result=output_location(root,'original',source)
            self.assertEqual(result,root/'TEXTO PARA FALA'/'WAV ORIGINAIS TEXTO para FALA'/'Ato 1'/'Sally'/'cena.wav')
            result.parent.mkdir(parents=True);result.write_bytes(b'previous')
            self.assertEqual(output_location(root,'original',source).name,'cena_2.wav')
            self.assertEqual(result.read_bytes(),b'previous')
            external=root/'externo'/'cena.wav'
            self.assertEqual(output_location(root,'original',external).parent.name,'ÁUDIO ORIGINAL TEXTO para FALA')
            self.assertEqual(output_location(root,'personal',external).parent.name,'VOZ MODELO TEXTO para FALA')
            self.assertEqual(output_location(root,'system',voice_name='Homem jovem').parent.name,'DO SISTEMA TEXTO para FALA')

    def test_unknown_markers_are_removed_safely(self):
        text, instructions = render_expression_text("Teste [[EXPRESSAO:inexistente]] final")
        self.assertEqual(text, "Teste final")
        self.assertEqual(instructions, [])


if __name__ == "__main__":
    unittest.main()
