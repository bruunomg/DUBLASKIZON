"""Reuse an isolated OmniVoice worker within one batch; release it afterwards.

The host uses only the standard library. Quality parameters and verification
remain in the original command, executed unchanged in the managed environment.
"""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path
import subprocess
import uuid


SERVER_CODE = r'''
import gc, hashlib, json, os, sys, traceback
import torch
from omnivoice.models.omnivoice import OmniVoice
_load = OmniVoice.from_pretrained
_generate = OmniVoice.generate
_prompt = OmniVoice.create_voice_clone_prompt
_load_asr = getattr(OmniVoice, 'load_asr_model', None)
_models = {}
_prompts = {}

def limited_vram(device):
    if not str(device).startswith('cuda'): return False
    return (os.environ.get('DUBLASKIZON_LOW_VRAM') == '1' or
            torch.cuda.get_device_properties(device).total_memory <= 7 * 1024**3)

class StagedASR:
    # Transfer weights only; the same FP16 Whisper still runs on CUDA.
    def __init__(self, owner, pipe, device):
        self.owner, self.pipe, self.device = owner, pipe, device
    def __getattr__(self, name): return getattr(self.pipe, name)
    def session(self):
        from contextlib import contextmanager
        @contextmanager
        def resident():
            self.owner.to('cpu')
            torch.cuda.empty_cache()
            try:
                self.pipe.model.to(self.device)
                self._resident=True
                yield
            finally:
                self._resident=False
                self.pipe.model.to('cpu')
                torch.cuda.empty_cache()
                self.owner.to(self.device)
        return resident()
    def __call__(self, *args, **kwargs):
        if self.__dict__.get('_resident',False):return self.pipe(*args,**kwargs)
        self.owner.to('cpu')
        torch.cuda.empty_cache()
        try:
            self.pipe.model.to(self.device)
            return self.pipe(*args, **kwargs)
        finally:
            self.pipe.model.to('cpu')
            torch.cuda.empty_cache()
            self.owner.to(self.device)

def load_asr(self, model_name=None, device=None):
    target = device or self._asr_device or self.device
    if not limited_vram(target):
        return _load_asr(self, model_name, device)
    synthesis_device = self.device
    self.to('cpu')
    torch.cuda.empty_cache()
    try:
        _load_asr(self, model_name, target)
        self._asr_pipe.model.to('cpu')
        self._asr_pipe = StagedASR(self, self._asr_pipe, synthesis_device)
        print('DESEMPENHO: GPU de pouca memória — síntese e Whisper alternados; modelos e qualidade preservados.', flush=True)
    finally:
        torch.cuda.empty_cache()
        self.to(synthesis_device)

def load(cls, *args, **kwargs):
    key = repr((args, sorted(kwargs.items())))
    if key not in _models:
        _models.clear()
        _prompts.clear()
        gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()
        _models[key] = _load(*args, **kwargs)
    else:
        print('DESEMPENHO: OmniVoice e conferência reutilizados nesta fila.', flush=True)
    return _models[key]

def prompt(self, ref_audio, ref_text=None, preprocess_prompt=True):
    key = None
    if isinstance(ref_audio, (str, os.PathLike)):
        path = os.path.abspath(ref_audio)
        stat = os.stat(path)
        key = (path, stat.st_size, stat.st_mtime_ns, ref_text, preprocess_prompt)
    elif isinstance(ref_audio, tuple) and hasattr(ref_audio[0], 'tobytes'):
        audio, rate = ref_audio
        key = (hashlib.sha256(audio.tobytes()).hexdigest(), rate, ref_text, preprocess_prompt)
    if key is not None and key in _prompts:
        print('DESEMPENHO: referência da voz reutilizada.', flush=True)
        return _prompts[key]
    result = _prompt(self, ref_audio, ref_text, preprocess_prompt)
    if key is not None:
        if len(_prompts) >= 4: _prompts.pop(next(iter(_prompts)))
        _prompts[key] = result
    return result

OmniVoice.from_pretrained = classmethod(load)
if _load_asr is not None: OmniVoice.load_asr_model = load_asr
for line in sys.stdin:
    request = json.loads(line)
    if request.get('close'): break
    rc = 0
    try:
        # Each embedded adapter must wrap the base once, never a previous wrapper.
        OmniVoice.generate = _generate
        OmniVoice.create_voice_clone_prompt = prompt
        sys.argv = ['-c', *request['args']]
        with torch.inference_mode():
            scene_namespace = {'__name__': '__main__'}
            exec(compile(request['code'], '<dublaskizon-scene>', 'exec'), scene_namespace)
            if 'OmniVoice.generate = _verified_generate' in request['code'] and not (scene_namespace.get('_DUBLASKIZON_TEXT_COMPLETE') or scene_namespace.get('_DUBLASKIZON_TEXT_AVAILABLE')):
                raise RuntimeError('A cena não confirmou o texto inteiro; saída não publicada.')
    except SystemExit as error:
        rc = error.code if isinstance(error.code, int) else 1
    except BaseException as error:
        rc = 1
        traceback.print_exc()
        if 'out of memory' in str(error).lower():
            _models.clear(); _prompts.clear(); gc.collect()
            if torch.cuda.is_available(): torch.cuda.empty_cache()
    finally:
        print('\n' + request['marker'] + str(rc), flush=True)
_models.clear(); _prompts.clear()
'''


