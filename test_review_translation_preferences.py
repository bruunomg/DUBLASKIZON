import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import audio_translation as translation
from review_tab import ReviewApp

class ReviewTranslationTests(unittest.TestCase):
    def test_totals_are_partitioned_and_custom_source_is_separate(self):
        app=SimpleNamespace(stems=['a','b','c','d','e'],
            state={'a':{'status':'aprovada'},'b':{'status':'avaliar'},'c':{'status':'rejeitada'}},
            review_state_key=lambda value:value,review_totals_var=SimpleNamespace(set=Mock()))
        ReviewApp.update_review_totals(app)
        self.assertEqual(app._review_totals_counts,{'pendente':2,'avaliar':1,'aprovada':1,'rejeitada':1})
        app.review_state_key=lambda value:'personalizado::'+value
        ReviewApp.update_review_totals(app)
        self.assertEqual(app._review_totals_counts['pendente'],5)
        self.assertIn('Padrão (total): 5',app.review_totals_var.set.call_args.args[0])
    def test_settings_survive_reopen_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder,patch('audio_translation.last_settings_path',return_value=Path(folder)/'last.json'):
            config=translation.settings({'language':'Espanhol','faster_model':'small','device':'cpu'})
            translation.save_last_settings(config)
            restored=translation.load_last_settings({'language':'Português (Brasil)'})
            self.assertEqual(restored['language'],'Espanhol');self.assertEqual(restored['faster_model'],'small')
            (Path(folder)/'last.json').write_text('{oops')
            self.assertEqual(translation.load_last_settings()['language'],translation.DEFAULTS['language'])
    def test_translation_exception_does_not_leave_cache_suspended(self):
        from warm_inference import ReviewMemoryCache
        cache=ReviewMemoryCache()
        try:
            with patch('warm_inference.review_memory_cache',cache),patch('audio_translation._generate_text',side_effect=ValueError('erro de teste')):
                with self.assertRaises(ValueError):translation.generate_text('a','b','c','d',{},lambda *_:None)
            self.assertFalse(cache.preparing)
        finally:cache.shutdown()

    def test_existing_text_does_not_evict_loaded_synthesis(self):
        with tempfile.TemporaryDirectory() as folder:
            text=Path(folder)/'scene.txt';text.write_text('Texto já existente',encoding='utf-8')
            with patch('warm_inference.review_memory_cache.translation_session',side_effect=AssertionError('Não deve liberar o motor')):
                result=translation.generate_text('audio',text,folder,'scene',{},lambda *_:None)
            self.assertEqual(result[0],'Texto já existente')

    def test_dialog_reopens_with_last_applied_selection(self):
        import tkinter as tk
        from tkinter import ttk
        root=tk.Tk();root.withdraw()
        self.addCleanup(root.destroy)
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        errors=[]
        def apply_dialog(second=False):
            try:
                window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
                combos=[w for w in widgets(window) if isinstance(w,ttk.Combobox)]
                language=next(w for w in combos if tuple(w.cget('values'))==tuple(translation.LANGUAGES))
                if second:self.assertEqual(language.get(),'Espanhol')
                else:language.set('Espanhol')
                next(w for w in widgets(window) if isinstance(w,ttk.Button) and w.cget('text')=='APLICAR').invoke()
            except Exception as exc:
                errors.append(exc)
                for w in root.winfo_children():
                    if isinstance(w,tk.Toplevel):w.destroy()
        with tempfile.TemporaryDirectory() as folder,patch('audio_translation.last_settings_path',return_value=Path(folder)/'last.json'):
            root.after(150,apply_dialog)
            first=translation.choose_settings(root)
            root.after(150,lambda:apply_dialog(True))
            second=translation.choose_settings(root,translation.DEFAULTS)
        self.assertEqual(errors,[])
        self.assertEqual(first['language'],second['language'])

if __name__=='__main__':unittest.main()
