import json
from pathlib import Path
import queue
import tempfile
import threading
import unittest
import wave
from unittest.mock import patch

import native_emotions
from text_to_speech_tab import TextToSpeechApp


def wav(path):
    with wave.open(str(path),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(24000)
        output.writeframes(b'\0' * 24000)


class NativeEmotionTests(unittest.TestCase):
    def test_conversion_exports_pcm_and_keeps_duration_unmodified(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('native_emotions.runtime',return_value=(root/'python.exe',{'code':'seed'})),patch('native_emotions.prepared',return_value=True),patch('native_emotions.native_root',return_value=root):
                args=native_emotions.conversion_command(root/'donor.wav',root/'target.wav',root/'out')
            compile(args[args.index('-c')+1],'<native-wrapper>','exec')
            self.assertIn("subtype='PCM_24'",args[args.index('-c')+1])
            self.assertEqual(args[args.index('--length-adjust')+1],'1.0')
            self.assertEqual(args[args.index('--f0-condition')+1],'False')

    @patch('qwen_backend.emotional_references',return_value={})
    def test_shipped_references_have_valid_checksums_and_emotion_labels(self,_extra):
        for voice in ('masculina','feminina'):
            refs=native_emotions.native_references(voice)
            self.assertTrue({'neutro','alegre','triste','raiva','sussurro','surpreso'} <= refs.keys())
            for path in refs.values():
                with wave.open(str(path),'rb') as audio:
                    self.assertGreater(audio.getnframes(),0)
        manifest=json.loads((native_emotions.resource_folder()/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['voices']['masculina']['alegre']['language'],'pt-BR')
        self.assertEqual(manifest['voices']['masculina']['sussurro']['language'],'de')
        self.assertFalse('grito' in native_emotions.native_references())

    def test_converted_reference_is_cached_per_target_audio_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);donor=root/'donor.wav';target=root/'target.wav'
            wav(donor);wav(target);calls=[]
            def command(source,reference,destination):return [str(destination)]
            def run(args):calls.append(args);wav(Path(args[0])/'converted.wav')
            with patch('native_emotions.native_root',return_value=root/'runtime'),patch('native_emotions.native_references',return_value={'alegre':donor}),patch('native_emotions.conversion_command',side_effect=command):
                first=native_emotions.converted_reference('alegre',target,run)
                self.assertEqual(first,native_emotions.converted_reference('alegre',target,run))
                self.assertEqual(len(calls),1)
                target.write_bytes(target.read_bytes()+b'changed')
                self.assertNotEqual(first,native_emotions.converted_reference('alegre',target,run))
                self.assertEqual(len(calls),2)
                self.assertFalse(list(root.rglob('convert_*')))

    def test_failed_conversion_does_not_create_cache_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);donor=root/'donor.wav';target=root/'target.wav';wav(donor);wav(target)
            def fail(args):raise RuntimeError('Falha simulada')
            with patch('native_emotions.native_root',return_value=root/'runtime'),patch('native_emotions.native_references',return_value={'alegre':donor}),patch('native_emotions.conversion_command',return_value=['motor']):
                with self.assertRaises(RuntimeError):native_emotions.converted_reference('alegre',target,fail)
                self.assertFalse(list(root.rglob('reference.wav')))
                self.assertFalse(list(root.rglob('convert_*')))

    def test_runtime_cannot_escape_managed_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);outside=root/'outside.exe';outside.write_bytes(b'python')
            managed=root/'managed';managed.mkdir()
            (managed/'active.json').write_text(json.dumps({'python':'../outside.exe','version':native_emotions.VERSION}),encoding='utf-8')
            with patch('native_emotions.native_root',return_value=managed):
                self.assertIsNone(native_emotions.runtime()[0])

    def test_worker_adapts_automatic_emotion_to_selected_voice(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);neutral=root/'selected.wav';adapted=root/'adapted.wav';donor=root/'donor.wav'
            for path in (neutral,adapted,donor):wav(path)
            app=TextToSpeechApp.__new__(TextToSpeechApp);app.events=queue.Queue();app.cancel_event=threading.Event();app.pending_metadata={'text':'[alegre] Olá'}
            calls=[]
            def run(args):calls.append(args);wav(Path(args[args.index('--output')+1]))
            app._run_emotional_command=run
            with patch('batch_tab.find_ffmpeg_directory',return_value=None),patch('native_emotions.native_references',return_value={'neutro':donor,'alegre':donor}),patch('native_emotions.prepared',return_value=True),patch('native_emotions.converted_reference',return_value=adapted) as convert:
                app._emotional_worker('[alegre] Olá',neutral,'',{},['motor'],'modelo',root/'out.wav',True)
            convert.assert_called_once_with('alegre',neutral,run,voice='masculina')
            self.assertEqual(calls[0][calls[0].index('--ref_audio')+1],str(adapted))
            self.assertEqual(list(app.events.queue)[-1][0],'done')

    def test_builtin_voice_uses_own_emotions_without_converter(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);neutral=root/'selected.wav';happy=root/'happy.wav';wav(neutral);wav(happy)
            app=TextToSpeechApp.__new__(TextToSpeechApp);app.events=queue.Queue();app.cancel_event=threading.Event();app.pending_metadata={'text':'[alegre] Olá'}
            def run(args):wav(Path(args[args.index('--output')+1]))
            app._run_emotional_command=run
            with patch('batch_tab.find_ffmpeg_directory',return_value=None),patch('native_emotions.native_references',return_value={'neutro':neutral,'alegre':happy}),patch('native_emotions.prepared',return_value=False),patch('native_emotions.converted_reference') as convert:
                app._emotional_worker('[alegre] Olá',neutral,'',{},['motor'],'modelo',root/'out.wav',True)
            convert.assert_not_called()
            self.assertEqual(list(app.events.queue)[-1][0],'done')


if __name__=='__main__':unittest.main()
