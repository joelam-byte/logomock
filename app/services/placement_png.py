"""A production placement image with only factory-relevant dimension chains."""
from pathlib import Path

from PIL import ImageDraw, ImageFont

from app.services import customer_export, dimension, selection_png


DIM_COLOR = (226, 75, 74, 255)
EXTENSION_COLOR = (226, 75, 74, 190)


def _label(value: float) -> str:
    return f'{dimension.fmt_mm(value)} mm'


def annotation_plan(frame, scheme, *, pixels_per_mm: float) -> list[dict]:
    """Return the four dimensions drawn on a placement image.

    The two clearance measurements use the closest print-area edges. Their
    labels intentionally contain just a physical value, because the dimension
    chain itself shows which edge or seam it measures to.
    """
    if pixels_per_mm <= 0:
        raise ValueError('产品比例必须大于零')
    logo = scheme.logo_px
    left = (logo.x - frame.x) / pixels_per_mm
    right = (frame.x + frame.w - logo.x - logo.w) / pixels_per_mm
    top = (logo.y - frame.y) / pixels_per_mm
    bottom = (frame.y + frame.h - logo.y - logo.h) / pixels_per_mm
    if left <= right:
        horizontal = ('horizontal-clearance', left, (frame.x, logo.y), (logo.x, logo.y))
    else:
        horizontal = ('horizontal-clearance', right, (logo.x + logo.w, logo.y), (frame.x + frame.w, logo.y))
    if top <= bottom:
        vertical = ('vertical-clearance', top, (logo.x + logo.w, frame.y), (logo.x + logo.w, logo.y))
    else:
        vertical = ('vertical-clearance', bottom, (logo.x + logo.w, logo.y + logo.h), (logo.x + logo.w, frame.y + frame.h))
    return [
        {'kind': horizontal[0], 'label': _label(horizontal[1]), 'start': horizontal[2], 'end': horizontal[3]},
        {'kind': vertical[0], 'label': _label(vertical[1]), 'start': vertical[2], 'end': vertical[3]},
        {'kind': 'logo-width', 'label': _label(scheme.size_mm.w),
         'start': (logo.x, logo.y), 'end': (logo.x + logo.w, logo.y)},
        {'kind': 'logo-height', 'label': _label(scheme.size_mm.h),
         'start': (logo.x + logo.w, logo.y), 'end': (logo.x + logo.w, logo.y + logo.h)},
    ]


def _font(image):
    size = max(15, min(26, round(image.width * 0.027)))
    for path in (Path('C:/Windows/Fonts/segoeui.ttf'), Path('C:/Windows/Fonts/msyh.ttc')):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def _text_size(draw, text, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _label_layout(item, *, axis, line, draw, font):
    (x0, y0), (x1, y1) = item['start'], item['end']
    width, height = _text_size(draw, item['label'], font)
    spacing = 12
    padding = 4
    if axis == 'horizontal':
        text_x = (x0 + x1 - width) / 2
        text_y = line - height - spacing if line <= min(y0, y1) else line + spacing
    else:
        text_x = line + spacing if line >= max(x0, x1) else line - width - spacing
        text_y = (y0 + y1 - height) / 2
    return {
        **item,
        'axis': axis,
        'line': line,
        'text_position': (text_x, text_y),
        'label_box': (
            round(text_x - padding), round(text_y - padding),
            round(text_x + width + padding), round(text_y + height + padding),
        ),
    }


def dimension_layout(image, frame, scheme, *, pixels_per_mm: float) -> list[dict]:
    """Return fully separated line and label geometry for placement PNGs."""
    draw = ImageDraw.Draw(image)
    font = _font(image)
    plan = annotation_plan(frame, scheme, pixels_per_mm=pixels_per_mm)
    logo = scheme.logo_px
    gap = max(14, round(min(image.size) * 0.025))
    return [
        _label_layout(plan[0], axis='horizontal', line=logo.y - gap, draw=draw, font=font),
        _label_layout(plan[1], axis='vertical', line=logo.x + logo.w + gap, draw=draw, font=font),
        _label_layout(plan[2], axis='horizontal', line=logo.y + logo.h + gap, draw=draw, font=font),
        _label_layout(plan[3], axis='vertical', line=logo.x - gap, draw=draw, font=font),
    ]


def _draw_label(draw, item, font):
    draw.rounded_rectangle(item['label_box'], radius=3, fill=(255, 255, 255, 255))
    draw.text(item['text_position'], item['label'], fill=DIM_COLOR, font=font)


def _h_dimension(draw, item, font):
    (x0, y0), (x1, y1) = item['start'], item['end']
    line_y = item['line']
    draw.line((x0, y0, x0, line_y), fill=EXTENSION_COLOR, width=2)
    draw.line((x1, y1, x1, line_y), fill=EXTENSION_COLOR, width=2)
    draw.line((x0, line_y, x1, line_y), fill=DIM_COLOR, width=3)
    arrow = 6
    direction = 1 if x1 >= x0 else -1
    draw.polygon([(x0, line_y), (x0 + direction * arrow, line_y - 3), (x0 + direction * arrow, line_y + 3)], fill=DIM_COLOR)
    draw.polygon([(x1, line_y), (x1 - direction * arrow, line_y - 3), (x1 - direction * arrow, line_y + 3)], fill=DIM_COLOR)
    _draw_label(draw, item, font)


def _v_dimension(draw, item, font):
    (x0, y0), (x1, y1) = item['start'], item['end']
    line_x = item['line']
    draw.line((x0, y0, line_x, y0), fill=EXTENSION_COLOR, width=2)
    draw.line((x1, y1, line_x, y1), fill=EXTENSION_COLOR, width=2)
    draw.line((line_x, y0, line_x, y1), fill=DIM_COLOR, width=3)
    arrow = 6
    direction = 1 if y1 >= y0 else -1
    draw.polygon([(line_x, y0), (line_x - 3, y0 + direction * arrow), (line_x + 3, y0 + direction * arrow)], fill=DIM_COLOR)
    draw.polygon([(line_x, y1), (line_x - 3, y1 - direction * arrow), (line_x + 3, y1 - direction * arrow)], fill=DIM_COLOR)
    _draw_label(draw, item, font)


def render(bag_path, logo_path, frame, scheme, *, pixels_per_mm: float):
    """Render a product image, Logo, and four visible factory dimensions."""
    image = selection_png.render(
        bag_path,
        logo_path,
        scheme,
        tint=customer_export.tint_logo,
    )
    draw = ImageDraw.Draw(image)
    font = _font(image)
    plan = dimension_layout(image, frame, scheme, pixels_per_mm=pixels_per_mm)
    _h_dimension(draw, plan[0], font)
    _v_dimension(draw, plan[1], font)
    _h_dimension(draw, plan[2], font)
    _v_dimension(draw, plan[3], font)
    return image
