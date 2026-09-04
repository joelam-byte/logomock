# -*- coding: utf-8 -*-
"""路径常量、端口、Inkscape 路径解析（配置 → 注册表 → 默认）。

本文件是矢量引擎的**工厂**所在：上层（routers/services）只通过
``get_engine()`` 拿 ``VectorEngine`` 抽象实例，不感知具体实现。
"""

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

# 项目根 = app/ 的上一级
RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
PROJECT_ROOT = Path(os.environ.get('LOGOMOCK_DATA_DIR') or (
    Path(sys.executable).parent if getattr(sys, 'frozen', False) else RESOURCE_ROOT))
WEB_DIR = RESOURCE_ROOT / "web"
PROJECTS_DIR = PROJECT_ROOT / "projects"
CONFIG_FILE = PROJECT_ROOT / "config.json"

HOST = "127.0.0.1"
PORT = int(os.environ.get('LOGOMOCK_PORT', '8000'))

# Inkscape 输出 SVG 使用 96dpi 用户单位（架构文档 3.1 / 5）
PX96_PER_MM = 3.7795275591


def configured_inkscape_path():
    """从项目根 ``config.json`` 读取用户显式指定的 Inkscape 路径（优先级最高）。

    返回 ``Path`` 或 ``None``。示例 config.json::

        {"inkscape": "D:/Program Files/Inkscape/bin/inkscape.exe"}
    """
    explicit = os.environ.get('LOGOMOCK_INKSCAPE')
    if explicit and Path(explicit).is_file():
        return Path(explicit)
    if not CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    raw = data.get("inkscape")
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_file():
        return candidate
    return None


@lru_cache(maxsize=1)
def get_engine():
    """工厂：返回矢量引擎实现实例（单例）。上层唯一获取引擎的入口。"""
    from app.engine.inkscape import InkscapeEngine

    return InkscapeEngine()
