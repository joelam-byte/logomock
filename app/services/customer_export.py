"""The single clean confirmation image sent to a customer."""
from pathlib import Path

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
    def compact(value: float) -> str:
        return f'{value:.1f}'.rstrip('0').rstrip('.')

    return f'{compact(scheme.size_mm.w)} x {compact(scheme.size_mm.h)} mm'


def annotation_font_size(image_width: int) -> int:
    return max(28, min(36, round(image_width * 0.04)))


def annotation_position(image_size: tuple[int, int], text_size: tuple[int, int]) -> tuple[int, int]:
    width, height = image_size
    text_width, text_height = text_size
    margin = max(20, round(height * 0.025))
    return ((width - text_width) // 2, height - text_height - margin)


def annotation_font(size: int):
    for path in (Path('C:/Windows/Fonts/segoeui.ttf'), Path('C:/Windows/Fonts/msyh.ttc')):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def render_confirmation(bag_path, logo_path, scheme):
    image = selection_png.render(bag_path, logo_path, scheme, tint=tint_logo)
    draw = ImageDraw.Draw(image)
    text = annotation_text(scheme)
    font = annotation_font(annotation_font_size(image.width))
    bounds = draw.textbbox((0, 0), text, font=font)
    position = annotation_position(image.size, (bounds[2] - bounds[0], bounds[3] - bounds[1]))
    draw.text(position, text, fill='#30343b', font=font)
    return image
