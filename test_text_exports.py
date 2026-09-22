import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import audio_translation as translation
import review_tab as review


class TextExports(unittest.TestCase):
    def test_profiles_preserve_edits_and_scene_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = dict(transcript='Hello', translation='Olá')
            first = translation.export_generated_texts(root, 'chapter/scene', {}, data)
            original = root/'TXT TEXTO ORIGINAL/chapter/scene.txt'
            self.assertEqual(original.read_text(encoding='utf-8').strip(), 'Hello')
            first.write_text('Edição manual', encoding='utf-8')
            original.write_text('Original manual', encoding='utf-8')
            second = translation.export_generated_texts(root, 'chapter/scene', {}, data)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(encoding='utf-8'), 'Edição manual')
            self.assertEqual(original.read_text(encoding='utf-8'), 'Original manual')
            third = translation.export_generated_texts(root, 'chapter/scene', {'engine':'openai-whisper'}, data)
            fourth = translation.export_generated_texts(root, 'chapter/scene', {'translator':'qwen-game-local'}, data)
            self.assertEqual(len({p.parent.parent for p in (first, second, third, fourth)}), 4)
            with self.assertRaises(ValueError):
                translation.export_generated_texts(root, '../escape', {}, data)

    def test_selected_original_is_indexed_and_saved_in_selected_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/'faster-whisper_small_auto'
            target = folder/'chapter/scene.txt'
            target.parent.mkdir(parents=True)
            target.write_text('Hello', encoding='utf-8')
            app = SimpleNamespace(original_unlocked=True, original_text_dir=folder,
                current_stem=lambda:'chapter/scene', original_text_by_stem={},
                original_text_box=SimpleNamespace(get=lambda *args:'Edited'),
                set_reference_edit_state=lambda *args:None,
                status_var=SimpleNamespace(set=lambda *args:None), _log_central=lambda *args:None)
            with patch.object(review, 'ORIGINAL_TEXT_DIR', root):
                self.assertEqual(review.original_text_files(folder)['chapter/scene'], target)
                self.assertTrue(review.ReviewApp.save_original_text(app))
                self.assertFalse((root/'chapter/scene.txt').exists())
                self.assertEqual(target.read_text(encoding='utf-8').strip(), 'Edited')


if __name__ == '__main__':
    unittest.main()
