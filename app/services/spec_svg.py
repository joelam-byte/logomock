"""1:1 physical artwork and a separate annotated production specification."""
from html import escape
from app.services import dimension
from app.services.svg_document import embedded_logo,number

MARGIN=15


def page(width,height,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{number(width)}mm" height="{number(height)}mm" viewBox="0 0 {number(width)} {number(height)}">{body}</svg>'


def build_artwork(logo_path,scheme):
    w,h=scheme.size_mm.w,scheme.size_mm.h
    return page(w,h,embedded_logo(logo_path,0,0,w,h))


def build(logo_path,scheme):
    w,h=scheme.size_mm.w,scheme.size_mm.h
    page_w=max(105,w+50)
    page_h=h+55
    body=f'<text x="15" y="8" font-family="Arial,Microsoft YaHei" font-size="3.5">1:1 Logo · {escape(scheme.id)}</text>'
    body+=embedded_logo(logo_path,MARGIN,MARGIN,w,h)
    body+=dimension.h_dim(MARGIN,MARGIN+w,y_line=MARGIN+h+7,y_obj=MARGIN+h,label=dimension.fmt_mm(w)+' mm')
    body+=dimension.v_dim(MARGIN,MARGIN+h,x_line=MARGIN+w+7,x_obj=MARGIN+w,label=dimension.fmt_mm(h)+' mm')
    color=f' · 色号 {scheme.color}' if scheme.color not in (None, 'original') else ''
    body+=f'<text x="15" y="{number(page_h-14)}" font-family="Arial,Microsoft YaHei" font-size="3.2">{escape("打印请选 100% / 实际大小"+color)}</text>'
    body+=f'<text x="15" y="{number(page_h-7)}" font-family="Arial,Microsoft YaHei" font-size="3">生产用无标注稿见 artwork 文件</text>'
    return page(page_w,page_h,body)
