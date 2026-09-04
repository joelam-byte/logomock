# -*- coding: utf-8 -*-
"""尺寸链几何 + 毫米格式化（架构文档 3.4 / B8）。

- ``fmt_mm()`` 是全项目**唯一**的毫米格式化函数（三份同源保证之一）。
- 尺寸链几何：纯数值/字符串计算，无 IO。

注意：本文件属于导出相关文件，**禁止出现 ``px_per_mm`` 标识符、
禁止任何 px↔mm 换算**（``test_no_recompute.py`` 用源码 grep 断言）。
毫米数字一律由调用方从 scheme 里已算好的 ``size_mm`` / ``offset_mm`` 读出后传入。
"""


def fmt_mm(v, ndigits=2):
    """把毫米数格式化为统一文本。

    round 到 ``ndigits`` 位小数后去尾零，但至少保留一位小数：
    ``75.3 -> "75.3"``、``30.0 -> "30.0"``、``30.05 -> "30.05"``、``0 -> "0.0"``。
    """
    v = round(float(v or 0.0), ndigits)
    s = f"{v:.{ndigits}f}"
    s = s.rstrip("0").rstrip(".")
    if "." not in s:
        s += ".0"
    return s


# 尺寸链视觉参数（SVG 用户单位：spec 为 mm，placement 为像素）
ARROW = 1.6          # 箭头半长
TEXT_H = 4.0         # 尺寸文字高度
DIM_COLOR = "#e24b4a"  # 尺寸链主色
TEXT_COLOR = "#1f2933"


def _n(v):
    """坐标 → 3 位小数字符串（SVG 属性用）。"""
    return f"{float(v):.3f}"


def _esc(s):
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _arrow(points):
    return f'<polygon points="{points}" fill="{DIM_COLOR}"/>'


def h_dim(x0, x1, y_line, y_obj, label):
    """水平尺寸链 SVG 片段（标注 x0→x1 的宽度）。

    - ``y_obj``：被测对象底边 y（延长线起点）
    - ``y_line``：尺寸线所在 y（须在 ``y_obj`` 下方）
    - ``label``：尺寸文字（已由 ``fmt_mm`` 生成，如 "75.3 mm"）
    """
    cx = (x0 + x1) / 2.0
    ext = y_line + 1.5
    parts = [
        # 延长线（对象底边 → 尺寸线下方）
        f'<line x1="{_n(x0)}" y1="{_n(y_obj)}" x2="{_n(x0)}" y2="{_n(ext)}" '
        f'stroke="{DIM_COLOR}" stroke-width="0.35" stroke-dasharray="2,1.5"/>',
        f'<line x1="{_n(x1)}" y1="{_n(y_obj)}" x2="{_n(x1)}" y2="{_n(ext)}" '
        f'stroke="{DIM_COLOR}" stroke-width="0.35" stroke-dasharray="2,1.5"/>',
        # 尺寸线
        f'<line x1="{_n(x0)}" y1="{_n(y_line)}" x2="{_n(x1)}" y2="{_n(y_line)}" '
        f'stroke="{DIM_COLOR}" stroke-width="0.35"/>',
        # 箭头（两端向外）
        _arrow(f"{_n(x0)},{_n(y_line)} {_n(x0 + ARROW)},{_n(y_line - ARROW / 2)} "
               f"{_n(x0 + ARROW)},{_n(y_line + ARROW / 2)}"),
        _arrow(f"{_n(x1)},{_n(y_line)} {_n(x1 - ARROW)},{_n(y_line - ARROW / 2)} "
               f"{_n(x1 - ARROW)},{_n(y_line + ARROW / 2)}"),
        # 文字
        f'<text x="{_n(cx)}" y="{_n(y_line - 1.2)}" font-family="Arial" '
        f'font-size="{TEXT_H}" fill="{TEXT_COLOR}" text-anchor="middle">{_esc(label)}</text>',
    ]
    return f'<g class="dim">{"".join(parts)}</g>'


def v_dim(y0, y1, x_line, x_obj, label, text_side="right"):
    """竖直尺寸链 SVG 片段（标注 y0→y1 的高度）。

    - ``x_obj``：被测对象边 x（延长线起点，通常为对象右边）
    - ``x_line``：尺寸线所在 x（在对象右侧为正，左侧为负向）
    - ``label``：尺寸文字（已由 ``fmt_mm`` 生成，如 "30.0 mm"）
    - ``text_side``：文字置于尺寸线右侧 "right" 或左侧 "left"
    """
    cy = (y0 + y1) / 2.0
    ext = x_line + (1.5 if x_line >= x_obj else -1.5)
    text_anchor = "start" if text_side == "right" else "end"
    text_x = x_line + (2.0 if text_side == "right" else -2.0)
    parts = [
        # 延长线（对象边 → 尺寸线外侧）
        f'<line x1="{_n(x_obj)}" y1="{_n(y0)}" x2="{_n(ext)}" y2="{_n(y0)}" '
        f'stroke="{DIM_COLOR}" stroke-width="0.35" stroke-dasharray="2,1.5"/>',
        f'<line x1="{_n(x_obj)}" y1="{_n(y1)}" x2="{_n(ext)}" y2="{_n(y1)}" '
        f'stroke="{DIM_COLOR}" stroke-width="0.35" stroke-dasharray="2,1.5"/>',
        # 尺寸线
        f'<line x1="{_n(x_line)}" y1="{_n(y0)}" x2="{_n(x_line)}" y2="{_n(y1)}" '
        f'stroke="{DIM_COLOR}" stroke-width="0.35"/>',
        # 箭头（两端向外）
        _arrow(f"{_n(x_line)},{_n(y0)} {_n(x_line - ARROW / 2)},{_n(y0 + ARROW)} "
               f"{_n(x_line + ARROW / 2)},{_n(y0 + ARROW)}"),
        _arrow(f"{_n(x_line)},{_n(y1)} {_n(x_line - ARROW / 2)},{_n(y1 - ARROW)} "
               f"{_n(x_line + ARROW / 2)},{_n(y1 - ARROW)}"),
        # 文字（横向，避免旋转带来的转曲差异）
        f'<text x="{_n(text_x)}" y="{_n(cy + TEXT_H / 3)}" font-family="Arial" '
        f'font-size="{TEXT_H}" fill="{TEXT_COLOR}" text-anchor="{text_anchor}">{_esc(label)}</text>',
    ]
    return f'<g class="dim">{"".join(parts)}</g>'
