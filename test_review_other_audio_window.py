import tempfile
from pathlib import Path
import tkinter as tk

import review_tab

root = tk.Tk()
root.geometry('1200x850')
root.deiconify()
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    original_dir = project / 'WAV ORIGINAIS'
    text_dir = project / 'TXT TEXTO PORTUGUES'
    original_dir.mkdir(parents=True)
    text_dir.mkdir(parents=True)
    for index in range(18):
        (original_dir / f'original_{index:02d}.wav').write_bytes(b'wav')
        (text_dir / f'original_{index:02d}.txt').write_text('texto da cena', encoding='utf-8')
    (text_dir / 'cena_001.txt').write_text('texto da cena', encoding='utf-8')
    review_tab.configure_project_root(project)
    app = review_tab.ReviewApp(root, embedded=False)
    app.regenerate_with_other_audio()
    root.update_idletasks()
    assert app.other_audio_window is not None
    assert app.other_audio_list is not None
    assert app.other_audio_list.size() == 18
    assert all('original_' in app.other_audio_list.get(index) for index in range(18))
    assert app.other_audio_list.cget('yscrollcommand')
    assert app.other_audio_choose_button.winfo_viewable()
    assert app.other_audio_listen_button.winfo_viewable()
    assert app.other_audio_confirm_button.winfo_viewable()
    assert app.other_audio_cancel_button.winfo_viewable()
    captured = []
    app.audio_player.play_one = lambda path, title, playlist=None, index=None: captured.append((Path(path), title, list(playlist or []), index))
    app.other_audio_list.selection_clear(0, 'end')
    app.other_audio_list.selection_set(5)
    app._update_other_audio_selection()
    app._play_selected_other_audio()
    assert captured and captured[-1][0].name == 'original_05.wav'
    external = project / 'externo.wav'
    external.write_bytes(b'external')
    old_open = review_tab.filedialog.askopenfilename
    review_tab.filedialog.askopenfilename = lambda **kwargs: str(external)
    try:
        app._choose_external_other_audio()
    finally:
        review_tab.filedialog.askopenfilename = old_open
    assert external in app.other_audio_paths
    called = []
    app.regenerate_scene = lambda: called.append(app.alternate_reference_audio)
    app._confirm_other_audio()
    assert called and called[0] == external
    assert app.other_audio_window is None
root.destroy()
print('review_other_audio_window_ok')
