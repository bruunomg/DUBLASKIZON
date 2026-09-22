"""Bootstrap regression tests: no network, no installs in the user's environment."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from types import SimpleNamespace

import dependency_setup as setup


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"LOCALAPPDATA": str(self.root), "HF_HOME": str(self.root / "hf")})
        self.env.start()
        self.lines = []
        self.job = setup.SetupJob(self.lines.append)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def active(self, name="old"):
        path = setup.runtime_root() / name / "Scripts" / "python.exe"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"test")
        (setup.runtime_root() / "active.json").write_text(json.dumps({"python": path.relative_to(setup.runtime_root()).as_posix()}))
        return path

    def test_pointer_does_not_escape_runtime(self):
        path = self.active()
        self.assertEqual(setup.managed_python(), path.resolve())
        (setup.runtime_root() / "active.json").write_text('{"python":"../../outside.exe"}')
        self.assertIsNone(setup.managed_python())

    def test_existing_official_python_skips_maintenance_installer(self):
        installed=self.root/'Python313'/'python.exe'
        installed.parent.mkdir();installed.write_bytes(b'python')
        with patch.object(setup,'installed_python313',return_value=[installed]),patch.object(self.job,'run') as run,patch.object(self.job,'download_python') as download:
            self.assertEqual(self.job.ensure_base_python(),installed)
            download.assert_not_called()
            self.assertEqual(run.call_args.args[0][0],installed)

    def test_installer_success_without_python_has_clear_failure(self):
        with patch.object(setup,'installed_python313',return_value=[]),patch.object(self.job,'run'),patch.object(self.job,'download_python',return_value=self.root/'installer.exe'):
            with self.assertRaisesRegex(RuntimeError,'nenhum Python 3.13'):
                self.job.ensure_base_python()
        self.assertIsNone(setup.managed_python())

    def test_rediscover_actual_location_after_installer(self):
        actual=self.root/'existing'/'python.exe'
        with patch.object(setup,'installed_python313',side_effect=[[],[],[actual]]),patch.object(self.job,'run'),patch.object(self.job,'download_python',return_value=self.root/'installer.exe'):
            self.assertEqual(self.job.ensure_base_python(),actual)

    def test_actual_process_stream_and_failure(self):
        self.job.run([sys.executable, "-u", "-c", "import time;print('FIRST');time.sleep(.3);print('SECOND')"])
        log = self.job.log.read_text(encoding="utf-8")
        self.assertIn("FIRST", log)
        self.assertIn("SECOND", log)
        with self.assertRaises(RuntimeError):
            self.job.run([sys.executable, "-c", "raise SystemExit(7)"])

    def test_ffmpeg_directory_reaches_child_without_changing_global_path(self):
        directory=self.root/'ferramentas com espaço';directory.mkdir()
        executable=directory/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg');executable.write_bytes(b'test')
        original=os.environ.get('PATH')
        self.job.ffmpeg_dir=directory
        self.job.run([sys.executable,'-c',"import os,shutil;from pathlib import Path;assert Path(shutil.which('ffmpeg')).resolve()==Path(os.environ['FFMPEG_BINARY']).resolve();print('FFMPEG VISIVEL')"])
        self.assertIn('FFMPEG VISIVEL',self.job.log.read_text(encoding='utf-8'))
        self.assertEqual(os.environ.get('PATH'),original)

    def test_actual_process_cancel(self):
        timer = threading.Timer(.4, self.job.cancel.set)
        timer.start()
        try:
            with self.assertRaises(setup.Cancelled):
                self.job.run([sys.executable, "-c", "import time;time.sleep(60)"])
        finally:
            timer.join()

    def test_actual_timeout(self):
        with self.assertRaises(TimeoutError):
            self.job.run([sys.executable, "-c", "import time;time.sleep(60)"], timeout=.2)

    def test_official_environment_ignores_pip_mirrors(self):
        with patch.dict(os.environ, {"PIP_EXTRA_INDEX_URL": "https://example.invalid", "HF_ENDPOINT": "https://example.invalid", "PYTHONPATH": "bad"}):
            env = setup.official_environment()
            self.assertNotIn("PIP_EXTRA_INDEX_URL", env)
            self.assertNotIn("PYTHONPATH", env)
            self.assertEqual(env["HF_ENDPOINT"], "https://huggingface.co")
            self.assertEqual(env["PIP_CONFIG_FILE"], os.devnull)

    def test_hash_mismatch_cannot_create_installer(self):
        class Response(io.BytesIO):
            url = setup.PYTHON_URL
            headers = {"Content-Length": "3"}
        with patch.object(setup.urllib.request, "urlopen", side_effect=lambda *a, **k: Response(b"bad")), patch.object(self.job.cancel, "wait"):
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                self.job.download_python()
        self.assertFalse((setup.runtime_root() / f"python-{setup.PYTHON_VERSION}-amd64.exe").exists())

    def test_download_official_redirect_only(self):
        class Response(io.BytesIO):
            url = "https://other.example/python.exe"
            headers = {}
        with patch.object(setup.urllib.request, "urlopen", side_effect=lambda *a, **k: Response(b"")), patch.object(self.job.cancel, "wait"):
            with self.assertRaisesRegex(RuntimeError, "Redirecionamento"):
                self.job.download_python()

    def test_failed_install_keeps_previous_environment(self):
        old = self.active()
        base = setup.runtime_root() / f"python-{setup.PYTHON_VERSION}" / "python.exe"
        base.parent.mkdir()
        base.write_bytes(b"fake")
        with patch.object(self.job, "run", side_effect=RuntimeError("failure")), patch.object(setup.shutil, "disk_usage", return_value=type("Disk", (), {"free": 30 * 1024**3})()):
            with self.assertRaises(RuntimeError):
                self.job._install_locked("cpu")
        self.assertEqual(setup.managed_python(), old.resolve())

    def test_activate_only_after_all_checks(self):
        old = self.active()
        base = setup.runtime_root() / f"python-{setup.PYTHON_VERSION}" / "python.exe"
        base.parent.mkdir()
        base.write_bytes(b"fake")
        commands = []
        def run(args, **kwargs):
            self.assertEqual(setup.managed_python(), old.resolve())
            commands.append([str(a) for a in args])
            if "venv" in args:
                path = Path(args[-1]) / "Scripts" / "python.exe"
                path.parent.mkdir(parents=True)
                path.write_bytes(b"new")
        with patch.object(self.job, "run", side_effect=run), patch.object(setup.shutil, "disk_usage", return_value=type("Disk", (), {"free": 30 * 1024**3})()):
            self.job._install_locked("cu128")
        self.assertNotEqual(setup.managed_python(), old.resolve())
        self.assertTrue(old.exists())
        self.assertTrue(any("https://download.pytorch.org/whl/cu128" in c for c in commands))
        self.assertTrue(any("omnivoice==0.2.1" in c for c in commands))
        self.assertTrue(any("check" in c for c in commands))
        self.assertTrue(any("--help" in c for c in commands))

    def test_cache_and_inference_routing(self):
        self.active()
        model = setup.MODELS[0]
        path = self.root / "OmniVoice" / "hf_cache" / model
        path.mkdir(parents=True)
        (path / "config.json").write_text("{}")
        self.assertIsNone(setup.legacy_model_path(model))
        for name in ("tokenizer.json", "model.safetensors"):
            (path / name).write_bytes(b"test")
        self.assertEqual(setup.legacy_model_path(model), path)
        command = setup.inference_command()
        args = ["-c", "--model", model, "--text", "hello"]
        with patch.object(sys, "argv", args), patch("runpy.run_module") as run_module:
            exec(command[-1], {})
            self.assertEqual(args[2], str(path))
            run_module.assert_called_once_with("omnivoice.cli.infer", run_name="__main__")

    def test_model_download_and_offline_test(self):
        self.active()
        with patch.object(self.job, "run") as run:
            self.job.download_models(setup.MODELS[0], True)
            self.assertEqual(json.loads(run.call_args.args[0][-2]), [setup.MODELS[0], setup.CODEC, setup.WHISPER])
            self.assertEqual(run.call_args.args[0][-1],'0')
            self.job.download_models(setup.MODELS[0],False,sizes_only=True)
            self.assertEqual(json.loads(run.call_args.args[0][-2]),[setup.MODELS[0],setup.CODEC])
            self.assertEqual(run.call_args.args[0][-1],'1')
            self.job.test_model(setup.MODELS[0], True)
            self.assertIn("HF_HUB_OFFLINE", run.call_args.args[0][3])

    def test_transfer_parser_chunked_bytes_and_unknown_totals(self):
        events=[];parser=setup.TransferParser(events.append)
        parser.feed('Downloading torch.whl\nProgress 100')
        self.assertEqual(events,[])
        parser.feed('0000000 of 4000000000\nProgress 120 of 0\n')
        self.assertEqual(events[0],{'name':'torch.whl','current':1000000000,'total':4000000000})
        self.assertEqual(events[1]['total'],0)
        parser.feed('DUBLASKIZON_TRANSFER {"kind":"size","total":300,"missing":100}\n')
        self.assertEqual(events[-1]['missing'],100)
        self.assertEqual(setup.byte_size(4_000_000_000),'4.00 GB')

    def test_transfer_reports_cache_and_older_pip_downloads(self):
        events=[];parser=setup.TransferParser(events.append)
        parser.feed('Using cached torch.whl (3461.4 MB)\n')
        self.assertEqual(events[-1]['kind'],'cache')
        parser.feed('Downloading torch.whl\n  ----- 125.0/500.0 MB 20 MB/s\n')
        self.assertEqual(events[-1]['current'],125000000)
        self.assertEqual(events[-1]['total'],500000000)
        parser.feed('Installing collected packages: torch\n')
        self.assertEqual(events[-1]['kind'],'activity')

    def test_model_size_query_does_not_download_and_transfer_preserves_cache(self):
        files=[SimpleNamespace(filename='cached',file_size=10,will_download=False,commit_hash='abc'),SimpleNamespace(filename='new',file_size=90,will_download=True,commit_hash='abc')]
        snapshots=[];downloads=[];printed=[]
        def snapshot(*args,**kwargs):
            snapshots.append(kwargs)
            return files if kwargs.get('dry_run') else 'cached-snapshot'
        class Bar:
            def __init__(self,*args,**kwargs):pass
        module=SimpleNamespace(snapshot_download=snapshot,hf_hub_download=lambda *a,**k:downloads.append((a,k)))
        with patch.dict(sys.modules,{'huggingface_hub':module,'tqdm.auto':SimpleNamespace(tqdm=Bar)}),patch('builtins.print',side_effect=lambda *a,**k:printed.append(str(a[0]))):
            with patch.object(sys,'argv',['worker','["repo"]','1']):exec(setup.MODEL_DOWNLOAD_WORKER,{})
            self.assertEqual(downloads,[])
            with patch.object(sys,'argv',['worker','["repo"]','0']):exec(setup.MODEL_DOWNLOAD_WORKER,{})
        self.assertEqual(len(downloads),2)
        self.assertTrue(any('"missing": 90' in line for line in printed))
        self.assertTrue(all(k['revision']=='abc' for _,k in downloads))

    def test_processing_detects_nvidia_or_falls_back_to_cpu(self):
        exe=self.root/'nvidia-smi.exe';exe.write_bytes(b'exe')
        with patch.object(setup.shutil,'which',return_value=str(exe)),patch.object(setup.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='NVIDIA RTX 5060, 8192\n')):
            result=setup.detect_processing();self.assertEqual(result['variant'],'cu128');self.assertIn('5060',result['gpu'])
        with patch.object(setup.shutil,'which',return_value=None),patch.object(Path,'is_file',return_value=False):
            self.assertEqual(setup.detect_processing()['variant'],'cpu')

    def test_batch_prefers_managed_but_respects_override(self):
        import batch_tab
        self.active()
        with patch.dict(os.environ, {"OMNIVOICE_INFER": ""}):
            self.assertEqual(batch_tab.find_omnivoice_command()[0], str(setup.managed_python()))
        exe = self.root / "custom.exe"
        exe.write_bytes(b"test")
        with patch.dict(os.environ, {"OMNIVOICE_INFER": str(exe)}):
            self.assertEqual(batch_tab.find_omnivoice_command(), [str(exe)])

    def test_assistant_controls_queue_completion_and_close(self):
        import tkinter as tk
        from tkinter import ttk, messagebox
        import batch_tab
        widgets = []
        class Widget:
            def __init__(self, *a, **kw):
                self.kw, self.value, self.callbacks, self.exists = kw, kw.get("value", ""), [], True
                widgets.append(self)
            def configure(self, **kw): self.kw.update(kw)
            def cget(self, key): return self.kw.get(key,0)
            def get(self): return self.value
            def set(self, value): self.value = value
            def pack(self, **kw): pass
            def grid(self, **kw): pass
            def columnconfigure(self, *a, **kw): pass
            def title(self, *a): pass
            def geometry(self, *a): pass
            def minsize(self, *a): pass
            def transient(self, *a): pass
            def iconbitmap(self, *a): pass
            def protocol(self, *a): pass
            def bind(self, *a, **kw): pass
            def after(self, ms, callback): self.callbacks.append(callback)
            def winfo_exists(self): return self.exists
            def winfo_screenheight(self): return 1080
            def destroy(self): self.exists = False
            def lift(self): pass
            def insert(self, *a): pass
            def index(self, *a): return "1.0"
            def delete(self, *a): pass
            def see(self, *a): pass
            def yview(self, *a): pass
            def start(self, *a): pass
            def stop(self): pass
        app = SimpleNamespace(root=None, dependency_window=None, current_theme=lambda: {"root":"#222"},
                              should_show_dependency_assistant=lambda: True,
                              save_dependency_assistant_preference=lambda value: None,
                              ensure_control_contrast=lambda w: None, prepare_shared_audio_tools=lambda: None)
        class ImmediateThread:
            def __init__(self, target, **kw): self.target = target
            def start(self): self.target()
        with ExitStack() as stack:
            for module, names in ((tk, ("Toplevel", "Label", "Text", "StringVar", "BooleanVar")),
                                  (ttk, ("Frame", "LabelFrame", "Label", "Button", "Checkbutton", "Combobox", "Progressbar", "Scrollbar"))):
                for name in names: stack.enter_context(patch.object(module, name, Widget))
            stack.enter_context(patch.object(setup.threading, "Thread", ImmediateThread))
            stack.enter_context(patch.object(setup,'detect_processing',return_value={'variant':'cpu','cpu':'AMD teste','gpu':'CPU'}))
            stack.enter_context(patch.object(batch_tab, "find_omnivoice_command", return_value=None))
            stack.enter_context(patch.object(batch_tab, "find_ffmpeg_directory", return_value=None))
            diagnose = stack.enter_context(patch.object(setup.SetupJob, "diagnose"))
            stack.enter_context(patch.object(messagebox, "askyesno", return_value=False))
            setup.show_assistant(app)
            window = app.dependency_window
            buttons = {w.kw.get("text"): w for w in widgets if "command" in w.kw}
            buttons["VERIFICAR"].kw["command"]()
            self.assertEqual(buttons["VERIFICAR"].kw["state"], "disabled")
            window.callbacks.pop(0)()
            diagnose.assert_called_once_with(None, None)
            self.assertEqual(buttons["VERIFICAR"].kw["state"], "normal")
            self.assertEqual(buttons["CANCELAR"].kw["state"], "disabled")
            buttons["1. INSTALAR / REPARAR"].kw["command"]()
            self.assertEqual(buttons["VERIFICAR"].kw["state"], "normal")
            buttons["CONTINUAR"].kw["command"]()
            self.assertIsNone(app.dependency_window)


if __name__ == "__main__":
    unittest.main()

