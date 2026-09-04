# -*- coding: utf-8 -*-
"""FastAPI 入口：挂载路由 + 挂载 web/ 静态目录。

统一错误响应格式：``{"ok": bool, "data": ..., "error": {"code", "message"}}``。
"""

import os
import mimetypes
import threading
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from urllib.parse import urlparse
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import HOST, PORT, WEB_DIR
from app.routers import convert, export, health, project, upload
from app.services.errors import AppError


def _open_browser():
    import time

    time.sleep(1.2)
    webbrowser.open(f"http://{HOST}:{PORT}")


@asynccontextmanager
async def lifespan(_app):
    if os.environ.get("LOGOMOCK_OPEN_BROWSER") == "1":
        threading.Thread(target=_open_browser, daemon=True).start()
    yield


mimetypes.add_type('text/javascript','.mjs')
app = FastAPI(title="logo 工作台", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost','testserver','[::1]'])


@app.middleware('http')
async def local_origin_only(request: Request, call_next):
    if request.method in {'POST','PUT','DELETE','PATCH'}:
        origin = request.headers.get('origin')
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme not in {'http','https'} or parsed.netloc != request.headers.get('host'):
                return JSONResponse(status_code=403,content={'ok':False,'error':{'code':'LOCAL_ONLY','message':'仅允许本地工作台访问'}})
    return await call_next(request)

# 路由
app.include_router(health.router)
app.include_router(project.router)
app.include_router(upload.router)
app.include_router(convert.router)
app.include_router(export.router)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse(
        status_code=200,
        content={"ok": False, "data": None, "error": exc.to_payload()},
    )


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, exc):
    return JSONResponse(status_code=422,content={'ok':False,'error':{'code':'INVALID_PAYLOAD','message':'输入数据不完整或格式不正确'}})


@app.exception_handler(OSError)
async def io_error(_request, exc):
    return JSONResponse(status_code=500,content={'ok':False,'error':{'code':'WRITE_FAILED','message':f'本地文件操作失败：{exc}'}})


# 静态资源
app.mount("/css", StaticFiles(directory=WEB_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=WEB_DIR / "js"), name="js")
app.mount('/web', StaticFiles(directory=WEB_DIR), name='web')


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
