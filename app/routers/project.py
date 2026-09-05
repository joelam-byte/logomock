"""Local projects: atomic, revision-checked saves and safe paths."""
import json
import os
import re
import shutil
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.config import PROJECTS_DIR
from app.models import Project
from app.services.geometry import normalize_geometry
from app.services.errors import AppError, FILE_NOT_FOUND, INVALID_PAYLOAD, PROJECT_EXISTS, PROJECT_NOT_FOUND

router = APIRouter(prefix='/api/projects', tags=['projects'])
_LOCK = threading.RLock()


def _sanitize(name):
    if not isinstance(name, str) or not name or len(name) > 100:
        raise AppError(INVALID_PAYLOAD, '请输入 1–100 个字符的项目名')
    if name != name.strip() or name.endswith('.') or name in ('.','..'):
        raise AppError(INVALID_PAYLOAD, '项目名不能以空格、句点结尾')
    if re.search(r'[\\\\/:*?"<>|\x00-\x1f]',name):
        raise AppError(INVALID_PAYLOAD, '项目名含文件系统不支持的字符')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        raise AppError(INVALID_PAYLOAD, '该项目名是 Windows 保留名称')
    return name


def project_dir(name):
    base = PROJECTS_DIR.resolve()
    path = (base / _sanitize(name)).resolve()
    if path.parent != base:
        raise AppError(INVALID_PAYLOAD, '非法项目路径')
    return path


def input_dir(name):
    return project_dir(name) / 'input'


def safe_file(name, relative):
    base = project_dir(name)
    target = (base / relative).resolve()
    if not target.is_relative_to(base) or target == base:
        raise AppError(FILE_NOT_FOUND, '非法文件路径')
    return target


@contextmanager
def storage_lock():
    # One local server plus an OS file lock also protects two accidentally started instances.
    with _LOCK:
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        lock_path = PROJECTS_DIR / '.write.lock'
        with lock_path.open('a+b') as lock:
            if os.name == 'nt':
                import msvcrt
                lock.seek(0,2)
                if lock.tell() == 0:
                    lock.write(b'0')
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(),msvcrt.LK_LOCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == 'nt':
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    fcntl.flock(lock,fcntl.LOCK_UN)


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('w',encoding='utf-8') as out:
            json.dump(data,out,ensure_ascii=False,indent=2,allow_nan=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def load(name):
    path = project_dir(name) / 'project.json'
    if not path.is_file():
        raise AppError(PROJECT_NOT_FOUND, f'项目不存在：{name}')
    try:
        project = Project.model_validate_json(path.read_text(encoding='utf-8'))
        project.name = _sanitize(name)
        return project
    except (OSError,ValueError) as exc:
        raise AppError(INVALID_PAYLOAD, f'项目读取失败：{exc}') from exc


def _commit(name, item, current_revision):
    if item.revision != current_revision:
        raise AppError('REVISION_CONFLICT', '项目已在其他窗口更新，请重新打开；当前修改未覆盖新版本',current_revision=current_revision)
    item = normalize_geometry(item)
    item.name = _sanitize(name)
    item.schema_version = 3
    item.revision = current_revision + 1
    item.updated_at = datetime.now(timezone.utc).isoformat()
    # Validate calculated values too (overflow or extreme aspect ratios).
    item = Project.model_validate(item.model_dump())
    atomic_write_json(project_dir(name)/'project.json',item.model_dump())
    return item


def save(name, item):
    item = item if isinstance(item,Project) else Project.model_validate(item)
    with storage_lock():
        current = load(name).revision if (project_dir(name)/'project.json').exists() else 0
        saved = _commit(name,item,current)
    # Internal callers historically return the same object after save.
    item.__dict__.update(saved.__dict__)
    return saved


def create(name):
    safe = _sanitize(name)
    with storage_lock():
        folder = project_dir(safe)
        if folder.exists():
            raise AppError(PROJECT_EXISTS,f'项目或同名文件夹已存在：{safe}')
        (folder/'input').mkdir(parents=True)
        (folder/'output').mkdir()
        return _commit(safe,Project(name=safe),0)


@router.get('')
def list_projects():
    from app.services import version_store

    items = []
    if PROJECTS_DIR.is_dir():
        for folder in PROJECTS_DIR.iterdir():
            if not folder.is_dir() or not (folder/'project.json').is_file():
                continue
            try:
                p = load(folder.name)
                version_count, preview_path = version_store.summary(folder.name)
                items.append(dict(name=p.name,revision=p.revision,updated_at=p.updated_at,
                                  has_bag=bool(p.inputs.bag_image),has_logo=bool(p.inputs.logo_svg),
                                  status=p.status,version_count=version_count,preview_path=preview_path))
            except AppError:
                continue
    return {'ok':True,'data':sorted(items,key=lambda p:(p['updated_at'],p['name']),reverse=True)}


@router.post('')
def create_project(payload: dict):
    return {'ok':True,'data':create(payload.get('name')).model_dump()}


@router.get('/{name}')
def load_project(name: str):
    return {'ok':True,'data':load(name).model_dump()}


@router.put('/{name}')
def save_project(name: str, payload: dict):
    try:
        incoming = Project.model_validate(payload)
        # These fields are server-owned; the separate asset/upload routes version them.
        current = load(name)
        incoming.inputs = current.inputs
        incoming.asset = current.asset
        saved = save(name,incoming)
        return {'ok':True,'data':saved.model_dump()}
    except ValidationError as exc:
        raise AppError(INVALID_PAYLOAD,f'项目数据校验失败：{exc}') from exc


@router.post('/{name}/clone')
def clone_project(name: str, payload: dict):
    target_name = _sanitize(payload.get('name'))
    with storage_lock():
        src = load(name)
        target = project_dir(target_name)
        if target.exists():
            raise AppError(PROJECT_EXISTS,'另存项目名已存在')
        # Only local regular input files, no junction/symlink traversal.
        target.mkdir(parents=True)
        (target/'input').mkdir()
        for file in input_dir(name).rglob('*'):
            if file.is_file():
                safe = safe_file(name,str(file.relative_to(project_dir(name))))
                dest = target / safe.relative_to(project_dir(name))
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(safe,dest)
        (target/'output').mkdir()
        src.name = target_name
        src.revision = 0
        cloned = _commit(target_name,src,0)
    return {'ok':True,'data':cloned.model_dump()}


@router.get('/{name}/file/{file_path:path}')
def get_file(name: str, file_path: str):
    target = safe_file(name,file_path)
    if not target.is_file() or target.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.svg','.pdf','.ai','.json'}:
        raise AppError(FILE_NOT_FOUND,'文件不存在或不允许访问')
    return FileResponse(target,headers={'Content-Security-Policy':"default-src 'none'; img-src data:; style-src 'unsafe-inline'; sandbox",
                                        'X-Content-Type-Options':'nosniff'})
