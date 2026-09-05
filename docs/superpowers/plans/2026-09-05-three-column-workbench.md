# Three-column Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the instruction-heavy multi-scheme workspace with a stable three-column task workbench that guides business users through Logo confirmation, direct placement, one-image export and version recovery.

**Architecture:** Retain the local browser workbench and SVG editor, but split the current monolithic `main.mjs` into focused state, asset-picker and version-panel modules. The grid always remains left resources, center visual work area and right context controls; only each column's content changes as the task state advances.

**Tech Stack:** HTML, CSS, ES modules, browser SVG, FastAPI local APIs, Node `node:test`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-internal-app-workflow-redesign.md`

## Global Constraints

- Core working screens keep the exact three-column order: resources on the left, visual work in the center and current controls on the right.
- Do not expose “enter group”, raw object IDs, rectangle-selection mode, per-letter selection or long step instructions to a business user.
- Natural state controls replace persistent tutorials: show the next valid main action and keep unavailable actions disabled or absent.
- The task supports one active Logo placement. Customer iterations belong to versions, not a strip of parallel design schemes.
- Product calibration retains existing millimetre behavior; do not redesign its input model.
- The right panel offers only original, black, white and dark gray Logo display modes. Do not add Pantone, arbitrary color pickers or automatic contrast advice.
- Customer export creates one PNG and its internal version. It must not offer SVG/PDF/placement/spec/comparison options in the daily UI.
- Version labels are internal only. Customer images never show a version number, color mode, selection rectangle, control point or reference frame.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `web/index.html` | Stable semantic three-column shell and minimal top bar. |
| `web/workspace/workspace.css` | Fixed grid, compact state-specific components and responsive minimum-width treatment. |
| `web/workspace/state.mjs` | Pure task-state selectors: next primary action, one active scheme and version-panel state. |
| `web/workspace/main.mjs` | Small orchestrator: API calls, SaveQueue adoption and wiring modules. |
| `web/workspace/assets.mjs` | Page sidebar + candidate-card Logo picker; removes raw object controls. |
| `web/workspace/editor.mjs` | Eight control points, direct Logo move/resize, clean preview and color-display filter. |
| `web/workspace/versions.mjs` | Version list/preview/actions and restore/delete confirmation dialogs. |
| `web/workspace/persistence.mjs` | Add typed wrappers for customer export and version APIs. |
| `web/workspace/geometry.mjs` | Enforce one scheme, aspect-lock behavior and color defaults in pure helpers. |
| `web/workspace/ui.mjs` | Reusable compact confirmation/error dialog helpers. |
| `tests/editor.test.mjs` | Pure geometry/state and SVG editor behavior tests. |
| `tests/ui-state.test.mjs` | DOM-free workflow-state and version action tests. |
| `README.md` | Replace legacy four-step/multi-file export description with the confirmed internal workflow. |
| `docs/绿色版使用说明.md` | Explain task reopen, version restore and the continuing Inkscape requirement. |

## Interfaces

```javascript
// web/workspace/state.mjs
// activeScheme(project) -> Scheme | null
// validCalibration(project) -> boolean
export function nextPrimaryAction(project) {
  // 'create-task' | 'upload-bag' | 'upload-logo' | 'choose-logo' |
  // 'calibrate' | 'place-logo' | 'export-customer'
}
// canCustomerExport(project) -> boolean
// suggestedFilename(project) -> string

// web/workspace/assets.mjs
export function logoPickerDialog(project, applyCandidateIds) { /* void */ }

// web/workspace/versions.mjs
export async function openVersionsDialog({project, api, adopt, refreshProjects}) { /* void */ }

// web/workspace/persistence.mjs
export const customerExport = (project, filename) =>
  api(projectURL(project.name) + '/customer-export', {
    method: 'POST', body: {revision: project.revision, filename},
  });
