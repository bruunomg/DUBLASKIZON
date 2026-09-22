import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from review_tab import ReviewApp

class IncrementalReview(unittest.TestCase):
    def make_review(self, source):
        r = ReviewApp.__new__(ReviewApp)
        r.stems = [f'cena{i:05}' for i in range(5000)]
        r.default_stems = list(r.stems)
        r.current_index = 2500
        r.audio_by_stem = {}; r.text_by_stem = {}; r.state = {}; r.theme = {}
        r.audio_source_mode = source
        r.scene_count_var = SimpleNamespace(set=Mock())
        r.audio_source_var = SimpleNamespace(get=lambda:source)
        r.scene_list = SimpleNamespace(yview=lambda:(.5,.6), insert=Mock(), itemconfig=Mock(), yview_moveto=Mock())
        r.scene_display_name=lambda stem:stem
        r.select_scene=Mock()
        return r

    def test_single_insert_in_5000_preserves_current_scene_and_deduplicates(self):
        for source in ('normal','custom'):
            r=self.make_review(source)
            selected=r.current_stem()
            with patch('pathlib.Path.rglob', side_effect=AssertionError('No scan')):
                r.register_completed_scene('cena00000a', 'original.wav', 'generated.txt', source)
                r.register_completed_scene('cena00000a', 'original.wav', 'generated.txt', source)
            self.assertEqual(len(r.stems),5001)
            self.assertEqual(r.current_stem(),selected)
            r.scene_list.insert.assert_called_once()
            r.select_scene.assert_not_called()
            r.scene_list.yview_moveto.assert_called_once_with(.5)

    def test_other_source_does_not_switch_or_insert(self):
        r=self.make_review('normal')
        r.register_completed_scene('new','original.wav','text.txt','custom')
        r.scene_list.insert.assert_not_called()
        self.assertEqual(r.audio_source_mode,'normal')
        self.assertIn('new',r.audio_by_stem)

if __name__=='__main__':unittest.main()
