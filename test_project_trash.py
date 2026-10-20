import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import project_trash as trash
class TrashTests(unittest.TestCase):
 def test_hierarchy_and_scene_isolation(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   for name in ('WAV ORIGINAIS','dublado','TXT TEXTO PORTUGUES'):
    extension='.txt' if name.startswith('TXT') else '.wav'
    file=root/name/'A'/('123'+extension);file.parent.mkdir(parents=True);file.write_bytes(b'scene')
    (file.parent/('1234'+extension)).write_bytes(b'other')
   files=trash.move_scene(root,'A/123')
   self.assertEqual(len(files),3)
   self.assertTrue((root/'lixeira do projeto/WAV ORIGINAIS/A/123.wav').is_file())
   self.assertTrue((root/'WAV ORIGINAIS/A/1234.wav').is_file())
 def test_failure_rolls_back(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   for name in ('WAV ORIGINAIS','dublado'):
    file=root/name/'123.wav';file.parent.mkdir();file.write_bytes(b'scene')
   original=trash.os.replace;count=[0]
   def replace(a,b):
    count[0]+=1
    if count[0]==2:raise PermissionError('locked')
    return original(a,b)
   with patch.object(trash.os,'replace',side_effect=replace),self.assertRaises(RuntimeError):trash.move_scene(root,'123')
   self.assertTrue((root/'WAV ORIGINAIS/123.wav').is_file())
   self.assertTrue((root/'dublado/123.wav').is_file())
 def test_repeated_move_does_not_overwrite(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);file=root/'dublado/123.wav';file.parent.mkdir();file.write_bytes(b'old')
   first=trash.move_scene(root,'123')[0];file.write_bytes(b'new');second=trash.move_scene(root,'123')[0]
   self.assertNotEqual(first,second);self.assertEqual(first.read_bytes(),b'old');self.assertEqual(second.read_bytes(),b'new')
 def test_unsafe_key_rejected(self):
  with tempfile.TemporaryDirectory() as folder,self.assertRaises(ValueError):trash.scene_files(folder,'../secret')
if __name__=='__main__':unittest.main()