export const listVersions = name => api(projectURL(name) + '/versions');
```

### Task 1: Establish the stable three-column shell and natural state selectors

**Files:**
- Modify: `web/index.html`
- Modify: `web/workspace/workspace.css`
- Create: `web/workspace/state.mjs`
- Modify: `web/workspace/main.mjs`
- Create: `tests/ui-state.test.mjs`

**Consumes:** Current `Project` data plus version/count/status metadata from `2026-09-05-task-version-and-customer-export.md`.

**Produces:** A single grid shell with no bottom scheme strip or persistent workflow hint; a tested function decides the one next primary action.

- [ ] **Step 1: Write failing state-selector tests**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {nextPrimaryAction, canCustomerExport} from '../web/workspace/state.mjs';

const readyProject = () => ({
  inputs: {bag_image: 'input/bag.png', logo_source: 'input/source.svg', logo_preview: 'input/clean.png'},
  asset: {selected_candidate_ids: ['page-0001--candidate-1']},
  calibration: {product_frame: {x: 0, y: 0, w: 400, h: 300}, width_mm: 200},
  frames: [{id: 'front', x: 0, y: 0, w: 400, h: 300}],
  schemes: [{id: 'active', frame_id: 'front', size_mm: {w: 50, h: 25}, offset_mm: {left: 20, bottom: 20}, logo_px: {x: 40, y: 210, w: 100, h: 50}}],
});

test('workflow exposes only the next unmet business action', () => {
  assert.equal(nextPrimaryAction(null), 'create-task');
  assert.equal(nextPrimaryAction({inputs: {}, schemes: []}), 'upload-bag');
  assert.equal(nextPrimaryAction({inputs: {bag_image: 'bag.png'}, schemes: []}), 'upload-logo');
  assert.equal(nextPrimaryAction({inputs: {bag_image: 'bag.png', logo_source: 'source.ai'}, schemes: []}), 'choose-logo');
});

test('customer export requires one calibrated active placement', () => {
  assert.equal(canCustomerExport({calibration: {width_mm: 0}, schemes: []}), false);
  assert.equal(canCustomerExport(readyProject()), true);
});
```

- [ ] **Step 2: Run the state tests and verify the module is missing**

Run: `node --test tests/ui-state.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `state.mjs`.

- [ ] **Step 3: Implement state selectors and replace structural HTML**

```javascript
export function activeScheme(project) {
  return project?.schemes?.length === 1 ? project.schemes[0] : null;
}

export function nextPrimaryAction(project) {
  if (!project) return 'create-task';
  if (!project.inputs?.bag_image) return 'upload-bag';
  if (!project.inputs?.logo_source) return 'upload-logo';
  if (!project.asset?.selected_candidate_ids?.length || !project.inputs?.logo_preview) return 'choose-logo';
  if (!validCalibration(project)) return 'calibrate';
  if (!activeScheme(project)) return 'place-logo';
  return 'export-customer';
}

export function validCalibration(project) {
  const frame = project?.calibration?.product_frame;
  return Number.isFinite(project?.calibration?.width_mm) && project.calibration.width_mm > 0 &&
    Number.isFinite(frame?.w) && frame.w > 0 && Number.isFinite(frame?.h) && frame.h > 0;
}

export function suggestedFilename(project) {
  return `${project.name}_效果图.png`;
}
```

In `index.html`, keep one `main.workspace` grid only. Remove `scheme-list`, `add-scheme`, the four persistent “制作提示” lines and the old “导出文件” copy. Keep a compact center toolbar for select, calibration frame, reference frame, undo/redo, clean preview and zoom. Add a left-panel `素材 / 版本记录` tab switch but keep its physical position unchanged.

Update `renderProjects()` so each task row shows `preview_path` as a thumbnail when present, otherwise the existing neutral icon; include formatted `updated_at`, the internal version count and the server-provided status label. Add a compact status selector only inside the selected task's left resource panel, with exact values `编辑中`, `等待反馈` and `已完成`; saving the selection updates `project.status` through the existing `SaveQueue`, never guesses a customer response.

In CSS, retain `grid-template-columns: 240px minmax(410px, 1fr) 280px`; remove rules for the bottom scheme strip; make center panel fill the reclaimed height. At widths below 980px, keep a horizontal minimum width and allow the browser to scroll rather than collapsing/reordering columns.

- [ ] **Step 4: Run state and existing editor tests**

Run: `node --test tests/ui-state.test.mjs tests/editor.test.mjs`

Expected: PASS. The existing geometry tests may be updated only where they still refer to removed multi-scheme UI labels, not geometry behavior.

- [ ] **Step 5: Commit the workbench shell**

```bash
git add web/index.html web/workspace/workspace.css web/workspace/state.mjs web/workspace/main.mjs tests/ui-state.test.mjs tests/editor.test.mjs
git commit -m "feat: establish three-column task workspace"
```

### Task 2: Replace raw-object cleanup with page and candidate selection

**Files:**
- Modify: `web/workspace/assets.mjs`
- Modify: `web/workspace/main.mjs`
- Modify: `web/workspace/workspace.css`
- Modify: `web/workspace/persistence.mjs`
- Test: `tests/ui-state.test.mjs`

**Consumes:** Page/candidate API from `2026-09-05-multipage-logo-import.md`.

**Produces:** A three-column Logo picker: page list left, generic candidate checkboxes/cards center, combined transparent preview and “确认使用” right.

- [ ] **Step 1: Write a failing candidate-selection state test**

```javascript
import {mergeCandidateIds, pickerReady} from '../web/workspace/assets.mjs';

