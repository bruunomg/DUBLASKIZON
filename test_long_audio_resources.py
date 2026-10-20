import sys,tempfile,unittest,wave,time,tracemalloc
from pathlib import Path
from audio_player import AudioPlayerManager

class LongWaveTests(unittest.TestCase):
 def test_three_minute_stereo_peaks_are_bounded(self):
  raw=b'\x00\x20\x00\xe0'*(48000*180)
  tracemalloc.start()
  data=AudioPlayerManager._waveform_from_pcm(raw,2,2,48000,5600)
  _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
  self.assertEqual(data['duration'],180)
  self.assertLessEqual(len(data['samples']),5600)
  self.assertLess(peak,4*1024**2)
  self.assertAlmostEqual(max(data['samples']),.25)
 def test_streaming_wav_preserves_three_minute_duration(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'long.wav'
   with wave.open(str(path),'wb') as out:
    out.setparams((1,2,16000,0,'NONE','not compressed'))
    for _ in range(180):out.writeframesraw(b'\x00\x10'*16000)
   data=AudioPlayerManager._read_waveform(path,700)
   self.assertEqual(data['duration'],180)
   self.assertLessEqual(len(data['samples']),700)
   self.assertAlmostEqual(max(data['samples']),.125)

if __name__=='__main__':unittest.main()
