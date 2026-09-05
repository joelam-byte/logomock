# Task Version and Customer Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn each successful customer-confirmation export into an immutable, manageable local version while preserving an autosaved current draft.

**Architecture:** Keep the existing filesystem-backed project model and revision-checked writes. Add a focused `VersionStore` service which owns internal version folders, manifests, restore and deletion; add a customer exporter that produces one PNG, writes an internal preview, then publishes one user-selected copy only after all validation succeeds.

**Tech Stack:** Python 3.13, FastAPI, Pydantic 2, Pillow, standard-library `tkinter` file dialog, plain JavaScript modules, Node test runner, pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-internal-app-workflow-redesign.md`

## Global Constraints

- Keep all customer assets, drafts and versions local; do not introduce a cloud service, database, account or synchronization feature.
- Preserve original input assets. Only generated files may be placed under the current task's `versions/` directory.
- Canonical placement stays in millimetres: `size_mm` and `offset_mm` determine projected `logo_px` after calibration changes.
- A customer export is exactly one PNG containing product image, placed Logo and a numeric `W × H mm` annotation; no editor guides, status, color name or internal version number may appear.
- An export either creates one complete immutable internal version and one external PNG, or creates neither. Existing versions and the current draft must survive every failed step.
- Restore copies a version snapshot into the current draft. It never mutates a version directory.
- Delete affects only the precise internal version directory after explicit confirmation in the UI. It never touches an externally delivered image.
- Continue serving legacy `/export` output for old projects until the workbench switches to the new customer-export route.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/models.py` | Add task status, monotonic version numbering, color mode and a validated immutable version manifest. |
| `app/services/version_store.py` | Own every read/write/delete operation below `projects/<name>/versions/`. |
| `app/services/customer_export.py` | Render one annotated PNG and publish it atomically to the user-selected destination. |
| `app/services/save_dialog.py` | Isolate the native Windows “Save As” dialog behind a testable function. |
| `app/routers/version.py` | List, restore and delete version endpoints. |
| `app/routers/export.py` | Add `POST /customer-export` without removing the legacy production export endpoint. |
| `app/routers/project.py` | Return task status, last version preview and version count in project listing. |
| `app/main.py` | Register `version.router`. |
| `tests/test_versions.py` | Test local version lifecycle, recovery and deletion boundaries. |
| `tests/test_exports.py` | Test the customer PNG pixels, annotation and atomic customer-export result. |
| `tests/test_projects.py` | Test task-list metadata and v2-to-v3 compatibility. |

## Interfaces

```python
# app/models.py
TaskStatus = Literal['editing', 'waiting_feedback', 'completed']
ColorMode = Literal['original', 'black', 'white', 'gray']

class VersionManifest(Model):
    version_id: str
    number: int
    created_at: str
    source_revision: int
    preview_path: str
    snapshot_path: str
    output_filename: str
    logo_width_mm: float
    logo_height_mm: float
    color: ColorMode
    read_only: bool = False

# app/services/version_store.py
# list_versions(name: str) -> list[VersionManifest]
# load_version(name: str, version_id: str) -> tuple[VersionManifest, Project]
# commit_version(name: str, project: Project, preview: Image.Image,
#                output_filename: str, destination: Path) -> VersionManifest
# restore_version(name: str, version_id: str, expected_revision: int) -> Project
# delete_version(name: str, version_id: str) -> None

# app/services/customer_export.py
def render_confirmation(bag_path: Path, logo_preview_path: Path,
                        scheme: Scheme, crop: Rect | None) -> Image.Image

# app/services/save_dialog.py
# choose_png_destination(initial_name: str) -> Path | None

# app/routers/export.py
# require_single_active_scheme(project: Project) -> Scheme
```

### Task 1: Version-capable project model and listing metadata

**Files:**
- Modify: `app/models.py`
- Modify: `app/routers/project.py`
- Test: `tests/test_projects.py`

**Consumes:** Existing v2 `Project` JSON and `project._commit()` revision validation.