test('candidate selection is page-aware and needs no raw object tools', () => {
  const selected = mergeCandidateIds(new Set(['page-0001--candidate-1']), 'page-0002--candidate-2');
  assert.deepEqual([...selected].sort(), ['page-0001--candidate-1', 'page-0002--candidate-2']);
  assert.equal(pickerReady(selected), true);
  assert.equal(pickerReady(new Set()), false);
});
```

- [ ] **Step 2: Run the picker test and verify the helpers are absent**

Run: `node --test tests/ui-state.test.mjs`

Expected: FAIL because `mergeCandidateIds` and `pickerReady` do not exist.

- [ ] **Step 3: Replace `cleanupDialog()` with `logoPickerDialog()`**

```javascript
export function mergeCandidateIds(selected, candidateId) {
  const next = new Set(selected);
  if (next.has(candidateId)) next.delete(candidateId); else next.add(candidateId);
  return next;
}

export function pickerReady(selected) {
  return selected.size > 0;
}

export function logoPickerDialog(project, applyCandidateIds) {
  // Left: AssetPage buttons in source order, including error state.
  // Center: checkbox card per page.candidates; use generic labels supplied by API.
  // Right: selected-count and a <canvas> composite preview redrawn from the selected candidate preview PNGs on every checkbox change.
  // Submit: applyCandidateIds([...selected]) only; never show object IDs, box selection or group commands.
}
```

Change the mutation payload in `main.mjs` to `{candidate_ids: ids}`. When a page has `error`, render it as a disabled page button with the server error copy and keep other pages selectable. Do not call the old “全选、清空、框选对象、重置建议” controls.

- [ ] **Step 4: Run JS tests and manually inspect one multipage fixture**

Run: `node --test tests/ui-state.test.mjs tests/editor.test.mjs`

Expected: PASS.

Manual check: open a two-page test project; confirm page 2 is reachable; select two cards; click “确认使用”; verify the main left Logo card shows the server-rendered clean preview.

- [ ] **Step 5: Commit the candidate-picker UI**

```bash
git add web/workspace/assets.mjs web/workspace/main.mjs web/workspace/workspace.css web/workspace/persistence.mjs tests/ui-state.test.mjs
git commit -m "feat: select logo candidates by page"
```

### Task 3: One-placement editor with direct manipulation and color modes

**Files:**
- Modify: `web/workspace/geometry.mjs`
- Modify: `web/workspace/editor.mjs`
- Modify: `web/workspace/main.mjs`
- Modify: `web/workspace/workspace.css`
- Test: `tests/editor.test.mjs`

**Consumes:** `Scheme.lock_aspect`, `Scheme.color` and color-aware customer renderer from the version/export plan.

**Produces:** One active Logo placement that can be selected, moved, resized through eight handles, measured in mm, centered and rendered in original/black/white/dark-gray modes.

- [ ] **Step 1: Write failing direct-manipulation tests**

```javascript
import {resizeFromHandle, newScheme} from '../web/workspace/geometry.mjs';

