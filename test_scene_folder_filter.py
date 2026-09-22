import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from review_tab import scene_text_folders, ReviewApp

class SceneFolderFilter(unittest.TestCase):
    def test_only_version_roots_with_full_scene_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for relative in ('Chapter/Character/scene.txt', 'whisper/Chapter/Character/scene.txt', 'qwen/Chapter/Character/other.txt'):
                p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('text')
            self.assertEqual(scene_text_folders(root,'Chapter/Character/scene'),[root/'whisper'])
            self.assertEqual(scene_text_folders(root,'Chapter/Character/missing'),[])

    def test_generation_notifies_ui_before_synthesis_finishes(self):
        callbacks=[]
        refresh=Mock()
        app=SimpleNamespace(root=SimpleNamespace(after=lambda ms,fn:callbacks.append(fn)),project_actions={'refresh_review':refresh},_show_generated_translation=Mock())
        ReviewApp._generated_text_ready(app,'scene','Olá',Path('new.txt'))
        self.assertEqual(app.regen_translation_result,('Olá',Path('new.txt')))
        app._show_generated_translation.assert_not_called()
        callbacks[0]()
        app._show_generated_translation.assert_called_once_with('scene','Olá',Path('new.txt'))
        refresh.assert_called_once()

if __name__=='__main__':unittest.main()
