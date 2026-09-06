"""Immutable uploads. Replacements explicitly invalidate dependent work."""
import io
import uuid
from pathlib import Path
from fastapi import APIRouter, File, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from app.models import Calibration
from app.routers import project
from app.services.errors import AppError, INVALID_PAYLOAD

router = APIRouter(prefix='/api/projects/{name}/upload',tags=['upload'])
MAX_BYTES = 40 * 1024 * 1024
MAX_PIXELS = 30_000_000
RASTER = {'.png','.jpg','.jpeg','.webp'}


async def read_upload(file, allowed):
    extension = Path(file.filename or '').suffix.lower()
    if extension not in allowed:
        raise AppError(INVALID_PAYLOAD,'不支持此文件格式')
    content = bytearray()
    while chunk := await file.read(1024*1024):
        content.extend(chunk)
        if len(content) > MAX_BYTES:
            raise AppError(INVALID_PAYLOAD,'文件超过 40 MB，请先精简文件')
    if not content:
        raise AppError(INVALID_PAYLOAD,'上传文件为空')
    return bytes(content), extension


def image_from_bytes(content):
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise AppError(INVALID_PAYLOAD,'图片过大，最多支持 3000 万像素')
            return ImageOps.exif_transpose(image).convert('RGBA')
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError) as exc:
        raise AppError(INVALID_PAYLOAD,'无法读取图片，请使用有效的 PNG / JPEG / WebP') from exc


@router.post('/bag')
async def upload_bag(name: str, file: UploadFile = File(...)):
    item = project.load(name)
    content, extension = await read_upload(file,RASTER)
    image = image_from_bytes(content)
    token = uuid.uuid4().hex
    folder = project.input_dir(name)
    (folder/f'bag-original-{token}{extension}').write_bytes(content)
    target = folder/f'bag-{token}.png'
    image.save(target)
    item.inputs.bag_image = target.relative_to(project.project_dir(name)).as_posix()
    item.calibration = Calibration()
    item.frames = []
    item.schemes = []
    return {'ok':True,'data':project.save(name,item).model_dump()}


@router.post('/logo')
async def upload_logo(name: str, file: UploadFile = File(...)):
    item = project.load(name)
    content, extension = await read_upload(file,RASTER|{'.svg','.pdf','.ai'})
    if extension in RASTER:
        image_from_bytes(content)
    if extension in {'.ai','.pdf'} and not content.lstrip().startswith(b'%PDF'):
        raise AppError(INVALID_PAYLOAD,'请使用 PDF 兼容的 AI 文件，或先在 Illustrator 中另存为 SVG / PDF')
    target = project.input_dir(name)/f'logo-source-{uuid.uuid4().hex}{extension}'
    target.write_bytes(content)
    item.inputs.logo_source = target.relative_to(project.project_dir(name)).as_posix()
    item.inputs.logo_svg = None
    item.inputs.logo_preview = None
    item.asset = None
    return {'ok':True,'data':project.save(name,item).model_dump()}
