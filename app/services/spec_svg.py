"""1:1 physical artwork and a separate annotated production specification."""
from html import escape
import re
from xml.etree import ElementTree as ET

from app.services import dimension
from app.services.svg_document import DRAWABLE, SVG, embedded_logo, number, prepare_svg, serialize, tag, view_box

MARGIN=15
SPEC_FORMAT='source-page-v3'
VECTOR_COLOR = {'black': '#000000', 'white': '#ffffff', 'gray': '#404040'}
COLOR_LABEL = {'original': '原色', 'black': '黑色', 'white': '白色', 'gray': '深灰'}


def page(width,height,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{number(width)}mm" height="{number(height)}mm" viewBox="0 0 {number(width)} {number(height)}">{body}</svg>'


def build_artwork(logo_path,scheme):
    w,h=scheme.size_mm.w,scheme.size_mm.h
    return page(w,h,embedded_logo(logo_path,0,0,w,h))


def _style_value(style, property_name):
    match=re.search(r'(?:^|;)\s*'+re.escape(property_name)+r'\s*:\s*([^;]+)',style or '',re.I)
    return match.group(1).strip() if match else None


def _without_style_property(style, property_name):
    value=re.sub(r'(^|;)\s*'+re.escape(property_name)+r'\s*:\s*[^;]*',r'\1',style or '',flags=re.I)
    return value.strip(' ;')


def _tint_vector_artwork(root, mode):
    color=VECTOR_COLOR.get(mode)
    if color is None:
        return
    for node in root.iter():
        if tag(node) not in DRAWABLE or tag(node) == 'image':
            continue
        style=node.get('style','')
        fill=_style_value(style,'fill') or node.get('fill')
        stroke=_style_value(style,'stroke') or node.get('stroke')
        # SVG's default for filled shapes is black; only keep fill:none shapes
        # as outlines, then recolor their explicit stroke instead.
        if fill != 'none':
            node.set('fill',color)
            style=_without_style_property(style,'fill')
        if stroke and stroke != 'none':
            node.set('stroke',color)
            style=_without_style_property(style,'stroke')
        if style:
            node.set('style',style)
        else:
            node.attrib.pop('style',None)


def build(logo_path,scheme):
    w,h=scheme.size_mm.w,scheme.size_mm.h
    page_w=max(105,w+50)
    page_h=h+55
    root=prepare_svg(logo_path)
    _tint_vector_artwork(root,scheme.color)
    source=view_box(root)
    scale_x=source.w/w
    scale_y=source.h/h
    page_x=source.x-MARGIN*scale_x
    page_y=source.y-MARGIN*scale_y
    root.set('width',number(page_w)+'mm')
    root.set('height',number(page_h)+'mm')
    root.set('data-logomock-spec',SPEC_FORMAT)
    root.set('viewBox',' '.join(number(value) for value in (
        page_x,page_y,page_w*scale_x,page_h*scale_y,
    )))
    # This is deliberately the original clean SVG page, enlarged for notes.
    # Wrapping it in one more SVG viewport makes some imported AI artwork
    # disappear during Inkscape's PDF conversion.
    root.set('preserveAspectRatio','none')
    body=f'<text x="15" y="8" font-family="Arial,Microsoft YaHei" font-size="3.5">1:1 Logo · {escape(scheme.id)}</text>'
    body+=dimension.h_dim(MARGIN,MARGIN+w,y_line=MARGIN+h+7,y_obj=MARGIN+h,label=dimension.fmt_mm(w)+' mm')
    body+=dimension.v_dim(MARGIN,MARGIN+h,x_line=MARGIN+w+7,x_obj=MARGIN+w,label=dimension.fmt_mm(h)+' mm')
    color=f' · 印色 {COLOR_LABEL.get(scheme.color, "原色")}'
    body+=f'<text x="15" y="{number(page_h-14)}" font-family="Arial,Microsoft YaHei" font-size="3.2">{escape("打印请选 100% / 实际大小"+color)}</text>'
    body+=f'<text x="15" y="{number(page_h-7)}" font-family="Arial,Microsoft YaHei" font-size="3">生产尺寸以红色尺寸标注为准</text>'
    root.append(ET.fromstring(
        f'<g xmlns="{SVG}" transform="translate({number(page_x)} {number(page_y)}) '
        f'scale({number(scale_x)} {number(scale_y)})">{body}</g>'
    ))
    return serialize(root)


def is_current_size_spec(path):
    """Whether a cached production size sheet uses the current PDF-safe form."""
    try:
        return ET.parse(path).getroot().get('data-logomock-spec') == SPEC_FORMAT
    except (OSError, ET.ParseError):
        return False
