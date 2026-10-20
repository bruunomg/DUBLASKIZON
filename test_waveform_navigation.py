import unittest
from types import SimpleNamespace
from test_scene_review_drawer import DrawerTests
from test_audacity_openvino import wav,ov
from waveform_navigation import wheel

class Navigation(unittest.TestCase):
    setUp=DrawerTests.setUp
    def prepare(self):
        original=self.player._current_audio_path('original')
        for kind in ov.KINDS:wav(ov.scene_directory(self.project,original)/(kind+'.wav'))
        self.player._refresh_waveforms();self.root.update()
    def test_copy_each_treated_track_preserves_sources(self):
        self.prepare();p=self.player;p._toggle_audio_edit();self.root.update()
        for kind in ov.KINDS:
            path=p._current_audio_path(kind);before=path.read_bytes()
            canvas=p.waveform_canvases[kind];width=canvas.winfo_width()
            p._on_waveform_press(kind,SimpleNamespace(x=10,state=0))
            p._on_waveform_release(kind,SimpleNamespace(x=width//2,state=0))
            p._update_audio_edit_buttons()
            self.assertEqual(str(p.audio_copy_button.cget('state')),'normal')
            p._copy_audio_selection()
            self.assertEqual(p.audio_clip_buffer['source_kind'],kind)
            selected=p._edit_selection_frames(kind);track,a,b,framebytes=selected
            self.assertEqual(p.audio_clip_buffer['frames'],track['frames'][a*framebytes:b*framebytes])
            self.assertTrue(p.audio_clip_buffer['frames'])
            self.assertEqual(path.read_bytes(),before)
    def test_ruler_common_position_zoom_scroll_and_scene_change(self):
        self.prepare();p=self.player;nav=p.waveform_navigation
        p._toggle_audio_edit();self.root.update()
        nav.select(SimpleNamespace(x=nav.canvas.winfo_width()//2))
        seconds=nav.seconds;self.assertGreater(seconds,0)
        for kind,canvas in p.waveform_canvases.items():
            marks=canvas.find_withtag('scene_cursor');self.assertTrue(marks,kind)
            x=canvas.coords(marks[0])[0]
            expected=2+seconds/nav.extent()*(max(180,canvas.winfo_width())-4)*p.waveform_zoom
            self.assertAlmostEqual(x,expected,places=3)
        self.assertEqual(p.waveform_selection_ranges['dubbed'],(seconds,seconds))
        p._set_waveform_zoom(4);p._scroll_audio_views('moveto',.25)
        self.assertAlmostEqual(nav.seconds,seconds)
        self.assertAlmostEqual(nav.canvas.xview()[0],p.waveform_canvases['original'].xview()[0],places=2)
        p.audio_edit_dirty=False;p._toggle_audio_edit();p.navigate(1);self.root.update()
        self.assertIsNone(nav.seconds)
    def test_wheel_and_compact_progress(self):
        self.prepare();p=self.player;view=p.waveform_vertical_view
        self.root.update();view.configure(height=100);view.configure(scrollregion=view.bbox('all'));view.yview_moveto(0)
        before=view.yview()[0]
        self.assertEqual(wheel(p,SimpleNamespace(delta=-120,state=0)),'break')
        self.assertGreater(view.yview()[0],before)
        p._set_waveform_zoom(4);p._scroll_audio_views('moveto',0)
        wheel(p,SimpleNamespace(delta=-120,state=1))
        self.assertGreater(p.waveform_scroll,0)
        row=p.audacity_ui.progress_row
        self.assertIs(row.master,p.review_progress_frame)
        self.assertGreaterEqual(row.winfo_y(),p.review_dub_bar.master.winfo_y()+p.review_dub_bar.master.winfo_height())
        self.assertLessEqual(row.winfo_y()+row.winfo_height(),p.review_progress_frame.winfo_height())

    def test_vertical_lock_when_content_fits_and_unlock_when_it_does_not(self):
        import tkinter as tk
        from waveform_navigation import scroll_vertical
        view=tk.Canvas(self.root,height=180,width=200,highlightthickness=0)
        # Use a temporary canvas to exercise actual Tk scroll geometry independently of auto-fit.
        popup=tk.Toplevel(self.root);view.destroy()
        view=tk.Canvas(popup,height=180,width=200,highlightthickness=0);view.pack()
        content=view.create_rectangle(0,0,180,100)
        original=self.player.waveform_vertical_view;self.player.waveform_vertical_view=view
        try:
            self.root.update();view.configure(scrollregion=view.bbox('all'))
            for delta in (-120,120,-120):wheel(self.player,SimpleNamespace(delta=delta,state=0))
            self.assertEqual(view.yview()[0],0)
            view.coords(content,0,0,180,600);view.configure(scrollregion=view.bbox('all'))
            wheel(self.player,SimpleNamespace(delta=-120,state=0));self.assertGreater(view.yview()[0],0)
            view.coords(content,0,0,180,100);view.configure(scrollregion=view.bbox('all'));scroll_vertical(self.player)
            self.assertEqual(view.yview()[0],0)
        finally:self.player.waveform_vertical_view=original;popup.destroy()
    def test_audacity_bar_expands_with_available_width(self):
        import tkinter as tk
        popup=tk.Toplevel(self.root);popup.geometry('600x80')
        self.player.audacity_ui.attach_progress(popup);self.root.update()
        bar=self.player.audacity_ui.progress_bar
        small=bar.winfo_width()
        popup.geometry('900x80');self.root.update()
        self.assertGreater(bar.winfo_width(),small+250)
        popup.geometry('600x80');self.root.update()
        self.assertAlmostEqual(bar.winfo_width(),small,delta=2)
        popup.destroy()


    def test_hidden_tracks_remove_their_entire_scroll_height(self):
        self.prepare();p=self.player;ui=p.audacity_ui
        self.root.update();shown=p.waveform_panel.winfo_reqheight()
        ui.all_visible.set(False);ui.reflow();self.root.update()
        self.assertEqual(ui.container.winfo_manager(),'')
        hidden=p.waveform_panel.winfo_reqheight()
        self.assertLess(hidden,shown-100)
        bounds=p.waveform_vertical_view.bbox('all')
        self.assertLessEqual(bounds[3],hidden+2)
        ui.all_visible.set(True);ui.reflow();self.root.update()
        self.assertEqual(ui.container.winfo_manager(),'pack')
        self.assertGreater(p.waveform_panel.winfo_reqheight(),hidden+100)
