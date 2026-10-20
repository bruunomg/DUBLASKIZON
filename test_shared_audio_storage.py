import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from shared_audio_tools import storage_dir,prepare_storage,find_tool
from duration_converter_tab import executable_path
from audio_player import find_ffplay
import batch_tab
class SharedStorageTests(unittest.TestCase):
 def test_reuse_across_project_and_app_folders_with_dll(self):
  with tempfile.TemporaryDirectory() as temp:
   base=Path(temp);app=base/'app1';old=base/'project1';new=base/'project2';tools=old/'ferramentas_audio';tools.mkdir(parents=True)
   for name in ('ffmpeg.exe','ffprobe.exe','ffplay.exe','sox.exe','libsox.dll'):(tools/name).write_bytes(name.encode())
   with patch.dict(os.environ,{'LOCALAPPDATA':str(base/'system'),'DUBLASKIZON_APP_DIR':str(app)}),patch('shutil.which',return_value=None):
    target=prepare_storage(old)
    self.assertEqual(target,storage_dir());self.assertTrue((target/'libsox.dll').is_file())
    with patch.dict(os.environ,{'DUBLASKIZON_APP_DIR':str(base/'app2')}),patch.object(batch_tab,'ROOT',new):
     for name in ('ffmpeg','ffprobe','ffplay','sox'):self.assertEqual(Path(executable_path(name,new)).parent,target)
     self.assertEqual(Path(find_ffplay(new)).parent,target)
     self.assertEqual(batch_tab.find_ffmpeg_directory(),target)
    self.assertTrue((tools/'sox.exe').exists())
    (tools/'ffmpeg.exe').write_bytes(b'local')
    prepare_storage(old);self.assertEqual((target/'ffmpeg.exe').read_bytes(),b'ffmpeg.exe')
    self.assertEqual(Path(find_tool('ffmpeg',old)),tools/'ffmpeg.exe')
 def test_inventory_shared_tools(self):
  from component_uninstall import catalog
  with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'LOCALAPPDATA':temp}):
   storage_dir().mkdir(parents=True);(storage_dir()/'sox.exe').write_bytes(b'test')
   items=catalog(include_ollama=False,include_system=False)
   self.assertTrue(any(storage_dir() in item['paths'] for item in items))
if __name__=='__main__':unittest.main()
