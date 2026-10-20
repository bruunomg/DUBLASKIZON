import tempfile
from pathlib import Path
import tkinter as tk
import unittest
from unittest.mock import Mock
import review_tab
from test_audacity_openvino import wav

class DrawerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name)
        previous=review_tab.ROOT
        self.addCleanup(lambda:review_tab.configure_project_root(previous))
        review_tab.configure_project_root(self.project)
        audio={};texts={}
        for key in ('chapter/first','chapter/second'):
            path=self.project/'WAV ORIGINAIS'/f'{key}.wav';wav(path);audio[key]=path
            txt=self.project/'TXT TEXTO PORTUGUES'/f'{key}.txt';txt.parent.mkdir(parents=True,exist_ok=True);txt.write_text('Teste.',encoding='utf-8');texts[key]=txt
            wav(self.project/'dublado'/f'{key}.wav')
        wav(self.project/'dublados personalizados/chapter/first.wav')
        self.root=tk.Tk();self.root.withdraw();self.addCleanup(self.root.destroy)
        self.controller=review_tab.ReviewApp(self.root,embedded=True,prompt_missing_text=False,scene_index=(audio,texts))
        self.player=self.controller.audio_player;self.addCleanup(self.player.close_window)
        self.controller.play_selected_scene();self.root.update()
        self.drawer=self.player.review_drawer

    def test_expansion_selection_and_source_share_real_review_state(self):
        self.assertIsNotNone(self.drawer)
        self.assertFalse(self.drawer.expanded)
        self.drawer.toggle();self.root.update()
        self.assertTrue(self.drawer.panel.winfo_ismapped())
        self.assertEqual(self.drawer.list.size(),2)
        self.assertIn(self.drawer.list.itemcget(1,'foreground'),('',self.drawer.list.cget('fg')))
        self.drawer.list.selection_clear(0,'end');self.drawer.list.selection_set(1);self.drawer.list.activate(1)
        self.drawer.select();self.root.update()
        self.assertEqual(self.player.current_context_key,'chapter/second')
        self.assertEqual(self.controller.current_stem(),'chapter/second')
        self.controller.audio_source_var.set('Dublados personalizados');self.drawer.change_source();self.root.update()
        self.assertEqual(self.controller.audio_source_mode,'custom')
        self.assertEqual(self.drawer.list.size(),1)
        self.assertEqual(self.player._current_audio_path('dubbed'),(self.project/'dublados personalizados/chapter/first.wav').resolve())
        self.assertEqual(self.player._current_audio_path('original'),(self.project/'WAV ORIGINAIS/chapter/first.wav').resolve())
        self.drawer.toggle();self.root.update()
        self.assertFalse(self.drawer.panel.winfo_ismapped())
        self.assertTrue(self.drawer.edge.winfo_ismapped())

    def test_bulk_actions_use_existing_controller(self):
        self.drawer.toggle();self.root.update()
        self.controller.finish_all_audio=Mock()
        for child in self.drawer.panel.winfo_children():
            if child.winfo_class()=='TButton' and child.cget('text')=='VOLUME MÁXIMO SEGURO — TODOS':child.invoke()
        self.controller.finish_all_audio.assert_called_once_with(max_volume=True)
        job=self.drawer.job;self.assertIsNotNone(job)
        self.player.close_window();self.assertIsNone(self.drawer.job)

    def test_tree_multiple_selection_context_and_horizontal_scroll(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        d=self.drawer;d.toggle();self.root.update();d.set_mode(True);self.root.update()
        self.assertEqual(len(d.tree_indices),2)
        self.assertEqual(d.tree.item(d.tree.parent('a0'),'text'),'chapter')
        d.tree.selection_set(('a0','a1'));d.tree.focus('a1');d.select();self.root.update()
        self.assertEqual(d.selected_indices(),[0,1])
        self.assertEqual(tuple(self.controller.scene_list.curselection()),(0,1))
        self.controller.show_scene_context_menu=Mock(return_value='break')
        box=d.tree.bbox('a1')
        d.context_menu(SimpleNamespace(y=box[1]+2,x_root=10,y_root=10))
        self.controller.show_scene_context_menu.assert_called_once()
        self.assertEqual(self.controller.show_scene_context_menu.call_args.kwargs['stem'],'chapter/second')
        d.scroll_horizontal('moveto',1);self.assertGreater(d.tree.xview()[0],0)
        d.set_mode(False);self.root.update();self.assertEqual(d.selected_indices(),[0,1])
        box=d.list.bbox(0);d.context_menu(SimpleNamespace(y=box[1]+2,x_root=10,y_root=10))
        self.assertEqual(self.controller.show_scene_context_menu.call_args.kwargs['stem'],'chapter/first')
    def test_drawer_divider_resizes_without_hiding_tools(self):
        d=self.drawer;d.toggle();self.root.update();before=d.panel.winfo_width()
        x,y=d.panes.sash_coord(0);d.panes.sash_place(0,x+90,y);self.root.update()
        self.assertGreater(d.panel.winfo_width(),before+50)
        self.assertTrue(d.main.winfo_ismapped())
        width=d.panel.winfo_width();d.toggle();d.toggle();self.root.update()
        self.assertAlmostEqual(d.panel.winfo_width(),width,delta=3)
