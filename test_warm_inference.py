import subprocess
import ast
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from warm_inference import SERVER_CODE, WarmInference, warm_batch


# Exercise the actual pipe protocol without installing a model in the test host.
FAKE_ENGINE = r'''
import sys, types
torch = types.ModuleType('torch')
class Context:
    def __enter__(self): pass
    def __exit__(self, *args): pass
torch.inference_mode = Context
torch.cuda = types.SimpleNamespace(is_available=lambda: False)
sys.modules['torch'] = torch
module = types.ModuleType('omnivoice.models.omnivoice')
class OmniVoice:
    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        print('LOAD_MODEL', flush=True)
        return cls()
    def generate(self, text): return text
    def create_voice_clone_prompt(self, *args):
        print('CREATE_PROMPT', flush=True)
        return args
module.OmniVoice = OmniVoice
sys.modules['omnivoice.models.omnivoice'] = module
'''


class WarmInferenceTests(unittest.TestCase):
    def setUp(self):
        self.pool = WarmInference()
        self.addCleanup(self.pool.close)
        self.patch = patch('warm_inference.SERVER_CODE', FAKE_ENGINE + SERVER_CODE)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.eligibility = patch.object(WarmInference, 'eligible', return_value=True)
        self.eligibility.start()
        self.addCleanup(self.eligibility.stop)

    def run_scene(self, code, args=()):
        process = self.pool.start([sys.executable, '-u', '-c', code, *args])
        lines = ''.join(process.stdout)
        return process, lines

    def test_two_scenes_reuse_model_and_preserve_arguments(self):
        code = "from omnivoice.models.omnivoice import OmniVoice; import sys; m=OmniVoice.from_pretrained('same'); print(m.generate(sys.argv[1]), flush=True)"
        first, output1 = self.run_scene(code, ['Olá!'])
        second, output2 = self.run_scene(code, ['Outra cena.'])
        self.assertEqual(first.pid, second.pid)
        self.assertEqual(output1.count('LOAD_MODEL'), 1)
        self.assertNotIn('LOAD_MODEL', output2)
        self.assertIn('Outra cena.', output2)
        self.assertEqual(second.wait(), 0)

    def test_adapters_do_not_wrap_the_previous_scene(self):
        code = "from omnivoice.models.omnivoice import OmniVoice\nbase=OmniVoice.generate\nOmniVoice.generate=lambda self,text: base(self,text)+' checked'\nprint(OmniVoice.from_pretrained('same').generate('fala'), flush=True)"
        self.run_scene(code)
        _, output = self.run_scene(code)
        self.assertIn('fala checked', output)
        self.assertNotIn('checked checked', output)

    def test_failure_is_reported_and_next_scene_can_run(self):
        failed, output = self.run_scene("raise RuntimeError('cena falhou')")
        self.assertEqual(failed.wait(), 1)
        self.assertIn('cena falhou', output)
        next_scene, output = self.run_scene("print('recuperado',flush=True)")
        self.assertEqual(next_scene.wait(), 0)
        self.assertIn('recuperado', output)

    def test_completion_proof_is_required_for_each_verified_scene(self):
        confirmed, _ = self.run_scene("# OmniVoice.generate = _verified_generate\n_DUBLASKIZON_TEXT_COMPLETE=True")
        self.assertEqual(confirmed.wait(), 0)
        unchecked, output = self.run_scene("# OmniVoice.generate = _verified_generate\nprint('sem conferência',flush=True)")
        self.assertEqual(unchecked.wait(), 1)
        self.assertIn('não confirmou o texto inteiro', output)

    def test_explicit_available_for_review_is_distinct_from_confirmed(self):
        available, _ = self.run_scene("# OmniVoice.generate = _verified_generate\n_DUBLASKIZON_TEXT_COMPLETE=False\n_DUBLASKIZON_TEXT_AVAILABLE=True")
        self.assertEqual(available.wait(), 0)

    def test_changing_model_discards_previous_model(self):
        code = "from omnivoice.models.omnivoice import OmniVoice; import sys; OmniVoice.from_pretrained(sys.argv[1])"
        self.run_scene(code, ['first'])
        _, output = self.run_scene(code, ['second'])
        self.assertEqual(output.count('LOAD_MODEL'), 1)
        _, output = self.run_scene(code, ['first'])
        self.assertEqual(output.count('LOAD_MODEL'), 1)

    def test_reference_cache_invalidates_when_file_changes(self):
        code = "from omnivoice.models.omnivoice import OmniVoice; import sys; m=OmniVoice.from_pretrained('same'); m.create_voice_clone_prompt(sys.argv[1])"
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / 'reference.wav'
            reference.write_bytes(b'original')
            _, output = self.run_scene(code, [str(reference)])
            self.assertIn('CREATE_PROMPT', output)
            _, output = self.run_scene(code, [str(reference)])
            self.assertNotIn('CREATE_PROMPT', output)
            reference.write_bytes(b'another reference')
            _, output = self.run_scene(code, [str(reference)])
            self.assertIn('CREATE_PROMPT', output)

    def test_cancel_terminates_worker_and_next_request_restarts(self):
        scene = self.pool.start([sys.executable, '-u', '-c', 'import time; time.sleep(30)'])
        previous = scene.pid
        scene.terminate()
        self.assertNotEqual(scene.wait(), 0)
        next_scene, _ = self.run_scene("print('novo',flush=True)")
        self.assertNotEqual(next_scene.pid, previous)
        self.assertEqual(next_scene.wait(), 0)

    def test_batch_closes_worker_even_when_exception_escapes(self):
        class App:
            @warm_batch
            def run(app):
                app.pool = app._warm_inference
                raise ValueError('teste')
        app = App()
        with self.assertRaises(ValueError): app.run()
        self.assertIsNone(app._warm_inference)
        self.assertIsNone(app.pool.process)

    def test_other_engines_use_existing_process(self):
        with patch.object(WarmInference, 'eligible', return_value=False), patch('warm_inference.subprocess.Popen') as original:
            command = ['other-engine', '--text', 'fala']
            self.pool.start(command, stdout=subprocess.PIPE)
            original.assert_called_once_with(command, stdout=subprocess.PIPE)


