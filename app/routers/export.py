"""One immutable snapshot per export. Failed runs never replace earlier deliverables."""
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from PIL import Image

from app.config import get_engine
from app.routers import project
from app.services import customer_export, placement_png, placement_svg, selection_png, spec_svg
from app.services import version_store as versions
from app.services.errors import AppError,INVALID_PAYLOAD,ENGINE_NOT_FOUND
from app.services.geometry import normalize_geometry,validate_export

router=APIRouter(prefix='/api/projects/{name}',tags=['export'])


def require_single_active_scheme(source):
    if len(source.schemes) != 1:
        raise AppError(INVALID_PAYLOAD, '客户确认图需要且只能保留一个 Logo 方案')
    return source.schemes[0]


@router.post('/customer-export')
def export_customer_confirmation(name: str, payload: dict):
    source = project.load(name)
    if payload.get('revision') != source.revision:
        raise AppError('REVISION_CONFLICT', '导出前任务已更新，请重新检查后再导出')
    scheme = require_single_active_scheme(source)
    validate_export(source, [scheme])
    if not source.inputs.bag_image or not source.inputs.logo_preview:
        raise AppError(INVALID_PAYLOAD, '请先上传产品图片并确认 Logo')
    requested_name = payload.get('filename')
    initial_name = requested_name if isinstance(requested_name, str) and requested_name else f'{name}_效果图.png'
    try:
        preview = customer_export.render_confirmation(
            project.safe_file(name, source.inputs.bag_image),
            project.safe_file(name, source.inputs.logo_preview),
            scheme,
        )
    except (OSError, ValueError) as exc:
        raise AppError(INVALID_PAYLOAD, f'无法生成客户确认图：{exc}') from exc
    destination = versions.customer_delivery_path(name, source.next_version_number, initial_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = versions.commit_version(name, source, preview, destination.name, destination)
    return {'ok': True, 'data': {
        'cancelled': False,
        'version': manifest.model_dump(),
        'output_path': destination.relative_to(project.project_dir(name)).as_posix(),
    }}


@router.post('/versions/{version_id}/production-export')
def export_version_production_files(name: str, version_id: str):
    """Create the three factory files from one immutable customer-confirmed version."""
    manifest, source = versions.load_version(name, version_id)
    snapshot = normalize_geometry(source)
    scheme = require_single_active_scheme(snapshot)
    validate_export(snapshot, [scheme])
    if not snapshot.inputs.bag_image:
        raise AppError(INVALID_PAYLOAD, '请先上传产品图片')
    bag = project.safe_file(name, snapshot.inputs.bag_image)
    logo = project.safe_file(name, snapshot.inputs.logo_svg)
    preview = project.safe_file(name, snapshot.inputs.logo_preview)
    if not all(path.is_file() for path in (bag, logo, preview)):
        raise AppError(INVALID_PAYLOAD, '该版本的素材文件缺失，无法生成生产文件')
    engine = get_engine()
    if not engine.available():
        raise AppError(ENGINE_NOT_FOUND, '导出 Logo 尺寸稿 PDF 需要 Inkscape')

    folder_name = re.sub(r'[^A-Za-z0-9_-]', '_', manifest.version_id)
    output_root = project.project_dir(name) / 'output' / 'production'
    final = output_root / folder_name
    filenames = ['Logo尺寸稿.svg', 'Logo尺寸稿.pdf', '印刷定位图.png']
    if (final.is_dir() and all((final / filename).is_file() for filename in filenames)
            and spec_svg.is_current_size_spec(final / 'Logo尺寸稿.svg')):
        return {'ok': True, 'data': {
            'files': [(Path('output') / 'production' / folder_name / filename).as_posix() for filename in filenames],
            'version_id': manifest.version_id,
        }}

    output_root.mkdir(parents=True, exist_ok=True)
    staging = output_root / f'.pending-{uuid.uuid4().hex}'
    staging.mkdir()
    previous = None
    try:
        size_svg = staging / 'Logo尺寸稿.svg'
        size_pdf = staging / 'Logo尺寸稿.pdf'
        placement = staging / '印刷定位图.png'
        size_svg.write_text(spec_svg.build(logo, scheme), encoding='utf-8')
        engine.svg_to_pdf(size_svg, size_pdf, text_to_path=True)
        frame = next(frame for frame in snapshot.frames if frame.id == scheme.frame_id)
        placement_png.render(
            bag,
            preview,
            frame,
            scheme,
            pixels_per_mm=snapshot.calibration.px_per_mm,
        ).save(placement, format='PNG')
        if final.exists():
            previous = output_root / f'.legacy-{uuid.uuid4().hex}'
            os.replace(final, previous)
        os.replace(staging, final)
        staging = None
        if previous is not None:
            shutil.rmtree(previous)
            previous = None
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        if previous is not None and previous.exists() and not final.exists():
            os.replace(previous, final)

    return {'ok': True, 'data': {
        'files': [(Path('output') / 'production' / folder_name / filename).as_posix() for filename in filenames],
        'version_id': manifest.version_id,
    }}


@router.post('/export')
def export_project(name:str,payload:dict):
    source=project.load(name)
    if payload.get('revision')!=source.revision:
        raise AppError('REVISION_CONFLICT','导出前项目版本已变化，请保存并重新导出')
    snapshot=normalize_geometry(source)
    formats=payload.get('formats',['png','svg','pdf'])
    if not isinstance(formats,list) or not formats or any(f not in {'png','svg','pdf'} for f in formats):
        raise AppError(INVALID_PAYLOAD,'请选择 PNG、SVG 或 PDF 输出格式')
    wanted=payload.get('scheme_ids',[])
    if not isinstance(wanted,list) or any(not isinstance(s,str) for s in wanted):
        raise AppError(INVALID_PAYLOAD,'方案选择格式无效')
    if payload.get('include_unselected'):
        wanted=[s.id for s in snapshot.schemes]
    if not wanted or not set(wanted)<={s.id for s in snapshot.schemes}:
        raise AppError(INVALID_PAYLOAD,'没有有效的导出方案')
    schemes=[s for s in snapshot.schemes if s.id in wanted]
    validate_export(snapshot,schemes)
    if not snapshot.inputs.bag_image:
        raise AppError(INVALID_PAYLOAD,'请先上传产品图片')
    bag=project.safe_file(name,snapshot.inputs.bag_image)
    logo=project.safe_file(name,snapshot.inputs.logo_svg)
    preview=project.safe_file(name,snapshot.inputs.logo_preview)
    if not all(p.is_file() for p in (bag,logo,preview)):
        raise AppError(INVALID_PAYLOAD,'素材文件缺失，请重新上传并分析')
    engine=get_engine()
    engine_ok=engine.available()
    if formats==['pdf'] and not engine_ok:
        raise AppError(ENGINE_NOT_FOUND,'导出 PDF 需要 Inkscape；也可选择 PNG / SVG')
    with Image.open(bag) as image:
        bag_w,bag_h=image.size
    token=f'export-{datetime.now().strftime("%Y%m%d-%H%M%S")}-r{snapshot.revision}-{uuid.uuid4().hex[:8]}'
    output=project.project_dir(name)/'output'
    staging=output/f'.pending-{uuid.uuid4().hex}'
    staging.mkdir(parents=True)
    files=[]
    skipped=[]
    warnings=[]
    images=[]
    for index,scheme in enumerate(schemes,1):
        # User-visible IDs need not be safe filenames or unique after sanitization.
        label=re.sub(r'[^a-zA-Z0-9_-]','_',scheme.id)[:40] or 'scheme'
        suffix=f'{index:02}-{label}'
        rendered=selection_png.render(bag,preview,scheme)
        if payload.get('comparison'):
            images.append(rendered)
        if 'png' in formats:
            filename=f'mockup-{suffix}.png'
            rendered.save(staging/filename,format='PNG')
            files.append(filename)
        frame=next(f for f in snapshot.frames if f.id==scheme.frame_id)
        rect=scheme.logo_px
        if rect.x<frame.x or rect.y<frame.y or rect.x+rect.w>frame.x+frame.w or rect.y+rect.h>frame.y+frame.h:
            warnings.append(dict(code='OUTSIDE_FRAME',message=f'方案 {scheme.id} 超出参照框，请确认印刷区域'))
        if 'svg' in formats or 'pdf' in formats:
            documents={
                'artwork':spec_svg.build_artwork(logo,scheme),
                'spec':spec_svg.build(logo,scheme),
                'placement':placement_svg.build(bag,bag_w,bag_h,frame,scheme,logo_path=logo),
            }
            for kind,document in documents.items():
                svg_name=f'{kind}-{suffix}.svg'
                svg_file=staging/svg_name
                svg_file.write_text(document,encoding='utf-8')
                if 'svg' in formats:
                    files.append(svg_name)
                if 'pdf' in formats:
                    pdf_name=f'{kind}-{suffix}.pdf'
                    if engine_ok:
                        engine.svg_to_pdf(svg_file,staging/pdf_name,text_to_path=True)
                        files.append(pdf_name)
                    else:
                        skipped.append(dict(file=pdf_name,reason='未检测到 Inkscape，PDF 已跳过'))
                if 'svg' not in formats:
                    svg_file.unlink()
    if payload.get('comparison'):
        selection_png.save_comparison(images,schemes,staging/'comparison.png')
        files.append('comparison.png')
    if snapshot.asset.kind=='raster':
        warnings.append(dict(code='RASTER_ARTWORK',message='原 Logo 是位图；SVG / PDF 中仍为嵌入位图，不是真正的矢量生产稿'))
    if skipped:
        warnings.append(dict(code=ENGINE_NOT_FOUND,message='PDF 未生成；已生成的 PNG / SVG 可使用'))
    project.atomic_write_json(staging/'snapshot.json',snapshot.model_dump())
    files.append('snapshot.json')
    final=output/token
    os.replace(staging,final)
    rel=lambda filename:(Path('output')/token/filename).as_posix()
    return {'ok':True,'data':dict(files=[rel(f) for f in files],skipped=skipped,warnings=warnings,
                                 degraded=bool(skipped),revision=snapshot.revision,
                                 scheme_ids=[s.id for s in schemes],output_dir=str(final))}


@router.post('/open-output')
def open_output(name:str):
    project.load(name)
    output=project.project_dir(name)/'output'
    output.mkdir(exist_ok=True)
    if os.name=='nt':
        os.startfile(output)
    return {'ok':True,'data':{'output_dir':str(output)}}
