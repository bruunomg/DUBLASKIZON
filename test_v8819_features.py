import unittest,tempfile,json,threading
from pathlib import Path
from unittest.mock import patch,Mock
from test_audacity_openvino import SceneTests,wav
import voice_requirements as vr

class NewFeatures(SceneTests):
    def test_windows_opens_external_and_explicit_editor_still_opens(self):
        self.player.close_window();self.player.playback_mode='windows'
        with patch('audio_player.os.startfile') as start:
            self.player.play_one(self.original);start.assert_called_once_with(str(self.original.resolve()))
            self.assertIsNone(self.player.window)
            self.player.play_one(self.original,force_editor=True);self.root.update()
            self.assertIsNotNone(self.player.window)
    def test_new_players_inherit_global_mode_and_existing_players_follow(self):
        from audio_player import AudioPlayerManager,set_global_playback_mode
        self.root._dublaskizon_playback_mode='windows'
        child=AudioPlayerManager(self.root,self.project);self.addCleanup(child.close_window)
        self.assertEqual(child.playback_mode,'windows')
        set_global_playback_mode(self.root,'ffplay')
        self.assertEqual(child.playback_mode,'ffplay');self.assertEqual(self.player.playback_mode,'ffplay')

    def test_rename_part_preserves_audio_and_text(self):
        from scene_parts import list_parts
        part=self.project/'part_1';part.mkdir();wav(part/'parte.wav')
        (part/'texto.txt').write_text('Teste.',encoding='utf-8');(part/'info.json').write_text('{"number":1,"kind":"txt"}',encoding='utf-8')
        audio=(part/'parte.wav').read_bytes();text=(part/'texto.txt').read_bytes()
        ui=self.player.scene_parts_ui
        with patch('tkinter.simpledialog.askstring',return_value='Meu trecho'),patch.object(ui,'refresh') as refresh:
            ui.rename_part({'audio':part/'parte.wav','title':''});refresh.assert_called_once_with(force=True)
        self.assertEqual(json.loads((part/'info.json').read_text(encoding='utf-8'))['title'],'Meu trecho')
        self.assertEqual((part/'parte.wav').read_bytes(),audio);self.assertEqual((part/'texto.txt').read_bytes(),text)

class Requirements(unittest.TestCase):
    def test_model_size_uses_metadata_and_patterns(self):
        import io
        metadata=json.dumps({'siblings':[{'rfilename':'model.safetensors','size':1234},{'rfilename':'not-needed.zip','size':9999}]}).encode()
        with patch.object(vr,'repositories',return_value={'org/model':['*.safetensors']}),patch('voice_requirements.urllib.request.urlopen',return_value=io.BytesIO(metadata)):
            self.assertEqual(vr.estimate('org/model'),(1234,[]))
    def test_metadata_failure_is_unknown_not_zero_size_claim(self):
        with patch.object(vr,'repositories',return_value={'org/model':['*']}),patch('voice_requirements.urllib.request.urlopen',side_effect=OSError('offline')):
            self.assertEqual(vr.estimate('org/model'),(0,['org/model']))
    def test_requirements_selectors_do_not_change_with_wheel(self):
        import tkinter as tk
        from tkinter import ttk
        import dependency_setup as setup
        from types import SimpleNamespace
        root=tk.Tk();self.addCleanup(root.destroy)
        app=SimpleNamespace(root=root,dependency_window=None,current_theme=lambda:{'root':'#202B3B'},should_show_dependency_assistant=lambda:True,save_dependency_assistant_preference=lambda v:None,ensure_control_contrast=lambda w:None,prepare_shared_audio_tools=lambda:None)
        with patch.object(setup,'detect_processing',return_value={'variant':'cpu','cpu':'Teste','gpu':'CPU'}):setup.show_assistant(app);root.update()
        window=app.dependency_window;self.addCleanup(lambda:window.destroy() if window.winfo_exists() else None)
        combos=[];buttons={}
        def walk(w):
            for child in w.winfo_children():
                if isinstance(child,ttk.Combobox):combos.append(child)
                if isinstance(child,tk.Button):buttons[child.cget('text')]=child
                walk(child)
        walk(window)
        for combo in combos:
            before=combo.get();combo.event_generate('<MouseWheel>',delta=-120);root.update();self.assertEqual(combo.get(),before)
        for title in ('1. INSTALAR / REPARAR','2. BAIXAR MODELOS','3. PREPARAR AUDACITY','4. TESTAR MODELO'):
            self.assertEqual(buttons[title].cget('bg'),'#00FFFF')

    def test_missing_model_confirmation_includes_space_and_starts_selected_tool(self):
        import tkinter as tk
        from types import SimpleNamespace
        root=tk.Tk();root.withdraw();self.addCleanup(root.destroy)
        callback=Mock()
        batch=SimpleNamespace(root=root,running=False,selected_model_id=lambda:'org/model',append_log=Mock(),project_actions={'prepare_model':callback})
        with patch.object(vr,'missing',return_value=(True,['org/model'])),patch.object(vr,'estimate',return_value=(1024**3,[])),patch.object(vr,'free_space',return_value=100*1024**3),patch('tkinter.messagebox.askyesno',return_value=True) as ask:
            vr.prompt(batch);root.after(400,root.quit);root.mainloop()
            callback.assert_called_once_with('org/model')
            text=ask.call_args.args[1];self.assertIn('Espaço livre:',text);self.assertIn('Tamanho dos modelos:',text)
    def test_insufficient_space_prevents_install_offer(self):
        import tkinter as tk
        from types import SimpleNamespace
        root=tk.Tk();root.withdraw();self.addCleanup(root.destroy)
        callback=Mock();batch=SimpleNamespace(root=root,running=False,selected_model_id=lambda:'org/model',append_log=Mock(),project_actions={'prepare_model':callback})
        with patch.object(vr,'missing',return_value=(True,['org/model'])),patch.object(vr,'estimate',return_value=(1024**3,[])),patch.object(vr,'free_space',return_value=1),patch('tkinter.messagebox.askyesno') as ask,patch('tkinter.messagebox.showwarning') as warning:
            vr.prompt(batch);root.after(400,root.quit);root.mainloop()
            callback.assert_not_called();ask.assert_not_called();warning.assert_called_once()
