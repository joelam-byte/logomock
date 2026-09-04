"""Clean product renders. No editor guides or document annotations exist here."""
from pathlib import Path
from math import ceil
from PIL import Image,ImageDraw,ImageFont


def render(bag_path,logo_path,scheme,crop=None):
    with Image.open(bag_path) as image:
        bag=image.convert('RGBA')
    with Image.open(logo_path) as image:
        logo=image.convert('RGBA')
    rect=scheme.logo_px
    if rect.w<=0 or rect.h<=0:
        raise ValueError('Logo 尺寸必须大于零')
    # AFFINE's bicubic sampler does not low-pass a large reduction. Prefilter
    # before the fractional placement, or fine logo strokes alias/disappear.
    target=(min(logo.width,max(1,ceil(rect.w))),min(logo.height,max(1,ceil(rect.h))))
    if target!=logo.size:
        logo=logo.resize(target,Image.Resampling.LANCZOS)
    sx,sy=logo.width/rect.w,logo.height/rect.h
    layer=logo.transform(bag.size,Image.Transform.AFFINE,(sx,0,-rect.x*sx,0,sy,-rect.y*sy),
                         Image.Resampling.BICUBIC)
    bag=Image.alpha_composite(bag,layer)
    if crop:
        x=max(0,min(bag.width,round(crop.x)))
        y=max(0,min(bag.height,round(crop.y)))
        right=max(0,min(bag.width,round(crop.x+crop.w)))
        bottom=max(0,min(bag.height,round(crop.y+crop.h)))
        if right<=x or bottom<=y:
            raise ValueError('裁剪框必须与产品图片相交')
        bag=bag.crop((x,y,right,bottom))
    return bag


def save_png(bag_path,logo_path,schemes,out_path,crop=None):
    if len(schemes)!=1:
        raise ValueError('纯净效果图每个文件只能包含一个方案')
    render(bag_path,logo_path,schemes[0],crop).save(out_path,format='PNG')


def save_comparison(images,schemes,out_path):
    tile=420
    gutter=20
    cols=min(3,len(images))
    rows=(len(images)+cols-1)//cols
    canvas=Image.new('RGB',(cols*(tile+gutter)+gutter,rows*(tile+65)+gutter),'#f4f5f7')
    draw=ImageDraw.Draw(canvas)
    font_path=Path('C:/Windows/Fonts/msyh.ttc')
    font=ImageFont.truetype(str(font_path),16) if font_path.exists() else ImageFont.load_default(size=16)
    for index,(image,scheme) in enumerate(zip(images,schemes)):
        x=gutter+(index%cols)*(tile+gutter)
        y=gutter+(index//cols)*(tile+65)
        frame=Image.new('RGBA',(tile,tile),'white')
        thumb=image.copy()
        thumb.thumbnail((tile,tile),Image.Resampling.LANCZOS)
        frame.alpha_composite(thumb,((tile-thumb.width)//2,(tile-thumb.height)//2))
        canvas.paste(frame.convert('RGB'),(x,y))
        label=f'{scheme.id}  |  {scheme.size_mm.w:.2f} × {scheme.size_mm.h:.2f} mm'
        draw.text((x,y+tile+12),label,fill='#202a36',font=font)
    canvas.save(out_path)
