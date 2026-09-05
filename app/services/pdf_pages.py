"""Safe page-counting for PDF-compatible AI and PDF source files."""
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


def page_count(source: Path) -> int:
    try:
        reader = PdfReader(source, strict=False)
        if reader.is_encrypted:
            raise ValueError('PDF 已加密，无法读取全部页面')
        count = len(reader.pages)
    except (OSError, PdfReadError) as exc:
        raise ValueError('无法读取 PDF 页面，请重新导出 PDF 兼容 AI、PDF 或 SVG') from exc
    if not 1 <= count <= 100:
        raise ValueError('PDF 页面数无效或超过 100 页')
    return count
