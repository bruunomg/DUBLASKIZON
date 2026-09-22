"""Exercise the worker against the installed Hub, with a tiny separate cache."""
from pathlib import Path
import os,sys,json,contextlib,io,importlib,inspect
root=Path(__file__).resolve().parent
os.environ['HF_HOME']=str(root/'f5-download-validation-cache')
os.environ['HF_HUB_OFFLINE']='0'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='20'
os.environ['HF_HUB_ETAG_TIMEOUT']='15'
sys.path.insert(0,str(root/'source'/'DUBLASKIZON-86'))
import f5_backend
import huggingface_hub as hub
print('Installed Hub:',hub.__version__,flush=True)
inspect.signature(hub.hf_hub_download).bind('repo','file',endpoint='https://huggingface.co')
progress=importlib.import_module('huggingface_hub.utils.tqdm')
sys.argv=['worker',json.dumps({f5_backend.MODEL:['README.md','vocab.txt']}),'0']
exec(f5_backend.DOWNLOAD_WORKER,{})
# Validate actual Hub byte-progress factory, including resume offset and completion.
with contextlib.redirect_stdout(io.StringIO()) as output:
    with progress._get_progress_bar_context(desc='byte-test',log_level=20,total=1000,initial=100) as bar:
        bar.last_report=0;bar.update(400);bar.refresh()
        bar.last_report=0;bar.update(500);bar.refresh()
events=[json.loads(line.split(' ',1)[1]) for line in output.getvalue().splitlines() if line.startswith('DUBLASKIZON_TRANSFER ')]
assert any(e['current']==100 for e in events),events
assert any(e['current']==1000 and e['total']==1000 for e in events),events
print('REAL HUB PROGRESS FACTORY OK',flush=True)
# Cache-only repeat should report all bytes already present.
with contextlib.redirect_stdout(io.StringIO()) as output:exec(f5_backend.DOWNLOAD_WORKER,{})
events=[json.loads(line.split(' ',1)[1]) for line in output.getvalue().splitlines() if line.startswith('DUBLASKIZON_TRANSFER ')]
assert any(e.get('kind')=='size' and e['missing']==0 for e in events),events
print('REAL DOWNLOAD AND CACHE REUSE OK',flush=True)
