"""Versioned project data. Millimeters are canonical; pixels are a projection."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TaskStatus = Literal['editing', 'waiting_feedback', 'completed']
ColorMode = Literal['original', 'black', 'white', 'gray']


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
    # The new workbench only writes ColorMode values. Keep prior named colours
    # readable so legacy projects can still use their legacy export route.
    color: ColorMode | str = 'original'
    lock_aspect: bool = True

    @field_validator('color', mode='before')
    @classmethod
    def normalise_legacy_color(cls, value):
        return 'original' if value is None else value


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


class AssetPage(Model):
    id: str
    number: int = Field(ge=1)
    label: str
    source_svg: str | None = None
    source_preview: str | None = None
    source_box: Rect | None = None
    objects: list[AssetObject] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    error: str | None = None
    _paths = field_validator('source_svg', 'source_preview')(relative_asset_path)


class Asset(Model):
    id: str
    kind: Literal['vector','raster'] = 'vector'
    pages: list[AssetPage] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    selected_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def migrate_single_page(cls, value):
        if not isinstance(value, dict) or value.get('pages'):
            return value
        if not any(key in value for key in ('source_svg', 'source_preview', 'objects', 'candidates')):
            return value
        data = dict(value)
        candidates = data.get('candidates') or []
        selected_ids = data.get('selected_ids') or []
        data['pages'] = [{
            'id': 'page-0001',
            'number': 1,
            'label': '页面 1',
            'source_svg': data.get('source_svg'),
            'source_preview': data.get('source_preview'),
            'source_box': data.get('source_box'),
            'objects': data.get('objects') or [],
            'candidates': candidates,
        }]
        if 'selected_candidate_ids' not in data:
            selected = set(selected_ids)
            data['selected_candidate_ids'] = [
                (candidate.get('id') if isinstance(candidate, dict) else candidate.id)
                for candidate in candidates
                if set(candidate.get('object_ids') if isinstance(candidate, dict) else candidate.object_ids) == selected
            ]
        return data

    def _first_page(self) -> AssetPage:
        if not self.pages:
            raise ValueError('素材没有可用页面')
        return self.pages[0]

    # Temporary compatibility accessors keep the existing import/export path
    # working while it is upgraded to the page-oriented API below.
    @property
    def source_svg(self) -> str:
        value = self._first_page().source_svg
        if value is None:
            raise ValueError('素材页面没有 SVG 源文件')
        return value

    @property
    def source_preview(self) -> str:
        value = self._first_page().source_preview
        if value is None:
            raise ValueError('素材页面没有预览图')
        return value

    @property
    def source_box(self) -> Rect:
        value = self._first_page().source_box
        if value is None:
            raise ValueError('素材页面没有可用画板')
        return value

    @property
    def objects(self) -> list[AssetObject]:
        return self._first_page().objects

    @property
    def candidates(self) -> list[Candidate]:
        return self._first_page().candidates


class VersionManifest(Model):
    version_id: str = Field(min_length=1, max_length=160)
    # Legacy V1 exports have no intrinsic sequence number and use zero only
    # while marked read-only; modern version folders still enforce >= 1.
    number: int = Field(ge=0)
    created_at: str
    source_revision: int = Field(ge=0)
    preview_path: str
    snapshot_path: str
    output_filename: str
    logo_width_mm: float = Field(ge=0)
    logo_height_mm: float = Field(ge=0)
    color: ColorMode = 'original'
    read_only: bool = False


class Project(Model):
    schema_version: int = 3
    revision: int = Field(default=0, ge=0)
    updated_at: str = ''
    name: str = Field(default='', max_length=100)
    status: TaskStatus = 'editing'
    next_version_number: int = Field(default=1, ge=1)
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
