"""Task-version list, restore and deletion endpoints."""
from fastapi import APIRouter

from app.routers import project
from app.services import version_store as versions
from app.services.errors import AppError, INVALID_PAYLOAD


router = APIRouter(prefix='/api/projects/{name}/versions', tags=['versions'])


@router.get('')
def list_task_versions(name: str):
    project.load(name)
    return {'ok': True, 'data': [item.model_dump() for item in versions.list_versions(name)]}


@router.post('/{version_id}/restore')
def restore_task_version(name: str, version_id: str, payload: dict):
    expected = payload.get('revision')
    if not isinstance(expected, int):
        raise AppError(INVALID_PAYLOAD, '恢复版本需要当前任务修订号')
    return {'ok': True, 'data': versions.restore_version(name, version_id, expected).model_dump()}


@router.delete('/{version_id}')
def delete_task_version(name: str, version_id: str):
    versions.delete_version(name, version_id)
    return {'ok': True, 'data': {'deleted': version_id}}
