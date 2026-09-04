"""Analyze sources and commit recoverable, selected clean assets."""
import uuid
from fastapi import APIRouter
from app.config import get_engine
from app.routers import project
from app.services.assets import analyze, apply_selection
from app.services.errors import AppError, INVALID_PAYLOAD

router=APIRouter(prefix='/api/projects/{name}',tags=['assets'])


@router.post('/convert')
def convert_logo(name: str):
    item=project.load(name)
    source=item.inputs.logo_source or item.inputs.logo_svg
    if not source:
        raise AppError(INVALID_PAYLOAD,'请先上传 Logo')
    base=project.project_dir(name)
    folder=project.input_dir(name)/f'asset-{uuid.uuid4().hex}'
    try:
        asset=analyze(project.safe_file(name,source),folder,get_engine(),base)
        asset,clean,preview=apply_selection(asset,asset.selected_ids,base,get_engine())
    except ValueError as exc:
        raise AppError(INVALID_PAYLOAD,str(exc)) from exc
    item.asset=asset
    item.inputs.logo_svg=clean
    item.inputs.logo_preview=preview
    return {'ok':True,'data':project.save(name,item).model_dump()}


@router.post('/asset/select')
def select_asset(name: str,payload: dict):
    item=project.load(name)
    if not item.asset:
        raise AppError(INVALID_PAYLOAD,'请先分析 Logo 素材')
    selected=payload.get('object_ids')
    if not isinstance(selected,list) or any(not isinstance(v,str) for v in selected):
        raise AppError(INVALID_PAYLOAD,'对象选择格式无效')
    try:
        asset,clean,preview=apply_selection(item.asset,selected,project.project_dir(name),get_engine())
    except ValueError as exc:
        raise AppError(INVALID_PAYLOAD,str(exc)) from exc
    item.asset=asset
    item.inputs.logo_svg=clean
    item.inputs.logo_preview=preview
    return {'ok':True,'data':project.save(name,item).model_dump()}