test('corner resize keeps logo aspect when lock is on', () => {
  const next = resizeFromHandle({x:10, y:20, w:100, h:50}, 'se', {x:50, y:20}, 2, true);
  assert.deepEqual(next, {x:10, y:20, w:150, h:75});
});

test('east handle changes only width when aspect lock is off', () => {
  const next = resizeFromHandle({x:10, y:20, w:100, h:50}, 'e', {x:30, y:0}, 2, false);
  assert.deepEqual(next, {x:10, y:20, w:130, h:50});
});

test('new placement is the only active scheme and starts with original color', () => {
  assert.equal(newScheme(fixture(), 'f', 's').color, 'original');
  assert.equal(newScheme(fixture(), 'f', 's').lock_aspect, true);
});
```

- [ ] **Step 2: Run the geometry tests and confirm helpers/fields are absent**

Run: `node --test tests/editor.test.mjs`

Expected: FAIL because `resizeFromHandle()` and the new defaults are absent.

- [ ] **Step 3: Implement eight-handle resize and compact right controls**

```javascript
export function resizeFromHandle(rect, handle, delta, aspect, lockAspect) {
  // Handles: nw, n, ne, e, se, s, sw, w.
  // Move the opposite edge/corner as the anchor.
  // When lockAspect, derive h = w / aspect and recenter the secondary axis for side handles.
  // Clamp w and h to 0.1 before returning.
}
```

Render all eight selected Logo handles in `Editor.rect()`. Route pointer movement through `resizeFromHandle()` instead of its current corner-only calculation. Preserve direct drag for movement and current product/frame/crop geometry behavior.

Remove `duplicateScheme`, `deleteScheme`, new-scheme strip and arbitrary scheme naming from the UI. On completion of calibration/reference-frame setup, create the single active scheme if none exists. If a legacy project has multiple schemes, show a one-time dialog asking which scheme to use; copy that scheme into the draft and retain old legacy exports read-only.

Render a four-button color control in the right panel. Update `scheme.color`, auto-save through the existing `SaveQueue`, and use an SVG image CSS filter only for immediate canvas feedback; the PNG renderer remains the export source of truth. Add a `锁定原始比例` checkbox bound to `scheme.lock_aspect`.

- [ ] **Step 4: Run browser-logic tests and visually exercise editor handles**

Run: `node --test tests/editor.test.mjs tests/ui-state.test.mjs`

Expected: PASS.

Manual check: move the Logo; drag each of four corners; drag east/west with lock off; type a new millimetre width; switch all four colors; reload the task and verify its placement, size, color and lock state persist.

- [ ] **Step 5: Commit placement controls**

```bash
git add web/workspace/geometry.mjs web/workspace/editor.mjs web/workspace/main.mjs web/workspace/workspace.css tests/editor.test.mjs
git commit -m "feat: simplify logo placement controls"
```

### Task 4: Customer export and version-management UI

**Files:**
- Create: `web/workspace/versions.mjs`
- Modify: `web/workspace/persistence.mjs`
- Modify: `web/workspace/main.mjs`
- Modify: `web/workspace/ui.mjs`
- Modify: `web/workspace/workspace.css`
- Test: `tests/ui-state.test.mjs`

**Consumes:** Customer-export and version routes from `2026-09-05-task-version-and-customer-export.md`.

**Produces:** One primary “生成客户确认图” action, an external PNG save flow, and a left-tab version browser with preview, restore and deletion confirmation.

- [ ] **Step 1: Write failing version-view helpers tests**

```javascript
import {versionActionState, formatVersionLabel} from '../web/workspace/versions.mjs';

test('version UI protects read-only legacy records and formats internal labels', () => {
  assert.equal(formatVersionLabel({number: 2, read_only: false}), '第 2 版');
  assert.equal(versionActionState({read_only: true}).canDelete, false);
  assert.equal(versionActionState({read_only: true}).canRestore, true);
  assert.equal(versionActionState({read_only: false}).canDelete, true);
});
```

- [ ] **Step 2: Run the helper test and verify the module is absent**

Run: `node --test tests/ui-state.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `versions.mjs`.

- [ ] **Step 3: Implement export and version flows**

