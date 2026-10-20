"""Optional CPU-only Silero preflight, one detector per batch, never edits input."""
from __future__ import annotations
import functools
import json
import queue
import subprocess
import threading
import time

WORKER_CODE = r'''
import sys,json,torch,numpy as np,soundfile as sf
from silero_vad import load_silero_vad,get_speech_timestamps
torch.set_num_threads(1)
model=load_silero_vad()
for line in sys.stdin:
 try:
  request=json.loads(line)
  if request.get('close'): break
  audio,rate=sf.read(request['path'],dtype='float32',always_2d=True)
  # Select the strongest channel; opposite-phase stereo must not erase speech.
  pcm=audio[:,np.argmax(np.mean(audio**2,axis=0))]
  if not pcm.size or not np.isfinite(pcm).all(): raise ValueError('Áudio inválido para detecção')
  length=max(1,round(len(pcm)*16000/rate))
  pcm=np.interp(np.linspace(0,len(pcm)-1,length),np.arange(len(pcm)),pcm).astype(np.float32)
  peak=float(np.max(np.abs(pcm)))
  if 0<peak<.5: pcm=pcm*(.5/peak)
  with torch.inference_mode():
   regions=get_speech_timestamps(torch.from_numpy(pcm),model,sampling_rate=16000,
       threshold=.2,min_speech_duration_ms=80,min_silence_duration_ms=100,speech_pad_ms=40)
  answer={'speech':bool(regions),'seconds':len(pcm)/16000}
 except Exception as error: answer={'error':str(error)}
 print('DUBLASKIZON_PRESENCE '+json.dumps(answer),flush=True)
'''

class SpeechDetector:
    def __init__(self):
        self.process=None
        self.responses=queue.Queue()

    def detect(self, path, cancelled=lambda:False):
        if self.process is None:
            from dependency_setup import managed_python
            from batch_tab import hidden_process_kwargs
            python=managed_python()
            if not python: raise RuntimeError('Prepare Silero VAD pelo botão 1 de Requisitos.')
            self.process=subprocess.Popen([str(python),'-u','-c',WORKER_CODE],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',errors='replace',
                **hidden_process_kwargs())
            process=self.process
            def read():
                for line in process.stdout:
                    if line.startswith('DUBLASKIZON_PRESENCE '):
                        self.responses.put(line.split(' ',1)[1])
                self.responses.put(None)
            threading.Thread(target=read,daemon=True).start()
        self.process.stdin.write(json.dumps({'path':str(path)})+'\n')
        self.process.stdin.flush()
        deadline=time.monotonic()+30
        while True:
            if cancelled(): raise RuntimeError('Detecção cancelada')
            if time.monotonic()>deadline: raise RuntimeError('Detecção de fala excedeu 30 segundos')
            try: result=self.responses.get(timeout=.1)
            except queue.Empty: continue
            if result is None: raise RuntimeError('Silero indisponível; prepare pelo botão 1 de Requisitos.')
            answer=json.loads(result)
            if 'error' in answer: raise RuntimeError(answer['error'])
            return bool(answer['speech'])

    def close(self):
        if self.process is None:return
        process,self.process=self.process,None
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
        if process.stdin:process.stdin.close()
        # Reader owns stdout while the subprocess is alive.
        if process.stdout:process.stdout.close()

def speech_preflight_batch(function):
    @functools.wraps(function)
    def run(self,*args,**kwargs):
        detector=SpeechDetector()
        self._speech_detector=detector
        try:return function(self,*args,**kwargs)
        finally:
            detector.close()
            self._speech_detector=None
    return run
