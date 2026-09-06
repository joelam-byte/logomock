# Python runtime and web resources only. Inkscape is intentionally external.
import os
import sys
from pathlib import Path
# A project-local copy makes Tcl discovery reliable under restricted Windows
# build environments. PyInstaller collects it into _tcl_data / _tk_data.
runtime=Path(SPECPATH)/'tools'/'tk-runtime'
runtime_source=next((candidate for candidate in (
    runtime,
    Path(sys.base_prefix)/'Library'/'lib',
    Path(sys.base_prefix)/'lib',
) if (candidate/'tcl8.6').is_dir() and (candidate/'tk8.6').is_dir()), runtime)
for key,relative in [('TCL_LIBRARY','tcl8.6'),('TK_LIBRARY','tk8.6')]:
    if (runtime_source/relative).is_dir():
        os.environ[key]=str(runtime_source/relative)
runtime_dlls=next((candidate for candidate in (
    Path(sys.base_prefix)/'Library'/'bin',
    Path(sys.base_prefix)/'bin',
) if candidate.is_dir()), Path(sys.base_prefix)/'bin')
tk_binaries=[
    (str(runtime_dlls/name),'.') for name in ('tcl86t.dll','tk86t.dll','tcl86.dll','tk86.dll')
    if (runtime_dlls/name).is_file()
]
a = Analysis(['launcher.py'], pathex=[], binaries=tk_binaries, datas=[
                 ('web','web'),
                 (str(runtime_source/'tcl8.6'),'_tcl_data'),
                 (str(runtime_source/'tk8.6'),'_tk_data'),
             ],
             hiddenimports=['tkinter','tkinter.messagebox','uvicorn.logging','uvicorn.loops.auto','uvicorn.protocols.http.auto',
                            'uvicorn.protocols.http.h11_impl','uvicorn.protocols.websockets.auto',
                            'uvicorn.lifespan.on'], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['pytest','httpx','httpx2','matplotlib','IPython'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='LogoMock',debug=False,
          bootloader_ignore_signals=False,strip=False,upx=False,console=False,
          disable_windowed_traceback=False,argv_emulation=False,target_arch=None,
          codesign_identity=None,entitlements_file=None)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='LogoMock')
