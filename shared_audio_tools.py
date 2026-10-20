"""Shared audio tools, independent of the project and application folder."""
from pathlib import Path
import os,shutil
NAMES=('ffmpeg','ffprobe','ffplay','sox')
def storage_dir():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Dublaskizon/runtime/ferramentas_audio'
def local_roots(project=None):
    module=Path(__file__).resolve().parent
    app=Path(os.environ.get('DUBLASKIZON_APP_DIR',module)).expanduser()
    bases=[app]+([Path(project).expanduser()] if project else [])+[module]
    return list(dict.fromkeys(p for base in bases for p in (base,base/'ferramentas_audio',base/'tools',base/'sox')))
def find_tool(name,project=None):
    for root in local_roots(project)+[storage_dir()]:
        for filename in (name+'.exe',name):
            candidate=root/filename
            if candidate.is_file():return str(candidate)
        if root.name.casefold() not in ('ferramentas_audio','tools','sox'):continue
        try:
            for candidate in root.rglob('*'):
                if candidate.name.casefold() in (name.casefold(),name.casefold()+'.exe') and candidate.is_file():return str(candidate)
        except OSError:pass
    return shutil.which(name) or shutil.which(name+'.exe')
def prepare_storage(project=None):
    """Reuse existing tools without moving them or replacing shared versions."""
    target=storage_dir();target.mkdir(parents=True,exist_ok=True)
    for name in NAMES:
        if any((target/filename).is_file() for filename in (name,name+'.exe')):continue
        found=find_tool(name,project)
        if not found:continue
        source=Path(found)
        if source.parent.resolve()==target.resolve():continue
        files=[source]+list(source.parent.glob('*.dll'))
        for item in files:
            dest=target/item.name
            if not dest.exists():shutil.copy2(item,dest)
    return target
