"""Versioned project data. Millimeters are canonical; pixels are a projection."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def relative_asset_path(value):
    if value is None:
        return value
    normalized = value.replace('\\', '/')
    parts = normalized.split('/')
    if parts[0] != 'input' or any(p in ('', '.', '..') for p in parts) or ':' in normalized:
        raise ValueError('素材路径必须位于当前项目 input 文件夹')
    return normalized


class Model(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class Rect(Model):
    x: float = 0
    y: float = 0
    w: float = Field(default=0, ge=0)
    h: float = Field(default=0, ge=0)


class Calibration(Model):
    product_frame: Rect = Field(default_factory=Rect)
    width_mm: float = Field(default=0, ge=0)
    height_mm: float | None = Field(default=None, ge=0)
    px_per_mm: float = Field(default=0, ge=0)


class Frame(Rect):
    id: str = Field(default='', max_length=100)
    name: str = Field(default='', max_length=200)


class SizeMM(Model):
    w: float = Field(default=0, ge=0, le=10000)
    h: float = Field(default=0, ge=0, le=10000)


class OffsetMM(Model):
    left: float = 0
    bottom: float = 0


class Scheme(Model):
    id: str = Field(default='', max_length=100)
    name: str = Field(default='', max_length=100)
    frame_id: str = Field(default='', max_length=100)
    logo_px: Rect = Field(default_factory=Rect)
    size_mm: SizeMM = Field(default_factory=SizeMM)
    offset_mm: OffsetMM = Field(default_factory=OffsetMM)
    color: str | None = Field(default=None, max_length=128)


class Inputs(Model):
    bag_image: str | None = None
    logo_source: str | None = None
    logo_svg: str | None = None
    logo_preview: str | None = None
    _paths = field_validator('bag_image','logo_source','logo_svg','logo_preview')(relative_asset_path)


class AssetObject(Model):
    id: str
    label: str
    box: Rect
    reason: Literal['background','dimension'] | None = None
    selected: bool = True


class Candidate(Model):
    id: str
    label: str
    object_ids: list[str]
    box: Rect
    preview: str | None = None
    _paths = field_validator('preview')(relative_asset_path)


class Asset(Model):
    id: str
    source_svg: str
    source_preview: str
    kind: Literal['vector','raster'] = 'vector'
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    source_box: Rect
    objects: list[AssetObject] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    selected_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    _paths = field_validator('source_svg','source_preview')(relative_asset_path)


class Project(Model):
    schema_version: int = 2
    revision: int = Field(default=0, ge=0)
    updated_at: str = ''
    name: str = Field(default='', max_length=100)
    inputs: Inputs = Field(default_factory=Inputs)
    calibration: Calibration = Field(default_factory=Calibration)
    frames: list[Frame] = Field(default_factory=list, max_length=100)
    schemes: list[Scheme] = Field(default_factory=list, max_length=100)
    crop: Rect | None = None
    asset: Asset | None = None

    @model_validator(mode='after')
    def unique_ids(self):
        for values in (self.frames, self.schemes):
            if len({v.id for v in values}) != len(values):
                raise ValueError('方案和参照框 ID 不可重复')
        return self
