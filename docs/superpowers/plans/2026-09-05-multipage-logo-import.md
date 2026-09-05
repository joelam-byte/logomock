# Multi-page Logo Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a business user inspect every parseable page in a PDF-compatible AI/PDF/SVG Logo source, select visually grouped candidates, and confirm one clean Logo without using object-selection tools.

**Architecture:** Extend the asset model from one flattened source to an ordered list of `AssetPage` records. Use `pypdf` only to count PDF pages and Inkscape to convert one page at a time; use source group structure first, then conservative geometry grouping, to form non-overlapping candidate cards. The server stores every page preview and candidate preview locally; the UI later consumes only page/candidate IDs.

**Tech Stack:** Python 3.13, FastAPI, Pydantic 2, Pillow, `pypdf==6.17.0`, Inkscape CLI, defusedxml, pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-internal-app-workflow-redesign.md`

## Global Constraints

- AI support is limited to PDF-compatible AI. Never claim that native legacy AI has been fully read.
- Every successfully parsed page must be shown; a failed page must remain visible with a failure state rather than being silently skipped.
- Preserve source group meaning where it exists: a grouped wordmark must be selectable once, not as individual letters.
- Backgrounds, dimensions and disconnected artwork are suggestions only. A user can select or deselect candidates; the application must never irreversibly remove source content.
- Candidate labels use source names when available, otherwise generic names such as “页面 1”, “组 1” and “对象 1”. No brand-name or Logo-semantic recognition is introduced.
- The confirmation API accepts candidate IDs, not raw client-supplied file paths or arbitrary element IDs.
- Raster advanced cleanup, vectorization and resolution inference remain out of scope. Preserve only the existing best-effort raster import path.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `requirements.txt` | Pin `pypdf==6.17.0` for deterministic multi-page PDF counting. |
| `app/models.py` | Add `AssetPage`; move source SVG, preview, objects and candidates from a single asset into page records. |
| `app/engine/base.py` | Add a per-PDF-page SVG conversion contract. |
| `app/engine/inkscape.py` | Convert a selected PDF page using compatible Inkscape flags. |
| `app/services/pdf_pages.py` | Safely count PDF pages and reject encrypted/corrupt sources. |
| `app/services/svg_document.py` | Prefix page-local SVG IDs safely and discover source-group candidate seeds while preserving document order. |
| `app/services/assets.py` | Analyse pages, produce non-overlapping candidates, and compose selected candidate objects into one clean SVG/PNG. |
| `app/routers/convert.py` | Replace object-ID selection with validated candidate-ID selection. |
| `app/routers/upload.py` | Preserve existing source invalidation and reject unsupported page sources early. |
| `tests/test_assets.py` | Cover grouping, page failure visibility and candidate composition. |
| `tests/test_engine.py` | Cover page-specific Inkscape argument fallback with a fake executable or mocked `_execute`. |
| `tests/test_projects.py` | Cover loading a pre-redesign asset without writing it on read. |

## Interfaces

```python
class AssetPage(Model):
    id: str                       # 'page-0001'
    number: int                   # 1-based source order
    label: str                    # source label or '页面 1'
    source_svg: str | None = None
    source_preview: str | None = None
    source_box: Rect | None = None
    objects: list[AssetObject] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    error: str | None = None

class Asset(Model):
    id: str
    kind: Literal['vector', 'raster']
    pages: list[AssetPage] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    selected_ids: list[str] = Field(default_factory=list)  # derived server-side only
    width: float
    height: float
    warnings: list[str] = Field(default_factory=list)