```javascript
export function formatVersionLabel(version) {
  return version.read_only ? '旧版导出' : `第 ${version.number} 版`;
}
export function versionActionState(version) {
  return {canRestore: true, canDelete: !version.read_only};
}

async function exportCustomer() {
  await state.queue.flush();
  const result = await customerExport(state.project, suggestedFilename(state.project));
  if (result.cancelled) return;
  await refresh();
  await openVersionsDialog({project: state.project, api, adopt, refreshProjects: refresh});
}
```

Replace the old multi-checkbox SVG/PDF export dialog. The export preview uses the same clean canvas mode as the output renderer and shows only the numeric mm annotation. The top primary action says “生成客户确认图”.

In `versions.mjs`, fetch versions on tab entry, render selected-version preview in the center pane, and use the right pane for timestamp, width/height, color, “从此版本继续编辑” and “删除此版本”. Before restore, flush `SaveQueue`; send the live `project.revision`; call `adopt()` with the returned draft. Before deletion, show a dialog naming the exact internal version and state that externally delivered files are unaffected.

- [ ] **Step 4: Run JS tests and perform the full feedback loop manually**

Run: `node --test tests/editor.test.mjs tests/ui-state.test.mjs`

Expected: PASS.

Manual check: create/export version 1; close the local app; reopen; open task; select version 1; restore; move the Logo; export version 2; delete version 1; verify version 2 and the externally saved first PNG remain.

- [ ] **Step 5: Commit version workbench integration**

```bash
git add web/workspace/versions.mjs web/workspace/persistence.mjs web/workspace/main.mjs web/workspace/ui.mjs web/workspace/workspace.css tests/ui-state.test.mjs
git commit -m "feat: manage customer confirmation versions"
```

### Task 5: Documentation, end-to-end verification and portable build

**Files:**
- Modify: `README.md`
- Modify: `docs/绿色版使用说明.md`
- Modify: `LogoMock.spec` only if the build requires Tk hidden imports
- Test: `tests/test_projects.py`
- Test: `tests/test_assets.py`
- Test: `tests/test_exports.py`
- Test: `tests/test_versions.py`
- Test: `tests/editor.test.mjs`
- Test: `tests/ui-state.test.mjs`

**Consumes:** All three implementation plans.

**Produces:** A release-ready internal application whose guidance matches the confirmed workflow and whose portable build can use Inkscape installed separately.

- [ ] **Step 1: Update user-facing instructions without adding documentation-only automated tests**

Document this exact path: “新建任务 → 导入产品图 → 导入并确认 Logo → 按现有方式标定 → 调整位置/尺寸/颜色 → 生成客户确认图 → 客户反馈后从版本恢复”。 State that AI/PDF/SVG requires separately installed official Inkscape and that AI must be PDF-compatible. State that a customer export is one PNG and versions are internal.

- [ ] **Step 2: Run the whole automated suite before building**

Run: `python -m pytest tests -q; node --test tests/editor.test.mjs tests/ui-state.test.mjs`

Expected: PASS, with real-Inkscape tests skipped only when Inkscape is not configured.

- [ ] **Step 3: Build the portable application and smoke-launch it in a clean data directory**

Run: `.\build.bat; .\dist\LogoMock.exe --headless --port 8018 --data-dir .\_qa\v2-clean-data`

Expected: build succeeds and `http://127.0.0.1:8018/api/health` reports the local server. If the executable cannot open the save dialog because Tcl/Tk was omitted, add the existing PyInstaller-compatible `collect_data_files('tkinter')`/hidden-import configuration in `LogoMock.spec`, rebuild and repeat the smoke launch.

- [ ] **Step 4: Perform a human visual acceptance pass**

Use a disposable task with a two-page PDF-compatible AI/PDF containing a grouped wordmark, background and dimension label. Verify every confirmed UI state in the design: fixed three columns, page cards, generic labels, one clean Logo, handles, four colors, numeric `W × H mm` output, version restore and internal deletion. Capture only disposable `_qa` evidence; do not alter user projects.

- [ ] **Step 5: Commit release documentation and verification artifacts**

```bash
git add README.md docs/绿色版使用说明.md LogoMock.spec tests
git commit -m "docs: explain internal task workflow"
```
