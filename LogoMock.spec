# Python runtime and web resources only. Inkscape is intentionally external.
import os
from pathlib import Path
# A project-local copy makes Tcl discovery reliable under restricted Windows
# build environments. PyInstaller collects it into _tcl_data / _tk_data.
runtime=Path(SPECPATH)/'tools'/'tk-runtime'
for key,relative in [('TCL_LIBRARY','tcl8.6'),('TK_LIBRARY','tk8.6')]:
    if (runtime/relative).is_dir():
        os.environ[key]=str(runtime/relative)
a = Analysis(['launcher.py'], pathex=[], binaries=[], datas=[('web','web')],
             hiddenimports=['tkinter','tkinter.messagebox','uvicorn.logging','uvicorn.loops.auto','uvicorn.protocols.http.auto',
                            'uvicorn.protocols.http.h11_impl','uvicorn.protocols.websockets.auto',
                            'uvicorn.lifespan.on'], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['pytest','httpx','httpx2','matplotlib','IPython'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,a.binaries,a.datas,[],name='LogoMock',debug=False,
          bootloader_ignore_signals=False,strip=False,upx=False,console=False,
          disable_windowed_traceback=False,argv_emulation=False,target_arch=None,
          codesign_identity=None,entitlements_file=None)