# Public signatures implemented by this plan:
# VectorEngine.to_svg_page(self, src: Path, svg: Path, page_number: int) -> None
# page_count(source: Path) -> int
# analyse_source(source: Path, folder: Path, engine: VectorEngine, project_root: Path) -> Asset
# apply_candidates(asset: Asset, candidate_ids: list[str], project_root: Path, engine: VectorEngine) -> tuple[Asset, str, str]
```

### Task 1: PDF page counting and page-specific Inkscape conversion

**Files:**
- Modify: `requirements.txt`
- Create: `app/services/pdf_pages.py`
- Modify: `app/engine/base.py`
- Modify: `app/engine/inkscape.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_assets.py`

**Consumes:** Existing `InkscapeEngine._export()` verification and `EngineError` envelope.

**Produces:** A safe 1-based `page_count()` and `VectorEngine.to_svg_page()` for pages 1…N.

- [ ] **Step 1: Write failing page tests**

```python
def test_page_count_reads_all_pdf_pages(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    source = tmp_path / 'two-pages.pdf'
    with source.open('wb') as stream:
        writer.write(stream)
    assert pdf_pages.page_count(source) == 2


def test_inkscape_page_conversion_tries_modern_then_legacy_flag(monkeypatch, tmp_path):
    engine = InkscapeEngine(exe=tmp_path / 'inkscape.exe')
    calls = []
    monkeypatch.setattr(engine, '_export', lambda src, dst, kind, extra=(): calls.append(tuple(extra)))
    engine.to_svg_page(tmp_path / 'source.pdf', tmp_path / 'page.svg', 2)
    assert calls[0] == ('--pages=2',)
```

- [ ] **Step 2: Run the page tests and confirm missing modules/methods**

Run: `python -m pytest tests/test_engine.py -k page tests/test_assets.py -k page_count -v`

Expected: FAIL because `pdf_pages` and `to_svg_page()` do not exist.

- [ ] **Step 3: Implement safe count and cross-version import flags**

```python
# app/services/pdf_pages.py
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

# app/engine/inkscape.py
def to_svg_page(self, src, svg, page_number):
    if page_number < 1:
        raise ValueError('PDF 页码从 1 开始')
    failures = []
    for flag in (f'--pages={page_number}', f'--pdf-page={page_number}'):
        try:
            self._export(src, svg, 'svg', (flag,))
            return
        except EngineError as exc:
            failures.append(exc.stderr or exc.message)
    raise EngineError(CONVERT_FAILED, f'无法读取第 {page_number} 页', stderr='\n'.join(failures))
```

Pin `pypdf==6.17.0` in `requirements.txt`. Update `VectorEngine` protocol and only call `to_svg_page()` for PDF-compatible AI/PDF; native SVG remains a one-page document.

- [ ] **Step 4: Run page and engine regressions**

Run: `python -m pytest tests/test_engine.py tests/test_assets.py -v`

Expected: PASS; real-Inkscape tests may skip only when the executable is unavailable.

- [ ] **Step 5: Commit page conversion support**

```bash
git add requirements.txt app/services/pdf_pages.py app/engine/base.py app/engine/inkscape.py tests/test_engine.py tests/test_assets.py
git commit -m "feat: convert every PDF logo page"
```

### Task 2: Page-oriented compatible asset model

**Files:**
- Modify: `app/models.py`
- Modify: `app/routers/project.py`
- Test: `tests/test_projects.py`

**Consumes:** V3 project model from `2026-09-05-task-version-and-customer-export.md`.

**Produces:** `AssetPage` records with page-local paths and a read-compatible migration from current single-page assets.

- [ ] **Step 1: Write a failing legacy asset load test**

```python
def test_v2_asset_is_exposed_as_one_page_without_rewriting_disk(client):
    path = repo.PROJECTS_DIR / 'legacy' / 'project.json'
    path.parent.mkdir(parents=True)
    original = json.dumps({
        'name': 'legacy',
        'asset': {
            'id': 'a', 'kind': 'vector', 'source_svg': 'input/source.svg',
            'source_preview': 'input/source.png', 'width': 40, 'height': 20,
            'source_box': {'x': 0, 'y': 0, 'w': 40, 'h': 20},
            'objects': [], 'candidates': [], 'selected_ids': [], 'warnings': [],
        },
    })
    path.write_text(original, encoding='utf-8')
    loaded = data(client.get('/api/projects/legacy'))
    assert loaded['asset']['pages'][0]['number'] == 1
    assert path.read_text(encoding='utf-8') == original
```

- [ ] **Step 2: Run the migration test and confirm `pages` is absent**

Run: `python -m pytest tests/test_projects.py::test_v2_asset_is_exposed_as_one_page_without_rewriting_disk -v`

Expected: FAIL because the current `Asset` has only `source_svg`, `objects` and `candidates`.

- [ ] **Step 3: Introduce `AssetPage` and a model-level compatibility adapter**

```python
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

class Asset(Model):
    pages: list[AssetPage] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    # retain old fields only in a `model_validator(mode='before')` migration
```

The before-validator must create one `AssetPage(id='page-0001', number=1, label='页面 1')` by copying the legacy asset's source SVG path, source preview path, source box, objects and candidates, then derive an empty `selected_candidate_ids`. Before writing a newly analysed page SVG, call `svg.prefix_ids(root, 'page-0001--')` so generated object IDs, `<use href>`, `url(#...)` references and the actual stored SVG all use the same prefix. This prevents two source pages from colliding during clean-Logo composition.

- [ ] **Step 4: Run project and model regressions**

Run: `python -m pytest tests/test_projects.py tests/test_assets.py -v`

Expected: PASS. Read-only loading of V2 `project.json` still does not rewrite the file.

- [ ] **Step 5: Commit the page-oriented model**

```bash
git add app/models.py app/routers/project.py tests/test_projects.py tests/test_assets.py
git commit -m "feat: model logo source pages"
```

### Task 3: Candidate seeds that preserve groups and separate suggestions

**Files:**
- Modify: `app/services/svg_document.py`
- Modify: `app/services/assets.py`
- Test: `tests/test_assets.py`

**Consumes:** `AssetPage`, per-page SVG files and Inkscape `query_all()` bounds.

**Produces:** Non-overlapping page-local candidates: source groups are primary selections, while detected backgrounds/dimensions are promoted to separate candidate cards and default unselected.

- [ ] **Step 1: Write failing group-preservation tests**

```python
def test_grouped_wordmark_is_one_candidate_but_nested_background_is_separate(tmp_path):
    source = tmp_path / 'source.svg'
    source.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
      <g id="logo"><rect id="background" width="200" height="100" fill="white"/>
        <g id="word"><path id="s" d="M20 20h10v20H20z"/><path id="t" d="M35 20h10v20H35z"/></g>
      </g><text id="dimension" x="20" y="90">50 mm</text>
    </svg>''')
    root = svg.prefix_ids(svg.prepare_svg(source), 'page-0001--')
    objects = [
        AssetObject(id='page-0001--background', label='对象 1', box={'x': 0, 'y': 0, 'w': 200, 'h': 100}, reason='background', selected=False),
        AssetObject(id='page-0001--s', label='对象 2', box={'x': 20, 'y': 20, 'w': 10, 'h': 20}, selected=True),
        AssetObject(id='page-0001--t', label='对象 3', box={'x': 35, 'y': 20, 'w': 10, 'h': 20}, selected=True),
        AssetObject(id='page-0001--dimension', label='对象 4', box={'x': 20, 'y': 82, 'w': 40, 'h': 8}, reason='dimension', selected=False),
    ]
    page = assets.group_page_candidates(root, objects, page_id='page-0001', page_number=1)
    by_members = {frozenset(c.object_ids) for c in page.candidates}
    assert frozenset({'page-0001--s', 'page-0001--t'}) in by_members
    assert frozenset({'page-0001--background'}) in by_members
    assert frozenset({'page-0001--dimension'}) in by_members
```

- [ ] **Step 2: Run candidate tests and confirm current geometry-only grouping fails**

Run: `python -m pytest tests/test_assets.py -k 'grouped_wordmark or nested_background' -v`

Expected: FAIL because `group_candidates()` flattens drawable elements and has no source-group seed information.

- [ ] **Step 3: Add source-tree candidate seed extraction**

```python
# app/services/svg_document.py
def prefix_ids(root: ET.Element, prefix: str) -> ET.Element:
    """Deep-copy root and rewrite ids, hrefs and url(#id) references with prefix."""
    # Reuse the URL and style-reference rewrites already used by select_svg().

def candidate_seed_ids(root: ET.Element) -> list[tuple[str, list[str]]]:
    """Return document-order, non-overlapping drawable-id groups."""
    # Prefer each meaningful <g> subtree; fall back to individual direct drawables.
    # Do not descend into a selected group again, so candidates never overlap.

# app/services/assets.py
def group_page_candidates(root, objects):
    suggested = {obj.id: obj.reason for obj in objects}
    candidates = []
    for label, ids in svg.candidate_seed_ids(root):
        normal = [ident for ident in ids if suggested[ident] is None]
        hinted = [ident for ident in ids if suggested[ident] in {'background', 'dimension'}]
        if normal:
            candidates.append(candidate_from_ids(label or generic_group_name(group_index), normal))
        for ident in hinted:
            candidates.append(candidate_from_ids(generic_object_name(object_index), [ident]))
    return candidates
```

Use the existing proximity grouping only for ungrouped normal drawables. Candidate IDs must be stable within one analysis run and start with their `page-####` prefix. Remove the current 30-candidate truncation; render all candidates, paginating in the UI instead of hiding source content.

- [ ] **Step 4: Run all asset tests**

Run: `python -m pytest tests/test_assets.py -v`

Expected: PASS for transformed groups, `<use>` dependencies, background/dimension suggestions and disconnected art.

- [ ] **Step 5: Commit group-preserving candidates**

```bash
git add app/services/svg_document.py app/services/assets.py tests/test_assets.py
git commit -m "feat: preserve logo groups in candidates"
```

### Task 4: Analyse all pages and apply candidate selections

**Files:**
- Modify: `app/services/assets.py`
- Modify: `app/routers/convert.py`
- Modify: `app/routers/upload.py`
- Test: `tests/test_assets.py`
- Test: `tests/test_projects.py`

**Consumes:** Tasks 1–3.

**Produces:** `/convert` records an `AssetPage` for every source page; `/asset/select` accepts `candidate_ids` and creates one clean selected SVG/PNG from their server-derived object IDs.

- [ ] **Step 1: Write failing all-pages and candidate-composition tests**

```python
def test_analysis_keeps_failed_second_page_visible_and_does_not_silently_drop_it(monkeypatch, client):
    project = uploaded_two_page_pdf_project(client)
    original = assets.analyse_svg_page
    def fail_page_two_only(*args, **kwargs):
        if kwargs['number'] == 2:
            raise EngineError('CONVERT_FAILED', '页面内容损坏')
        return original(*args, **kwargs)
    monkeypatch.setattr(assets, 'analyse_svg_page', fail_page_two_only)
    result = data(client.post('/api/projects/sample/convert'))
    assert [page['number'] for page in result['asset']['pages']] == [1, 2]
    assert result['asset']['pages'][0]['error'] is None
    assert '第 2 页' in result['asset']['pages'][1]['error']


def test_select_candidates_unions_only_their_server_side_objects(client, monkeypatch):
    project, candidate_ids = ready_multi_candidate_project(client)
    seen = {}
    def fake_apply(asset, candidate_ids, project_root, engine):
        seen['candidate_ids'] = candidate_ids
        asset.selected_candidate_ids = candidate_ids
        asset.selected_ids = ['page-0001--word', 'page-0001--mark']
        return asset, 'input/clean.svg', 'input/clean.png'
    monkeypatch.setattr(convert, 'apply_candidates', fake_apply)
    chosen = candidate_ids
    saved = data(client.post('/api/projects/sample/asset/select', json={'candidate_ids': chosen}))
    assert saved['asset']['selected_candidate_ids'] == chosen
    assert seen['candidate_ids'] == chosen
    assert saved['asset']['selected_ids'] == ['page-0001--word', 'page-0001--mark']
```

Add these concrete test helpers above the two tests:

```python
def uploaded_two_page_pdf_project(client):
    data(client.post('/api/projects', json={'name': 'sample'}))
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    source = io.BytesIO()
    writer.write(source)
    return data(client.post('/api/projects/sample/upload/logo', files={'file': ('source.pdf', source.getvalue(), 'application/pdf')}))

def ready_multi_candidate_project(client):
    data(client.post('/api/projects', json={'name': 'sample'}))
    item = repo.load('sample')
    first = Candidate(id='page-0001--candidate-1', label='组 1', object_ids=['page-0001--word'], box={'x': 10, 'y': 10, 'w': 40, 'h': 20})
    second = Candidate(id='page-0001--candidate-2', label='对象 1', object_ids=['page-0001--mark'], box={'x': 70, 'y': 10, 'w': 20, 'h': 20})
    page = AssetPage(id='page-0001', number=1, label='页面 1', source_svg='input/source.svg', source_preview='input/source.png', source_box={'x': 0, 'y': 0, 'w': 100, 'h': 60}, candidates=[first, second])
    item.asset = Asset(id='asset', kind='vector', pages=[page], selected_candidate_ids=[], selected_ids=[], width=40, height=20)
    item.inputs = Inputs(logo_source='input/source.pdf')
    repo.save('sample', item)
    return item.model_dump(), [first.id, second.id]
```

- [ ] **Step 2: Run route tests and verify current object-ID contract fails**

Run: `python -m pytest tests/test_assets.py -k 'failed_second_page or select_candidates' -v`

Expected: FAIL because `/convert` returns one page and `/asset/select` expects `object_ids`.

- [ ] **Step 3: Implement all-page analysis and candidate-only selection**

```python
def analyse_source(source, folder, engine, project_root):
    count = page_count(source) if source.suffix.lower() in {'.pdf', '.ai'} else 1
    pages = []
    for number in range(1, count + 1):
        page_id = f'page-{number:04d}'
        try:
            page_svg = folder / f'{page_id}.svg'
            if count == 1 and source.suffix.lower() == '.svg':
                shutil.copy2(source, page_svg)
            else:
                engine.to_svg_page(source, page_svg, number)
            pages.append(analyse_svg_page(page_svg, engine, project_root, page_id, number))
        except (ValueError, EngineError) as exc:
            pages.append(AssetPage(id=page_id, number=number, label=f'页面 {number}', error=f'第 {number} 页无法读取：{exc}'))
    if not any(page.candidates for page in pages):
        raise ValueError('没有可用的 Logo 内容，请检查源文件或 Inkscape 设置')
    first = next(page for page in pages if page.candidates)
    first_candidate = first.candidates[0]
    return Asset(
        id=uuid.uuid4().hex, kind='vector', pages=pages,
        selected_candidate_ids=[first_candidate.id], selected_ids=list(first_candidate.object_ids),
        width=first_candidate.box.w, height=first_candidate.box.h,
        warnings=['请确认所选内容后再进入排版。'],
    )

def apply_candidates(asset, candidate_ids, project_root, engine):
    candidates = {candidate.id: candidate for page in asset.pages for candidate in page.candidates}
    if not candidate_ids or not set(candidate_ids) <= candidates.keys():
        raise ValueError('请选择一个或多个有效候选内容')
    # Collect page roots and selected page-qualified element IDs, then compose them into one SVG.
```

Keep an adapter accepting legacy `object_ids` only when `asset.pages` came from a legacy one-page model; all newly analysed assets must use `candidate_ids`. Invalidate derived `asset`, clean SVG and preview when uploading a new Logo exactly as today.

- [ ] **Step 4: Run API, asset and project regressions**

Run: `python -m pytest tests/test_assets.py tests/test_projects.py tests/test_engine.py -v`

Expected: PASS; a malformed page produces a visible page error while a valid earlier page remains selectable.

- [ ] **Step 5: Commit multi-page analysis and selection**

```bash
git add app/services/assets.py app/routers/convert.py app/routers/upload.py tests/test_assets.py tests/test_projects.py
git commit -m "feat: select logo candidates across pages"
```

### Task 5: Full-suite import safety and packaged dependency verification

**Files:**
- Modify: `requirements-dev.txt` only if it mirrors runtime requirements
- Modify: `LogoMock.spec` only if PyInstaller does not collect `pypdf` during the build check
- Test: `tests/test_assets.py`
- Test: `tests/test_engine.py`

**Consumes:** Completed Tasks 1–4.

**Produces:** A reproducible environment and a verified multi-page import path in the packaged desktop app.

- [ ] **Step 1: Add a real-engine smoke fixture test guarded by Inkscape availability**

```python
def test_real_inkscape_can_import_page_two_when_available(tmp_path):
    engine = get_engine()
    if not engine.available():
        pytest.skip('Inkscape required for multi-page import smoke test')
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    source = tmp_path / 'two-pages.pdf'
    with source.open('wb') as stream:
        writer.write(stream)
    output = tmp_path / 'page-2.svg'
    engine.to_svg_page(source, output, 2)
    assert output.is_file() and output.stat().st_size > 100
```

- [ ] **Step 2: Run the focused smoke test**

Run: `python -m pytest tests/test_engine.py::test_real_inkscape_can_import_page_two_when_available -v`

Expected: PASS when Inkscape is configured, otherwise SKIP with the stated reason.

- [ ] **Step 3: Build and inspect dependency collection**

Run: `python -m pip install -r requirements-dev.txt; .\build.bat`

Expected: `dist/LogoMock.exe` is built. If startup reports `ModuleNotFoundError: pypdf`, add `pypdf` to the `hiddenimports` list in the existing `Analysis` configuration in `LogoMock.spec`, then rebuild.

- [ ] **Step 4: Run the full automated suite after the build-source change**

Run: `python -m pytest tests -q; node --test tests/editor.test.mjs`

Expected: PASS, with only explicitly guarded real-Inkscape tests skipped.

- [ ] **Step 5: Commit the verified dependency/package changes**

```bash
git add requirements.txt requirements-dev.txt LogoMock.spec tests/test_engine.py
git commit -m "build: package multipage logo import"
```
