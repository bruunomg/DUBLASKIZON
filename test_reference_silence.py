import unittest,types
from unittest.mock import patch
import numpy as np
from voice_reference import find_reference_start

class ReferenceSilenceTests(unittest.TestCase):
 def scan(self,audio):
  reads=[]
  class Reader:
   samplerate=1000
   def __init__(self,*args):self.offset=0
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,frames,**kwargs):
    reads.append(frames);part=audio[self.offset:self.offset+frames];self.offset+=len(part);return part
  with patch.dict('sys.modules',{'soundfile':types.SimpleNamespace(SoundFile=Reader),'torch':None}):
   result=find_reference_start('unchanged.wav')
  self.assertLessEqual(max(reads),8000)
  return result
 def test_finds_activity_after_a_minute_of_silence_without_channel_cancellation(self):
  audio=np.zeros((90000,2),dtype='float32');audio[65000:70000,0]=.05;audio[:,1]=-audio[:,0]
  before=audio.copy();start=self.scan(audio)
  self.assertGreater(start,64);self.assertLess(start,65.1)
  np.testing.assert_array_equal(audio,before)
 def test_all_silence_does_not_become_a_reference(self):
  with self.assertRaisesRegex(RuntimeError,'silencioso'):self.scan(np.zeros((30000,1),dtype='float32'))