**Produces:** A v3 project that records `status` and `next_version_number`; project-list entries expose `status`, `version_count` and `preview_path` without writing legacy projects during read.

- [ ] **Step 1: Write failing model and listing tests**

```python
def test_legacy_project_reads_with_v3_defaults_without_rewrite(client):
    path = repo.PROJECTS_DIR / 'legacy' / 'project.json'
    path.parent.mkdir(parents=True)
    original = json.dumps({'name': 'legacy', 'schemes': []})
    path.write_text(original, encoding='utf-8')

    loaded = data(client.get('/api/projects/legacy'))
    assert loaded['status'] == 'editing'
    assert loaded['next_version_number'] == 1
    assert path.read_text(encoding='utf-8') == original


def test_project_list_exposes_version_summary_without_reading_output_files(client):
    data(client.post('/api/projects', json={'name': 'sample'}))
    listed = data(client.get('/api/projects'))[0]
    assert listed == {
        'name': 'sample', 'revision': 1, 'updated_at': listed['updated_at'],
        'has_bag': False, 'has_logo': False, 'status': 'editing',
        'version_count': 0, 'preview_path': None,
    }
```

- [ ] **Step 2: Run the focused tests and confirm the new fields are absent**

Run: `python -m pytest tests/test_projects.py::test_legacy_project_reads_with_v3_defaults_without_rewrite tests/test_projects.py::test_project_list_exposes_version_summary_without_reading_output_files -v`

Expected: FAIL because `Project` and list entries do not yet expose the asserted fields.

- [ ] **Step 3: Add compatible typed defaults and read-only list enrichment**

```python
# app/models.py
TaskStatus = Literal['editing', 'waiting_feedback', 'completed']
ColorMode = Literal['original', 'black', 'white', 'gray']

class Project(Model):
    schema_version: int = 3
    status: TaskStatus = 'editing'
    next_version_number: int = Field(default=1, ge=1)
    # existing fields remain below

class Scheme(Model):
    color: ColorMode = 'original'
    lock_aspect: bool = True

    @field_validator('color', mode='before')
    @classmethod
    def normalise_legacy_color(cls, value):
        return 'original' if value is None else value
```

Add `version_store.summary(name)` returning `(count, newest_preview_path)` without changing `project.json`, and use it in `list_projects()`. Change `_commit()` to write `schema_version = 3` only on an actual save.

- [ ] **Step 4: Run focused and existing project tests**

Run: `python -m pytest tests/test_projects.py -v`

Expected: PASS, including stale-write, clone and path-safety coverage.

- [ ] **Step 5: Commit the isolated data-model change**

```bash
git add app/models.py app/routers/project.py tests/test_projects.py
git commit -m "feat: add task version metadata"
```

### Task 2: Immutable filesystem version store

**Files:**
- Create: `app/services/version_store.py`
- Modify: `app/routers/project.py`
- Test: `tests/test_versions.py`

**Consumes:** `Project`, `VersionManifest`, `project.storage_lock()`, `project.atomic_write_json()`, `project.safe_file()` and `Project.revision`.

