import queue
import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from generation_progress import GenerationProgress, run_observed
import personalized_dubbing_tab as custom


class List:
    def __init__(self): self.rows=[];self.selection=set()
    def delete(self,i,end=None):
        if end is not None:self.rows=[];self.selection.clear()
        else:self.rows.pop(i)
    def insert(self,i,*rows):
        if i=='end':self.rows.extend(rows)
        else:self.rows[i:i]=rows
    def selection_set(self,i,end=None):self.selection.add(i)
    def selection_clear(self,i,end=None):
        if end is not None:self.selection.clear()
        else:self.selection.discard(i)
    def curselection(self):return sorted(self.selection)


class Tests(unittest.TestCase):
    def test_busy_tab_blinks_only_in_background_and_stops(self):
        tree=ast.parse((Path(__file__).parent/'Dublaskizon.py').read_text(encoding='utf-8-sig'))
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='poll_tab_activity')
        namespace={};exec(compile(ast.Module(body=[method],type_ignores=[]),'activity-test','exec'),namespace)
        class Button:
            def __init__(self):self.color='normal'
            def configure(self,**kw):self.color=kw.get('bg',self.color)
        root=SimpleNamespace(winfo_exists=lambda:True,after=lambda *a:'timer')
        app=SimpleNamespace(root=root,clone_scroll=object(),review_scroll=object(),terminal_scroll=object(),
                            batch_app=SimpleNamespace(running=True),review_app=SimpleNamespace(busy=True),
                            clone_tab_button=Button(),review_tab_button=Button(),commands_tab_button=Button(),terminal_app=None)
        app.active_scroll=app.clone_scroll
        def reset():
            for button in (app.clone_tab_button,app.review_tab_button,app.commands_tab_button):button.color='normal'
        app.update_tab_buttons=reset
        app.poll_tab_activity=lambda:namespace['poll_tab_activity'](app)
        app.poll_tab_activity()
        self.assertEqual(app.clone_tab_button.color,'normal')
        self.assertEqual(app.review_tab_button.color,'#FBBF24')
        app.poll_tab_activity();self.assertEqual(app.review_tab_button.color,'normal')
        app.review_app.busy=False
        app.poll_tab_activity();self.assertEqual(app.review_tab_button.color,'normal')

    def test_monotonic_output_progress(self):
        events=[];p=GenerationProgress(lambda *e:events.append(e))
        for line in ['Loading model','model loaded','generating audio','sampling: 70%|','sampling: 20%|','audio saved to out.wav']:
            p.feed(line)
        self.assertEqual(p.dub,99)
        self.assertEqual([e[0] for e in events],sorted(e[0] for e in events))
        self.assertEqual([e[1] for e in events],sorted(e[1] for e in events))

    def test_real_subprocess_observed_before_exit(self):
        events=[]
        result=run_observed([sys.executable,'-u','-c',"import time;print('generating audio');print('sampling: 50%|',flush=True);time.sleep(.4);print('audio saved to file')"],
                            lambda *e:events.append(e),runner=subprocess.run,stderr=subprocess.STDOUT,text=True)
        self.assertEqual(result.returncode,0)
        self.assertTrue(any(e[1]==50 for e in events))
        self.assertIn('audio saved',result.stdout)

    def test_initial_selection_and_ok(self):
        app=custom.PersonalizedDubbingApp.__new__(custom.PersonalizedDubbingApp)
        app.stems=['done','pending','pending2'];app.completed_stems={'done'}
        app.scene_list=List();app.status_var=SimpleNamespace(set=lambda text:None)
        app.populate_scenes()
        self.assertEqual(app.scene_list.rows,['[OK] done','pending','pending2'])
        self.assertEqual(app.scene_list.selection,{1,2})
        app.mark_completed('pending')
        self.assertEqual(app.scene_list.rows[1],'[OK] pending')
        self.assertEqual(app.scene_list.selection,{2})

    def test_worker_skips_existing_but_explicit_redub_replaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'custom';out.mkdir();target=out/'scene.wav';target.write_bytes(b'A'*64)
            text=root/'scene.txt';text.write_text('carro caro',encoding='utf-8');model=root/'voice.wav';model.write_bytes(b'voice')
            app=custom.PersonalizedDubbingApp.__new__(custom.PersonalizedDubbingApp)
            app.queue=queue.Queue();app.cancel_requested=False;app.audio_by_stem={'scene':model};app.text_by_stem={'scene':text}
            def launch(args,**kwargs):
                self.assertEqual(args[args.index('--text')+1],'caro caro')
                Path(args[args.index('--output')+1]).write_bytes(b'B'*64)
                return SimpleNamespace(stdout=iter(['generating audio\n','sampling: 50%|\n']),wait=lambda:0,returncode=0)
            def expression(src,original,destination,**kwargs):shutil.copy2(src,destination)
            with patch.object(custom,'ROOT',root),patch.object(custom,'CUSTOM_DIR',out),patch.object(custom,'MANIFEST_FILE',out/'manifest.json'),patch.object(custom.subprocess,'Popen',side_effect=launch) as process,patch.object(custom,'match_original_expression',side_effect=expression):
                app._worker(['scene'],model,['omni'])
                process.assert_not_called();self.assertEqual(target.read_bytes(),b'A'*64)
                app._worker(['scene'],model,['omni'],force=True,r_mode='soft')
                self.assertEqual(text.read_text(encoding='utf-8'),'carro caro')
                self.assertEqual(process.call_count,1);self.assertEqual(target.read_bytes(),b'B'*64)
                events=list(app.queue.queue)
                self.assertTrue(any(e[0]=='stage' and e[2]==50 for e in events))
                self.assertTrue(any(e[0]=='stage' and e[1:4]==(100,100,100) for e in events))


if __name__=='__main__':unittest.main()
