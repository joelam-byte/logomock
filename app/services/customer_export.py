"""The single clean confirmation image sent to a customer."""
from PIL import Image, ImageDraw, ImageFont

from app.services import selection_png


COLOR_RGB = {
    'black': (0, 0, 0),
    'white': (255, 255, 255),
    'gray': (64, 64, 64),
}


def tint_logo(image: Image.Image, mode: str) -> Image.Image:
    if mode not in COLOR_RGB:
        return image.convert('RGBA')
    result = Image.new('RGBA', image.size, COLOR_RGB[mode] + (0,))
    result.putalpha(image.convert('RGBA').getchannel('A'))
    return result


def annotation_text(scheme) -> str:
    return f'{scheme.size_mm.w:g} × {scheme.size_mm.h:g} mm'


def render_confirmation(bag_path, logo_path, scheme, crop):
    image = selection_png.render(bag_path, logo_path, scheme, crop, tint=tint_logo)
    draw = ImageDraw.Draw(image)
    draw.text((12, max(0, image.height - 22)), annotation_text(scheme), fill='#30343b', font=ImageFont.load_default())
    return image
