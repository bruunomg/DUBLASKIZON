import tempfile
import time
import wave
from pathlib import Path
import tkinter as tk

import voice_clone_tab


def make_wav(path: Path, seconds: float = 6.0):
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b'\x00\x00' * int(seconds * 8000))


root = tk.Tk()
root.geometry('1500x950')
root.deiconify()
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    source = project / 'fala_teste.wav'
    source2 = project / 'fala_teste_2.wav'
    source3 = project / 'fala_arrastada.wav'
    make_wav(source)
    make_wav(source2, 8)
    make_wav(source3, 7)
    app = voice_clone_tab.VoiceClonePreprocessorApp(root, embedded=False, project_root=project)
    app._add_paths([source, source2])
    root.update_idletasks()
    assert len(app.files) == 2
    assert len(app.file_tree.get_children()) == 2
    assert 'Arquivos: 2' in app.summary_var.get()
    assert app.current_target() == 'omnivoice'
    app.handle_drop(str(source3))
    app.handle_drop(str(source3))
    for _ in range(300):
        root.update()
        if not app.pending_paths and float(app.load_progress.cget('value')) >= 100:
            break
        time.sleep(0.01)
    assert source3.resolve() in app.files
    assert len(app.file_tree.get_children()) == 3
    assert app.last_drop_signature == str(source3)
    assert float(app.load_progress.cget('value')) == 100.0
    assert 'concluído' in app.load_progress_var.get().lower()
    source4 = project / 'fala_formatos.wav'
    make_wav(source4, 5)
    app.load_from_format_conversion([source4])
    assert source4.resolve() in app.files
    for _ in range(100):
        root.update()
        if not app.pending_paths:
            break
        time.sleep(0.01)
    assert source4.resolve() in app.info_by_path
    assert float(app.load_progress.cget('value')) == 100.0
    app.target_combo.set('ElevenLabs Instant')
    app._target_changed()
    assert app.current_target() == 'eleven_instant'
    assert 'Instant' in app.mode_hint_var.get()
    assert app.file_tree.heading('duration')['text'] == 'Duração'
    assert app.file_tree.heading('size')['text'] == 'Tamanho'
    app.file_tree.selection_set(str(source2))
    app._update_selected_metrics()
    root.update_idletasks()
    assert 'fala_teste_2.wav' in app.selected_info_var.get()
    assert len(app.selected_paths(fallback_to_all=False)) == 1
    assert '1 / 4' in app.selected_summary_var.get()
    assert float(app.size_progress.cget('value')) >= 0
    assert float(app.duration_progress.cget('value')) > 0
    app.format_var.set('mp3')
    app._update_selected_metrics()
    assert 'MP3' in app.selected_info_var.get()
    played = {}
    app.audio_player.play_one = lambda path, title, playlist, index: played.update(path=path, title=title, playlist=playlist, index=index)
    app.play_selected_audio()
    assert played['path'] == source2.resolve()
    assert played['playlist'] == [source2.resolve()]
    app._open_selected_file()
    assert played['path'] == source2.resolve(), "o duplo clique deve usar o player interno"
    app.file_tree.selection_set(str(source), str(source2))
    app._update_selected_metrics()
    assert len(app.selected_paths(fallback_to_all=False)) == 2
    assert '2 / 4' in app.selected_summary_var.get()
    app.clear_selection()
    assert app.selected_paths(fallback_to_all=False) == []
    assert '4 / 4' in app.selected_summary_var.get()
    assert app.process_button.winfo_exists()
    assert app.process_progress.winfo_exists()
    assert 'Processamento' in app.process_progress_var.get()
    assert app.add_button.winfo_exists()
    assert (project / 'REDIMENSIONAR ÁUDIO PARA CLONAR') in [Path(path) for _, path, _ in app.folder_button_definitions()]
    assert len(app.folder_button_definitions()) == 8
    assert app.load_format_button.winfo_exists()
    app.target_combo.set('ElevenLabs Professional')
    app._target_changed()
    assert 'Professional' in app.target_help_tooltip.text
    assert '45 minutos' in app.target_help_tooltip.text
    assert app.play_scene_button.winfo_exists()
    assert app.stop_audio_button.winfo_exists()
    assert app.open_output_button.winfo_exists()
    assert app.open_output_button.cget('text') == 'ABRIR SAÍDA'
    opened = {}
    original_popen = voice_clone_tab.subprocess.Popen
    voice_clone_tab.subprocess.Popen = lambda command, **kwargs: opened.update(command=command)
    try:
        app.open_output_folder()
    finally:
        voice_clone_tab.subprocess.Popen = original_popen
    assert str(project / 'REDIMENSIONAR ÁUDIO PARA CLONAR') in opened['command']
    assert app.help_button.winfo_exists()
root.destroy()
print('voice_clone_tab_ok')
