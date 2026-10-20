"""Build the Windows version resource from the same version as the app title."""
from pathlib import Path
import runpy
root=Path(__file__).resolve().parent
version=runpy.run_path(str(root/'app_version.py'))['APP_VERSION']
parts=tuple(int(x) for x in version.split('.'));parts=(parts+(0,0,0,0))[:4]
resource="VSVersionInfo(ffi=FixedFileInfo(filevers={parts},prodvers={parts},mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),kids=[StringFileInfo([StringTable('041604b0',[StringStruct('FileDescription','DUBLASKIZON V{version}'),StringStruct('FileVersion','{version}'),StringStruct('ProductName','DUBLASKIZON'),StringStruct('ProductVersion','{version}')])]),VarFileInfo([VarStruct('Translation',[1046,1200])])])\n"
(root/'version_info.txt').write_text(resource.format(parts=parts,version=version),encoding='utf-8')
