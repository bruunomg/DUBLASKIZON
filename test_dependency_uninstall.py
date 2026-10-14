import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import dependency_setup as setup


class DependencyUninstallTests(unittest.TestCase):
    def test_inventory_and_removal_are_limited_to_managed_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            local, home, app, project = root/'local', root/'home', root/'app', root/'project'
            env = {'LOCALAPPDATA': str(local), 'HF_HOME': str(home/'hf')}
            with patch.dict(os.environ, env, clear=False):
                runtime = setup.runtime_root(); runtime.mkdir(parents=True)
                (runtime/'package.bin').write_bytes(b'x'*1024)
                tools = app/'ferramentas_audio'; tools.mkdir(parents=True)
                (tools/'ffmpeg.exe').write_bytes(b'y'*2048)
                cache = home/'hf'/'hub'/('models--'+setup.MODELS[0].replace('/','--'))
                cache.mkdir(parents=True); (cache/'model.safetensors').write_bytes(b'z'*4096)
                unrelated = home/'hf'/'hub'/'models--outra--ferramenta'
                unrelated.mkdir(parents=True); (unrelated/'keep.bin').write_bytes(b'keep')
                targets = setup.managed_download_targets(app, project)
                self.assertIn(runtime, targets); self.assertIn(tools, targets); self.assertIn(cache, targets)
                self.assertNotIn(unrelated, targets)
                expected = sum(setup.path_size(path) for path in targets)
                removed, failures = setup.remove_managed_downloads(targets)
                self.assertFalse(failures)
                self.assertEqual(removed, expected)
                self.assertTrue((unrelated/'keep.bin').is_file())

    def test_size_does_not_follow_symlink(self):
        if not hasattr(os, 'symlink'):
            self.skipTest('symlink unavailable')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); outside=root/'outside';outside.mkdir();(outside/'large.bin').write_bytes(b'x'*5000)
            managed=root/'managed';managed.mkdir();(managed/'small.bin').write_bytes(b'x'*10)
            link=managed/'external'
            try:link.symlink_to(outside,target_is_directory=True)
            except OSError:self.skipTest('symlink permission unavailable')
            self.assertLess(setup.path_size(managed),5000)


if __name__ == '__main__':
    unittest.main()