class SceneProcess:
    """Subset of Popen used by the existing scene loops and cancel buttons."""
    def __init__(self, process, marker):
        self.process = process
        self.marker = marker
        self.returncode = None
        self.stdout = self._lines()
        self.pid = process.pid

    def _lines(self):
        for line in self.process.stdout:
            if line.startswith(self.marker):
                self.returncode = int(line[len(self.marker):].strip())
                return
            yield line
        self.returncode = self.process.wait() or 1

    def wait(self):
        if self.returncode is None:
            for _line in self.stdout:
                pass
        return self.returncode

    def poll(self):
        return self.returncode if self.returncode is not None else self.process.poll()

    def terminate(self):
        self.process.terminate()

    def kill(self):
        self.process.kill()


class WarmInference:
    def __init__(self):
        self.process = None
        self.key = None

    @staticmethod
    def eligible(command):
        if len(command) < 4 or command[2] != '-c' or '--model' not in command:
            return False
        model = command[command.index('--model') + 1]
        # Custom executables and other engines retain their original runner.
        return ('omnivoice' in model.lower() and
                'runtime' in Path(command[0]).parts and Path(command[0]).is_file())

    def start(self, command, **options):
        if not self.eligible(command):
            return subprocess.Popen(command, **options)
        key = (command[0], tuple(sorted((options.get('env') or os.environ).items())))
        if self.process is None or self.process.poll() is not None or key != self.key:
            self.close()
            worker_options = dict(options)
            worker_environment = dict(options.get('env') or os.environ)
            worker_environment.update(PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
            worker_options.update(stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, bufsize=1,
                                  encoding='utf-8', errors='replace', env=worker_environment)
            self.process = subprocess.Popen([command[0], '-u', '-c', SERVER_CODE], **worker_options)
            self.key = key
        marker = 'DUBLASKIZON_SCENE_END_' + uuid.uuid4().hex + ':'
        self.process.stdin.write(json.dumps({'args': command[4:], 'code': command[3], 'marker': marker}) + '\n')
        self.process.stdin.flush()
        return SceneProcess(self.process, marker)

    def close(self):
        process, self.process = self.process, None
        if process is None:
            return
        try:
            if process.poll() is None:
                process.stdin.write('{"close": true}\n')
                process.stdin.flush()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        except (OSError, ValueError):
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        finally:
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()


def warm_batch(function):
    """Keep ownership local to the batch; even exceptions close the worker."""
    @functools.wraps(function)
    def run(self, *args, **kwargs):
        pool = WarmInference()
        self._warm_inference = pool
        try:
            return function(self, *args, **kwargs)
        finally:
            pool.close()
            self._warm_inference = None
    return run