**Produces:** Version folders at `versions/version-0001/` containing a preview, immutable snapshot and manifest; safe list, load, restore and delete operations.

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_commit_restore_and_delete_version_do_not_mutate_other_state(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    project = repo.create('sample')
    preview = Image.new('RGBA', (40, 30), 'white')
    delivered = tmp_path / 'delivery.png'

    manifest = versions.commit_version('sample', project, preview, 'customer.png', delivered)
    assert manifest.version_id == 'version-0001'
    assert delivered.is_file()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    with TestClient(app) as value:
        yield value
    assert versions.list_versions('sample') == [manifest]

    changed = project.model_copy(deep=True)
    changed.status = 'completed'
    repo.save('sample', changed)
    restored = versions.restore_version('sample', manifest.version_id, changed.revision)
    assert restored.status == 'editing'
    assert versions.load_version('sample', manifest.version_id)[0] == manifest

    versions.delete_version('sample', manifest.version_id)
    assert versions.list_versions('sample') == []
    assert delivered.is_file()
```

- [ ] **Step 2: Run the store test and confirm the module does not exist**

Run: `python -m pytest tests/test_versions.py::test_commit_restore_and_delete_version_do_not_mutate_other_state -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.version_store'`.

- [ ] **Step 3: Implement one lock-scoped VersionStore**

```python
VERSION_ID = re.compile(r'^version-\d{4}$')

def version_dir(name: str, version_id: str) -> Path:
    if not VERSION_ID.fullmatch(version_id):
        raise AppError(INVALID_PAYLOAD, '版本编号无效')
    return project.safe_file(name, f'versions/{version_id}')

def commit_version(name, source, preview, output_filename, destination):
    with project.storage_lock():
        current = project.load(name)
        if current.revision != source.revision:
            raise AppError('REVISION_CONFLICT', '导出前任务已更新，请重新检查后再导出')
        number = current.next_version_number
        version_id = f'version-{number:04d}'
        staging = project.project_dir(name) / 'versions' / f'.pending-{uuid.uuid4().hex}'
        # Write preview.png, snapshot.json and manifest.json; verify preview with Pillow.
        # Copy to destination through a sibling temporary file, then os.replace.
        # Only then os.replace(staging, final) and save incremented next_version_number.
```

Implement `load_version()` with model validation, `restore_version()` with revision checking and a deep snapshot copy, and `delete_version()` with an exact `version-####` path check before `shutil.rmtree()`. Never renumber after deletion.

- [ ] **Step 4: Run version-store coverage**

Run: `python -m pytest tests/test_versions.py -v`

Expected: PASS for ordering, restoring, deletion boundary, malformed manifest rejection and interrupted staging cleanup.

- [ ] **Step 5: Commit the version store**

```bash
git add app/services/version_store.py app/routers/project.py tests/test_versions.py
git commit -m "feat: store immutable task versions"
```

### Task 3: Version API endpoints

**Files:**
- Create: `app/routers/version.py`
- Modify: `app/main.py`
- Test: `tests/test_versions.py`

**Consumes:** `VersionStore` functions from Task 2 and the existing `AppError` response envelope.

**Produces:** `GET /api/projects/{name}/versions`, `POST /api/projects/{name}/versions/{version_id}/restore` and `DELETE /api/projects/{name}/versions/{version_id}`.

- [ ] **Step 1: Write failing route tests**

```python
def test_version_routes_restore_only_from_current_revision(client, monkeypatch, tmp_path):
    source = data(client.post('/api/projects', json={'name': 'sample'}))
    delivered = tmp_path / 'sent.png'
    versions.commit_version('sample', Project.model_validate(source), Image.new('RGBA', (20, 20), 'white'), 'sent.png', delivered)
    listed = data(client.get('/api/projects/sample/versions'))
    assert listed[0]['version_id'] == 'version-0001'

    stale = client.post('/api/projects/sample/versions/version-0001/restore', json={'revision': 0}).json()
    assert stale['ok'] is False
    assert stale['error']['code'] == 'REVISION_CONFLICT'

    current = data(client.get('/api/projects/sample'))
    restored = data(client.post('/api/projects/sample/versions/version-0001/restore', json={'revision': current['revision']}))
    assert restored['revision'] == current['revision'] + 1

    assert data(client.delete('/api/projects/sample/versions/version-0001')) == {'deleted': 'version-0001'}
```

- [ ] **Step 2: Run the route test and verify each endpoint is 404**

Run: `python -m pytest tests/test_versions.py::test_version_routes_restore_only_from_current_revision -v`

Expected: FAIL because `version.router` is not registered.

- [ ] **Step 3: Add thin router handlers and register them**

```python
router = APIRouter(prefix='/api/projects/{name}/versions', tags=['versions'])

@router.get('')
def list_task_versions(name: str):
    project.load(name)
    return {'ok': True, 'data': [item.model_dump() for item in versions.list_versions(name)]}

@router.post('/{version_id}/restore')
def restore_task_version(name: str, version_id: str, payload: dict):
    expected = payload.get('revision')
    if not isinstance(expected, int):
        raise AppError(INVALID_PAYLOAD, '恢复版本需要当前任务修订号')
    return {'ok': True, 'data': versions.restore_version(name, version_id, expected).model_dump()}

@router.delete('/{version_id}')
def delete_task_version(name: str, version_id: str):
    versions.delete_version(name, version_id)
    return {'ok': True, 'data': {'deleted': version_id}}
```

Add `from app.routers import version` and `app.include_router(version.router)` in `app/main.py`.

- [ ] **Step 4: Run API and regression tests**

Run: `python -m pytest tests/test_versions.py tests/test_projects.py -v`

Expected: PASS with the existing consistent `{ok, data, error}` envelope.

- [ ] **Step 5: Commit the version API**

```bash
git add app/routers/version.py app/main.py tests/test_versions.py
git commit -m "feat: expose task version management"
```

### Task 4: Customer PNG renderer and native save destination

**Files:**
- Create: `app/services/customer_export.py`
- Create: `app/services/save_dialog.py`
- Modify: `app/services/selection_png.py`
- Test: `tests/test_exports.py`

**Consumes:** Existing `selection_png.render()`, `Scheme.color`, `Scheme.size_mm` and Pillow.

**Produces:** A reusable renderer with a small numeric `W × H mm` overlay and a save-path function returning `Path | None` on user cancel.

- [ ] **Step 1: Write failing renderer tests**

```python
def test_customer_confirmation_has_logo_and_numeric_mm_annotation_without_guides(tmp_path):
    bag = tmp_path / 'bag.png'
    logo = tmp_path / 'logo.png'
    Image.new('RGB', (240, 180), '#d8c3a9').save(bag)
    Image.new('RGBA', (40, 20), (0, 0, 255, 255)).save(logo)
    scheme = Scheme(logo_px={'x': 80, 'y': 60, 'w': 80, 'h': 40}, size_mm={'w': 50, 'h': 25})

    image = customer_export.render_confirmation(bag, logo, scheme, None)
    assert image.size == (240, 180)
    assert image.getpixel((120, 80))[:3] == (0, 0, 255)
    assert image.getpixel((0, 0))[:3] == (216, 195, 169)
    assert customer_export.annotation_text(scheme) == '50 × 25 mm'


def test_tinted_confirmation_uses_logo_alpha_not_original_blue_pixels(tmp_path):
    # Render a blue source logo using Scheme(color='white') and assert the placed pixel is white.
```

- [ ] **Step 2: Run the renderer tests and confirm the module is missing**

Run: `python -m pytest tests/test_exports.py::test_customer_confirmation_has_logo_and_numeric_mm_annotation_without_guides -v`

Expected: FAIL with `ImportError` for `customer_export`.

- [ ] **Step 3: Implement alpha-preserving color and numeric annotation**

```python
COLOR_RGB = {'black': (0, 0, 0), 'white': (255, 255, 255), 'gray': (64, 64, 64)}

def tint_logo(image: Image.Image, mode: str) -> Image.Image:
    if mode == 'original':
        return image.convert('RGBA')
    result = Image.new('RGBA', image.size, COLOR_RGB[mode] + (0,))
    result.putalpha(image.convert('RGBA').getchannel('A'))
    return result

def annotation_text(scheme: Scheme) -> str:
    return f'{scheme.size_mm.w:g} × {scheme.size_mm.h:g} mm'

def render_confirmation(bag_path, logo_path, scheme, crop):
    image = selection_png.render(bag_path, logo_path, scheme, crop, tint=tint_logo)
    draw = ImageDraw.Draw(image)
    draw.text((12, image.height - 22), annotation_text(scheme), fill='#30343b', font=ImageFont.load_default())
    return image
```

Extend `selection_png.render()` with an optional `tint: Callable[[Image.Image, str], Image.Image] | None` argument; it applies the callback before resize when `scheme.color != 'original'`. Keep the legacy renderer behavior unchanged when no callback is supplied.

Implement `choose_png_destination()` using `tkinter.filedialog.asksaveasfilename` with `defaultextension='.png'`, `filetypes=[('PNG image', '*.png')]`, `confirmoverwrite=True`, and a withdrawn/destroyed root window. Return `None` on cancel; test it by monkeypatching the function, never by opening a real dialog in pytest.

- [ ] **Step 4: Run renderer and existing export tests**

Run: `python -m pytest tests/test_exports.py -v`

Expected: PASS; existing clean-PNG assertions still pass because the legacy render path does not add an annotation.

- [ ] **Step 5: Commit the renderer and dialog boundary**

```bash
git add app/services/customer_export.py app/services/save_dialog.py app/services/selection_png.py tests/test_exports.py
git commit -m "feat: render customer confirmation PNG"
```

### Task 5: Atomic customer-export endpoint

**Files:**
- Modify: `app/routers/export.py`
- Modify: `app/services/version_store.py`
- Test: `tests/test_exports.py`
- Test: `tests/test_versions.py`

**Consumes:** Task 2 version store, Task 4 renderer and save dialog.

**Produces:** `POST /api/projects/{name}/customer-export` which creates exactly one internal version and returns its manifest, or returns a non-error cancellation result with no version.

- [ ] **Step 1: Write endpoint tests for success, cancel and post-render failure**

```python
def test_customer_export_creates_one_version_only_after_external_png_is_written(client, monkeypatch, tmp_path):
    destination = tmp_path / 'sent-to-customer.png'
    monkeypatch.setattr(save_dialog, 'choose_png_destination', lambda _: destination)
    project = ready_project(client)

    result = data(client.post('/api/projects/sample/customer-export', json={
        'revision': project['revision'], 'filename': 'customer-bag.png',
    }))
    assert result['version']['version_id'] == 'version-0001'
    assert destination.is_file()
    assert len(data(client.get('/api/projects/sample/versions'))) == 1


def test_customer_export_cancel_does_not_consume_a_version_number(client, monkeypatch):
    monkeypatch.setattr(save_dialog, 'choose_png_destination', lambda _: None)
    project = ready_project(client)
    result = data(client.post('/api/projects/sample/customer-export', json={'revision': project['revision']}))
    assert result == {'cancelled': True}
    assert data(client.get('/api/projects/sample'))['next_version_number'] == 1
```

Add this concrete helper above both tests in `tests/test_exports.py`:

```python
def ready_project(client):
    data(client.post('/api/projects', json={'name': 'sample'}))
    bag = io.BytesIO()
    Image.new('RGB', (400, 300), 'white').save(bag, format='PNG')
    data(client.post('/api/projects/sample/upload/bag', files={'file': ('bag.png', bag.getvalue(), 'image/png')}))
    logo = io.BytesIO()
    Image.new('RGBA', (40, 20), 'blue').save(logo, format='PNG')
    data(client.post('/api/projects/sample/upload/logo', files={'file': ('logo.png', logo.getvalue(), 'image/png')}))
    project = data(client.post('/api/projects/sample/convert'))
    project.update({
        'calibration': {'product_frame': {'x': 0, 'y': 0, 'w': 400, 'h': 300}, 'width_mm': 200},
        'frames': [{'id': 'front', 'name': 'front', 'x': 0, 'y': 0, 'w': 400, 'h': 300}],
        'schemes': [{'id': 'active', 'frame_id': 'front', 'size_mm': {'w': 50, 'h': 25}, 'offset_mm': {'left': 20, 'bottom': 20}}],
    })
    return data(client.put('/api/projects/sample', json=project))
```

- [ ] **Step 2: Run the endpoint tests and confirm the route is unavailable**

Run: `python -m pytest tests/test_exports.py -k customer_export -v`

Expected: FAIL because `/customer-export` does not exist.

- [ ] **Step 3: Add the endpoint as a separate path from legacy `/export`**

```python
@router.post('/customer-export')
def export_customer_confirmation(name: str, payload: dict):
    source = project.load(name)
    if payload.get('revision') != source.revision:
        raise AppError('REVISION_CONFLICT', '导出前任务已更新，请重新检查后再导出')
    scheme = require_single_active_scheme(source)
    validate_export(source, [scheme])
    destination = save_dialog.choose_png_destination(payload.get('filename') or f'{name}_效果图.png')
    if destination is None:
        return {'ok': True, 'data': {'cancelled': True}}
    preview = customer_export.render_confirmation(
        project.safe_file(name, source.inputs.bag_image),
        project.safe_file(name, source.inputs.logo_preview), scheme, source.crop,
    )
    manifest = versions.commit_version(name, source, preview, destination.name, destination)
    return {'ok': True, 'data': {'cancelled': False, 'version': manifest.model_dump()}}
```

`require_single_active_scheme()` must reject zero or multiple schemes with a user-readable error; Plan 3 changes the workbench so ordinary tasks always have exactly one scheme.

- [ ] **Step 4: Run export/version regression tests**

Run: `python -m pytest tests/test_exports.py tests/test_versions.py tests/test_projects.py -v`

Expected: PASS. Verify that a forced `destination.write_bytes` failure leaves no `versions/version-*` directory and does not increment `next_version_number`.

- [ ] **Step 5: Commit the customer-export API**

```bash
git add app/routers/export.py app/services/version_store.py tests/test_exports.py tests/test_versions.py
git commit -m "feat: archive each customer export"
```

### Task 6: Read-only legacy export adapter

**Files:**
- Modify: `app/services/version_store.py`
- Test: `tests/test_versions.py`

**Consumes:** Existing `output/export-*/snapshot.json` folders from the V1 route.

**Produces:** Legacy exports appear after modern versions as read-only `legacy-*` entries when both a valid snapshot and a PNG exist; restore remains possible but delete is rejected.

- [ ] **Step 1: Write a compatibility test**

```python
def test_legacy_output_snapshot_is_listed_read_only_and_can_restore(client):
    project = data(client.post('/api/projects', json={'name': 'sample'}))
    legacy = repo.project_dir('sample') / 'output' / 'export-legacy'
    legacy.mkdir(parents=True)
    repo.atomic_write_json(legacy / 'snapshot.json', project)
    Image.new('RGBA', (20, 20), 'white').save(legacy / 'mockup-01-A.png')

    item = data(client.get('/api/projects/sample/versions'))[0]
    assert item['version_id'] == 'legacy-export-legacy'
    assert item['read_only'] is True
    assert data(client.post(f"/api/projects/sample/versions/{item['version_id']}/restore", json={'revision': project['revision']}))
    deleted = client.delete(f"/api/projects/sample/versions/{item['version_id']}").json()
    assert deleted['ok'] is False
```

- [ ] **Step 2: Run the compatibility test and confirm old output is not indexed**

Run: `python -m pytest tests/test_versions.py::test_legacy_output_snapshot_is_listed_read_only_and_can_restore -v`

Expected: FAIL because `list_versions()` only inspects `versions/`.

- [ ] **Step 3: Add a non-mutating legacy adapter**

```python
def legacy_manifests(name: str) -> list[VersionManifest]:
    for folder in sorted((project.project_dir(name) / 'output').glob('export-*')):
        snapshot = folder / 'snapshot.json'
        preview = next(folder.glob('mockup-*.png'), None)
        if snapshot.is_file() and preview and preview.is_file():
            yield legacy_manifest(folder, snapshot, preview)
```

Mark the manifest `read_only=True`; make `load_version()` validate its snapshot but never write alongside it. Reject `delete_version()` for IDs beginning `legacy-` with `INVALID_PAYLOAD`.

- [ ] **Step 4: Run complete persistence/export coverage**

Run: `python -m pytest tests/test_versions.py tests/test_exports.py tests/test_projects.py -v`

Expected: PASS, including old project files that remain unchanged until explicitly saved or restored.

- [ ] **Step 5: Commit the compatibility adapter**

```bash
git add app/services/version_store.py tests/test_versions.py
git commit -m "feat: expose legacy export snapshots"
```
