# -*- coding: utf-8 -*-
"""Windows 注册表读取（HKLM\\SOFTWARE\\Inkscape\\Inkscape）。

探测报告第 1 节：注册表位置 ``HKLM\\SOFTWARE\\Inkscape\\Inkscape``
→ ``D:\\Program Files\\Inkscape``。Inkscape 不在 PATH，必须靠注册表定位。
"""

import sys
from pathlib import Path

# 注册表值名候选（不同版本 Inkscape 写入的值名不一）
_VALUE_NAMES = ("", "InstallDir", "InstallPath", "AppPath", "(default)")


def find_inkscape_from_registry():
    """从注册表定位 Inkscape，返回 ``inkscape.exe`` 的 ``Path`` 或 ``None``。"""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:  # pragma: no cover - 非 Windows 环境
        return None

    hives = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Inkscape\Inkscape"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Inkscape\Inkscape"),
    )
    for hive, subkey in hives:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                for value_name in _VALUE_NAMES:
                    try:
                        value, _ = winreg.QueryValueEx(key, value_name)
                    except OSError:
                        continue
                    if not value:
                        continue
                    exe = _resolve_exe(Path(value))
                    if exe is not None:
                        return exe
        except OSError:
            continue
    return None


def _resolve_exe(base):
    """注册表值可能是安装目录或 exe 路径，统一解析为 ``inkscape.exe``。"""
    candidates = []
    if base.suffix.lower() == ".exe":
        candidates.append(base)
    else:
        candidates.append(base / "bin" / "inkscape.exe")
        candidates.append(base / "inkscape.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
