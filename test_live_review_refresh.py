import ast
import queue
import threading
import time
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import batch_tab
import review_tab

tree = ast.parse(Path(__file__).with_name('Dublaskizon.py').read_text(encoding='utf-8-sig'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DublaskizonApp')
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('refresh_review', 'refresh_screen')]
scope = dict(queue=queue, threading=threading, batch_tab=batch_tab, review_tab=review_tab)
exec(compile(ast.Module(body=methods, type_ignores=[]), '<refresh>', 'exec'), scope)

class LiveRefresh(unittest.TestCase):
    def test_active_jobs_refresh_without_rebuilding(self):
        for name, flag in [('batch_app','running'), ('personalized_app','busy'), ('review_app','busy')]:
            app = SimpleNamespace(refresh_review=Mock(), rebuild_views=Mock())
            setattr(app, name, SimpleNamespace(**{flag: True}))
            scope['refresh_screen'](app)
            app.refresh_review.assert_called_once()
            app.rebuild_views.assert_not_called()

    def test_normal_and_custom_new_scenes_preserve_current_editor(self):
        for mode in ('normal', 'custom'):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for folder in ('WAV ORIGINAIS','TXT TEXTO PORTUGUES','dublados personalizados'):
                    (root/folder).mkdir()
                for stem in ('old','new'):
                    (root/'WAV ORIGINAIS'/f'{stem}.wav').write_bytes(b'RIFF')
                    (root/'TXT TEXTO PORTUGUES'/f'{stem}.txt').write_text('texto')
                    (root/'dublados personalizados'/f'{stem}.wav').write_bytes(b'RIFF')
                jobs = []
                r = SimpleNamespace(other_translation_dir=root/'OUTRAS TRADUÇÕES',
                    original_text_dir=root/'TXT TEXTO ORIGINAL', status_var=SimpleNamespace(set=Mock()),
                    current_stem=lambda:'old', audio_source_mode=mode, busy=False,
                    select_scene=Mock(), refresh_original_folder_buttons=Mock(),
                    refresh_other_translation_folder_buttons=Mock(), editor_text='unsaved edit')
                def refresh(preserve_stem):
                    self.assertEqual(preserve_stem, 'old')
                    r.stems = r.default_stems
                r.refresh_scene_list=refresh
                app = SimpleNamespace(review_app=r, project_root=root,
                    root=SimpleNamespace(after=lambda ms, callback:jobs.append(callback)))
                entered, release = threading.Event(), threading.Event()
                scan = batch_tab.find_audio_by_stem
                def slow_scan(path):
                    entered.set()
                    release.wait(3)
                    return scan(path)
                with patch.object(review_tab,'AUDIO_DIR',root/'WAV ORIGINAIS'), patch.object(review_tab,'TEXT_DIR',root/'TXT TEXTO PORTUGUES'), patch.object(batch_tab,'find_audio_by_stem',slow_scan):
                    scope['refresh_review'](app)
                    self.assertTrue(entered.wait(1))
                    scope['refresh_review'](app)
                    self.assertEqual(len(jobs), 1)
                    release.set()
                    deadline = time.monotonic()+5
                    while jobs:
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(.01)
                        jobs.pop(0)()
                self.assertEqual(r.stems, ['new','old'])
                self.assertEqual(r.editor_text, 'unsaved edit')
                r.select_scene.assert_not_called()
                self.assertFalse(app._review_refresh_running)

if __name__ == '__main__':
    unittest.main()
