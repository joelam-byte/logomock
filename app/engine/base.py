# -*- coding: utf-8 -*-
"""矢量引擎抽象接口 —— 上层（routers/services）唯一依赖此文件。

架构文档 3.1 铁律：
- ``app/services/*`` 与 ``app/routers/*`` 只 import 本文件
- 命令拼装、路径发现、stderr 捕获全部封在具体实现类（inkscape.py）
"""

from pathlib import Path
from typing import Protocol

from app.services.errors import AppError


class VectorEngine(Protocol):
    """矢量引擎抽象。将来换 Cairo / AI COM 只需新增实现类 + 改 config 工厂。"""

    def available(self) -> bool:
        """引擎是否可用（可执行文件存在）。"""
        ...

    def version(self) -> str:
        """版本串，用于 health 与错误提示。不可用时返回空串。"""
        ...

    def to_svg(self, src: Path, svg: Path) -> None:
        """任意受支持的源格式 → SVG。失败抛 EngineError。"""
        ...

    def to_svg_page(self, src: Path, svg: Path, page_number: int) -> None:
        """PDF-compatible source 的指定 1-based 页 → SVG。"""
        ...

    def svg_to_pdf(self, svg: Path, pdf: Path, *, text_to_path: bool = True) -> None:
        """SVG → PDF，可选转曲（默认转曲）。失败抛 EngineError。"""
        ...

    def svg_to_png(self, svg: Path, png: Path) -> None:
        """SVG → PNG（按 SVG 自身尺寸 96dpi 栅格化）。失败抛 EngineError。"""
        ...


class EngineError(AppError):
    """引擎调用失败的异常，附 stderr 原文供排查（错误条 #9）。"""

    def __init__(self, code, message, stderr=""):
        super().__init__(code, message, stderr=stderr)
        self.stderr = stderr
