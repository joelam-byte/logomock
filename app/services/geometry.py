"""The single projection used on every save and export snapshot."""
from app.models import Project, Rect
from app.services.errors import AppError, INVALID_PAYLOAD


def normalize_geometry(source: Project) -> Project:
    result = source.model_copy(deep=True)
    cal = result.calibration
    cal.px_per_mm = cal.product_frame.w / cal.width_mm if cal.width_mm > 0 else 0
    ratio = result.asset.height / result.asset.width if result.asset else None
    frames = {frame.id: frame for frame in result.frames}
    for scheme in result.schemes:
        frame = frames.get(scheme.frame_id)
        if ratio is not None:
            scheme.size_mm.h = scheme.size_mm.w * ratio
        if not frame or cal.px_per_mm <= 0:
            continue
        ppm = cal.px_per_mm
        size, offset = scheme.size_mm, scheme.offset_mm
        scheme.logo_px = Rect(x=frame.x + offset.left * ppm,
                              y=frame.y + frame.h - (offset.bottom + size.h) * ppm,
                              w=size.w * ppm, h=size.h * ppm)
    return result


def validate_export(project: Project, schemes):
    cal = project.calibration
    if cal.width_mm <= 0 or cal.product_frame.w <= 0 or cal.product_frame.h <= 0:
        raise AppError(INVALID_PAYLOAD, '请先设置产品标定框及真实宽度（毫米）')
    if not project.asset or not project.inputs.logo_svg or not project.inputs.logo_preview:
        raise AppError(INVALID_PAYLOAD, '请先整理并确认 Logo；旧项目需重新分析素材')
    frames = {f.id: f for f in project.frames}
    for scheme in schemes:
        frame = frames.get(scheme.frame_id)
        if not frame or frame.w <= 0 or frame.h <= 0:
            raise AppError(INVALID_PAYLOAD, f'方案 {scheme.id} 缺少有效参照框')
        if scheme.size_mm.w <= 0 or scheme.size_mm.h <= 0:
            raise AppError(INVALID_PAYLOAD, f'方案 {scheme.id} 的 Logo 尺寸必须大于零')
        if scheme.logo_px.w > 50000 or scheme.logo_px.h > 50000:
            raise AppError(INVALID_PAYLOAD, 'Logo 投影尺寸过大，请检查产品标定单位是否为毫米')
