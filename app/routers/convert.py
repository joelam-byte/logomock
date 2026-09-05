"""Analyze sources and commit recoverable, selected clean assets."""
import uuid
from fastapi import APIRouter
from app.config import get_engine
from app.routers import project
from app.services.assets import analyse_source, apply_candidates, apply_selection
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
        engine = get_engine()
        asset=analyse_source(project.safe_file(name,source),folder,engine,base)
        asset,clean,preview=apply_candidates(asset,asset.selected_candidate_ids,base,engine)
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
    selected=payload.get('candidate_ids')
    try:
        if isinstance(selected,list) and all(isinstance(value,str) for value in selected):
            asset,clean,preview=apply_candidates(item.asset,selected,project.project_dir(name),get_engine())
        else:
            # Old one-page projects stored raw object IDs. Keep their existing
            # recovery route only; newly analysed assets must use candidates.
            legacy=payload.get('object_ids')
            is_legacy=bool(item.asset.pages) and all(
                not obj.id.startswith('page-') for obj in item.asset.pages[0].objects
            )
            if not is_legacy or not isinstance(legacy,list) or any(not isinstance(value,str) for value in legacy):
                raise ValueError('请选择一个或多个有效候选内容')
            asset,clean,preview=apply_selection(item.asset,legacy,project.project_dir(name),get_engine())
    except ValueError as exc:
        raise AppError(INVALID_PAYLOAD,str(exc)) from exc
    item.asset=asset
    item.inputs.logo_svg=clean
    item.inputs.logo_preview=preview
    return {'ok':True,'data':project.save(name,item).model_dump()}