class LimitedVRAMTests(unittest.TestCase):
    def test_consecutive_checks_transfer_weights_only_once(self):
        scope=self.definitions();moves=[];calls=[]
        owner=SimpleNamespace(to=lambda device:moves.append(('synthesis',device)))
        class Pipe:
            model=SimpleNamespace(to=lambda device:moves.append(('whisper',device)))
            def __call__(self,text):calls.append(text);return text
        proxy=scope['StagedASR'](owner,Pipe(),'cuda:0')
        with proxy.session():
            for text in ('first','timestamps','final'):
                self.assertEqual(proxy(text),text)
        self.assertEqual(calls,['first','timestamps','final'])
        self.assertEqual(moves,[('synthesis','cpu'),('whisper','cuda:0'),('whisper','cpu'),('synthesis','cuda:0')])

    def test_group_failure_restores_gpu_for_next_synthesis(self):
        scope=self.definitions();moves=[]
        owner=SimpleNamespace(to=lambda device:moves.append(('synthesis',device)))
        class Pipe:
            model=SimpleNamespace(to=lambda device:moves.append(('whisper',device)))
            def __call__(self):raise RuntimeError('ASR failed')
        proxy=scope['StagedASR'](owner,Pipe(),'cuda:0')
        with self.assertRaises(RuntimeError):
            with proxy.session():proxy()
        self.assertFalse(proxy._resident)
        self.assertEqual(moves[-1],('synthesis','cuda:0'))

    def definitions(self, gib=6):
        nodes = [node for node in ast.parse(SERVER_CODE).body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and
                 node.name in ('limited_vram', 'StagedASR', 'load_asr')]
        scope = {'os': SimpleNamespace(environ={}),
                 'torch': SimpleNamespace(cuda=SimpleNamespace(
                     get_device_properties=lambda _device: SimpleNamespace(total_memory=gib * 1024**3),
                     empty_cache=lambda: None))}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<staged-asr>', 'exec'), scope)
        return scope

    def test_only_small_cuda_devices_use_staging(self):
        self.assertTrue(self.definitions(6)['limited_vram']('cuda:0'))
        self.assertFalse(self.definitions(8)['limited_vram']('cuda:0'))
        self.assertFalse(self.definitions(6)['limited_vram']('cpu'))

    def test_whisper_failure_restores_synthesis_to_gpu(self):
        scope = self.definitions()
        moves = []
        owner = SimpleNamespace(to=lambda device: moves.append(('synthesis', device)))
        class Pipe:
            model = SimpleNamespace(to=lambda device: moves.append(('whisper', device)))
            def __call__(self): raise RuntimeError('recognition failed')
        proxy = scope['StagedASR'](owner, Pipe(), 'cuda:0')
        with self.assertRaises(RuntimeError): proxy()
        self.assertEqual(moves, [('synthesis','cpu'), ('whisper','cuda:0'),
                                 ('whisper','cpu'), ('synthesis','cuda:0')])


if __name__ == '__main__':
    unittest.main()
