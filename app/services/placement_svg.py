"""Self-contained A4 placement reference. Page units are mm, not photo pixels."""
import base64
from html import escape
from pathlib import Path
from app.services import dimension
from app.services.spec_svg import page
from app.services.svg_document import embedded_logo,number


def build(bag_path,bag_w,bag_h,frame,scheme,*,logo_path):
    scale=min(174/bag_w,188/bag_h)
    x,y=18,25
    photo_w,photo_h=bag_w*scale,bag_h*scale
    href='data:image/png;base64,'+base64.b64encode(Path(bag_path).read_bytes()).decode('ascii')
    body=f'<rect width="210" height="297" fill="white"/><text x="18" y="14" font-family="Arial,Microsoft YaHei" font-size="5">Logo 定位参考 · {escape(scheme.id)}</text>'
    body+=f'<image x="{x}" y="{y}" width="{number(photo_w)}" height="{number(photo_h)}" href="{href}"/>'
    rect=scheme.logo_px
    lx,ly=x+rect.x*scale,y+rect.y*scale
    lw,lh=rect.w*scale,rect.h*scale
    body+=embedded_logo(logo_path,lx,ly,lw,lh)
    fx,fy=x+frame.x*scale,y+frame.y*scale
    fw,fh=frame.w*scale,frame.h*scale
    body+=f'<rect x="{number(fx)}" y="{number(fy)}" width="{number(fw)}" height="{number(fh)}" fill="none" stroke="#198777" stroke-width=".35" stroke-dasharray="2 1"/>'
    body+=dimension.h_dim(fx,lx,y_line=ly-6,y_obj=ly,label=dimension.fmt_mm(scheme.offset_mm.left)+' mm')
    body+=dimension.v_dim(ly+lh,fy+fh,x_line=lx+lw+6,x_obj=lx+lw,label=dimension.fmt_mm(scheme.offset_mm.bottom)+' mm')
    lines=[f'Logo：{scheme.size_mm.w:.2f} × {scheme.size_mm.h:.2f} mm',
           f'相对参照框：距左 {scheme.offset_mm.left:.2f} mm / 距底 {scheme.offset_mm.bottom:.2f} mm',
           '定位图为缩放参考；实际尺寸以数字和 1:1 工艺稿为准。',
           '绿框为定位参照，不属于印刷图案；纯净效果图见 mockup PNG。']
    if scheme.color not in (None, 'original'):
        lines.insert(2,'指定色号：'+scheme.color)
    for index,line in enumerate(lines):
        body+=f'<text x="18" y="{230+index*8}" font-family="Arial,Microsoft YaHei" font-size="3.6">{escape(line)}</text>'
    return page(210,297,body)
