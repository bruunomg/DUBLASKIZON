import tkinter as tk,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from Dublaskizon import ScrollableFrame,DublaskizonApp
import batch_tab

class CloneViewportTests(unittest.TestCase):
 def test_scale_25_fits_controls_without_outer_scroll(self):
  with tempfile.TemporaryDirectory() as folder:
   root=tk.Tk();root.geometry('1600x780+10+10')
   try:
    scroll=ScrollableFrame(root);scroll.fit_viewport=True;scroll.pack(fill='both',expand=True)
    base=Path(folder)
    with patch.multiple(batch_tab,ROOT=base,AUDIO_DIR=base/'WAV ORIGINAIS',TEXT_DIR=base/'TXT TEXTO PORTUGUES',OUTPUT_DIR=base/'dublado'):
     app=batch_tab.BatchApp(scroll.inner,embedded=True,skip_legacy_migration=True)
     scale=DublaskizonApp.__new__(DublaskizonApp);scale.root=root;scale.clone_frame=scroll.inner;scale.scale_percent=25
     scale._scale_font_targets={};scale._scale_padding_targets={}
     scale.capture_scale_targets();scale.apply_widget_scale();root.update();scroll.refresh_layout();root.update()
     self.assertFalse(scroll.scrollbar_visible)
     self.assertLess(app.clone_progress.canvas.winfo_rooty(),app.pause_button.winfo_rooty())
     self.assertLess(app.pause_button.winfo_rooty(),app.log_box.winfo_rooty())
     self.assertLessEqual(app.log_box.winfo_rootx()+app.log_box.winfo_width(),app.start_button.master.winfo_rootx())
     self.assertGreater(app.log_box.winfo_height(),app.clone_progress.canvas.winfo_height()*3)
     self.assertEqual(app.preserve_original_voice_check.master.master,app.start_button.master)
     self.assertGreater(app.preserve_original_voice_check.winfo_rooty(),app.start_button.winfo_rooty())
     self.assertLessEqual(scroll.inner.winfo_reqheight(),scroll.canvas.winfo_height())
     for button in (app.start_button,app.pause_button,app.cancel_button,app.play_scene_button):
      self.assertTrue(button.winfo_ismapped())
      self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),root.winfo_rooty()+root.winfo_height())
   finally:root.destroy()
  

if __name__=='__main__':unittest.main()
