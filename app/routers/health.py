"""Local environment inspection and explicit Inkscape selection."""
from pathlib import Path
from fastapi import APIRouter
from app.config import get_engine,PROJECT_ROOT,CONFIG_FILE
from app.engine.inkscape import InkscapeEngine
from app.routers.project import atomic_write_json
from app.services.errors import AppError,INVALID_PAYLOAD

router=APIRouter(tags=['health'])


@router.get('/api/health')
def health():
    engine=get_engine()
    return {'ok':True,'data':dict(available=engine.available(),version=engine.version() if engine.available() else '',
                                 engine_path=str(engine._exe or ''),data_dir=str(PROJECT_ROOT))}


@router.post('/api/engine')
def set_engine(payload:dict):
    raw=payload.get('path')
    if not isinstance(raw,str) or not raw.strip():
        raise AppError(INVALID_PAYLOAD,'请输入 Inkscape 路径')
    path=Path(raw.strip().strip('"'))
    if path.is_dir():
        path=path/'bin/inkscape.exe'
    if path.name.lower() not in {'inkscape.exe','inkscape.com','inkscape'} or not path.is_file():
        raise AppError(INVALID_PAYLOAD,'请选择有效的 Inkscape 程序')
    engine=InkscapeEngine(path)
    if 'inkscape' not in engine.version().lower():
        raise AppError(INVALID_PAYLOAD,'所选程序未返回有效的 Inkscape 版本')
    atomic_write_json(CONFIG_FILE,{'inkscape':str(path.resolve())})
    get_engine.cache_clear()
    return health()
