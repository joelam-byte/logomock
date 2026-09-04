# -*- coding: utf-8 -*-
"""统一应用错误类型与错误码。

架构文档 3.1 / 6.1：错误响应统一 ``{"ok": bool, "data": ..., "error": {"code", "message"}}``，
阻断级前端弹窗、提示级前端黄色信息条。

完整 12+4 条错误清单的落地在 B10（错误收口），本文件当前只定义
B0～B4 所需的错误码与 ``AppError`` 基类，后续批次在此追加。
"""


class ErrorLevel:
    """错误级别：阻断（弹窗）与提示（黄色信息条）。"""

    BLOCK = "block"
    WARN = "warn"


class AppError(Exception):
    """统一应用错误。所有业务异常都应抛出或继承本类。"""

    def __init__(self, code, message, level=ErrorLevel.BLOCK, **detail):
        super().__init__(message)
        self.code = code
        self.message = message
        self.level = level
        self.detail = detail

    def to_payload(self):
        payload = {"code": self.code, "message": self.message, "level": self.level}
        if self.detail:
            payload.update(self.detail)
        return payload


# ---- 错误码常量 ----
# 引擎层（3.1）
ENGINE_NOT_FOUND = "ENGINE_NOT_FOUND"                # 错误条 #8：Inkscape 未安装/不可用
INPUT_UNREADABLE = "INPUT_UNREADABLE"                # 引擎层：输入不可读（EPS 等）
UNKNOWN_EXPORT_TYPE = "UNKNOWN_EXPORT_TYPE"          # 引擎层：未知导出类型（如 ai）
MULTIPAGE_FIRST_PAGE_ONLY = "MULTIPAGE_FIRST_PAGE_ONLY"  # 引擎层：多页取第一页（#14，提示级）

# 转换/上传层（错误条 #9）
CONVERT_FAILED = "CONVERT_FAILED"                    # 转换失败，附 stderr 原文

# 导出层（错误条 #10 / #11）
WRITE_FAILED = "WRITE_FAILED"                        # 输出目录写入失败（阻断）
TEXT_NOT_CONVERTED = "TEXT_NOT_CONVERTED"            # 文字未转曲（提示级，非阻断）

# 项目层
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
PROJECT_EXISTS = "PROJECT_EXISTS"
INVALID_PAYLOAD = "INVALID_PAYLOAD"
FILE_NOT_FOUND = "FILE_NOT_FOUND"
