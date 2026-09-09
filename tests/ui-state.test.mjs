import test from 'node:test';
import assert from 'node:assert/strict';
import { nextPrimaryAction, canCustomerExport, suggestedFilename, selectedProjectName, taskActionState } from '../web/workspace/state.mjs';
import { pageSelections, selectionForPage, togglePageCandidate, previewLayout, candidatesIntersecting, candidateAtPoint, clearPageSelection, pickerReady } from '../web/workspace/assets.mjs';
import { formatVersionLabel, versionActionState } from '../web/workspace/versions.mjs';
import * as persistence from '../web/workspace/persistence.mjs';

const readyProject = () => ({
  name: '客户 A',
  inputs: {
    bag_image: 'input/bag.png',
    logo_source: 'input/source.svg',
    logo_preview: 'input/clean.png',
  },
  asset: { selected_candidate_ids: ['page-0001--candidate-1'] },
  calibration: { product_frame: { x: 0, y: 0, w: 400, h: 300 }, width_mm: 200, locked: true },
  frames: [{ id: 'front', x: 0, y: 0, w: 400, h: 300, locked: true }],
  schemes: [{
    id: 'active',
    frame_id: 'front',
    size_mm: { w: 50, h: 25 },
    offset_mm: { left: 20, bottom: 20 },
    logo_px: { x: 40, y: 210, w: 100, h: 50 },
  }],
});

test('workflow exposes only the next unmet business action', () => {
  assert.equal(nextPrimaryAction(null), 'create-task');
  assert.equal(nextPrimaryAction({ inputs: {}, schemes: [] }), 'upload-bag');
  assert.equal(nextPrimaryAction({ inputs: { bag_image: 'bag.png' }, schemes: [] }), 'upload-logo');
  assert.equal(nextPrimaryAction({ inputs: { bag_image: 'bag.png', logo_source: 'source.ai' }, schemes: [] }), 'analyze-logo');
  assert.equal(nextPrimaryAction({ ...readyProject(), calibration: { width_mm: 0 } }), 'calibrate');
  assert.equal(nextPrimaryAction({ ...readyProject(), schemes: [] }), 'place-logo');
  assert.equal(nextPrimaryAction(readyProject()), 'export-customer');
});

test('a calibrated product must be locked before moving on to Logo import', () => {
  const project = {
    inputs: { bag_image: 'input/bag.png' },
    calibration: { product_frame: { x: 20, y: 30, w: 400, h: 300 }, width_mm: 200 },
    frames: [],
    schemes: [],
  };

  assert.equal(nextPrimaryAction(project), 'lock-product');
  project.calibration.locked = true;
  assert.equal(nextPrimaryAction(project), 'upload-logo');
});

test('a created print area must be locked before placing the Logo', () => {
  const project = readyProject();
  project.schemes = [];
  project.calibration.locked = true;
  project.frames[0].locked = false;

  assert.equal(nextPrimaryAction(project), 'lock-frame');
  project.frames[0].locked = true;
  assert.equal(nextPrimaryAction(project), 'place-logo');
});

test('customer export requires one calibrated active placement', () => {
  assert.equal(canCustomerExport({ calibration: { width_mm: 0 }, schemes: [] }), false);
  assert.equal(canCustomerExport(readyProject()), true);
});

test('suggested customer image uses the task name', () => {
  assert.equal(suggestedFilename(readyProject()), '客户 A_效果图.png');
});

test('task selection captures the selected name before asynchronous work starts', () => {
  const event = { currentTarget: { value: '002' } };

  assert.equal(selectedProjectName(event), '002');
});

test('copying and deleting stay unavailable until a task is selected', () => {
  assert.deepEqual(taskActionState(null), { canClone: false, canDelete: false });
  assert.deepEqual(taskActionState(readyProject()), { canClone: true, canDelete: true });
});

test('page selection stays isolated and preview keeps source positions', () => {
  const selections = pageSelections({
    pages: [
      { id: 'page-0001', candidates: [{ id: 'page-0001--candidate-1' }] },
      { id: 'page-0002', candidates: [{ id: 'page-0002--candidate-1' }, { id: 'page-0002--candidate-2' }] },
    ],
    selected_candidate_ids: ['page-0001--candidate-1'],
  });
  const changed = togglePageCandidate(selections, 'page-0002', 'page-0002--candidate-2');

  assert.deepEqual([...selectionForPage(changed, 'page-0001')], ['page-0001--candidate-1']);
  assert.deepEqual([...selectionForPage(changed, 'page-0002')], ['page-0002--candidate-2']);
  const layout = previewLayout([
    { id: 'm', box: { x: 10, y: 30, w: 20, h: 40 } },
    { id: 'e', box: { x: 70, y: 30, w: 20, h: 40 } },
  ], { width: 240, height: 120 });
  assert.equal(layout.items.find(item => item.id === 'm').x, 24);
  assert.equal(layout.items.find(item => item.id === 'e').x, 168);
  assert.equal(pickerReady(selectionForPage(changed, 'page-0002')), true);
  assert.equal(pickerReady(new Set()), false);
});

test('drag selection returns only candidates intersecting the current source rectangle', () => {
  const selected = candidatesIntersecting([
    { id: 'm', box: { x: 10, y: 10, w: 20, h: 30 } },
    { id: 'e', box: { x: 50, y: 10, w: 20, h: 30 } },
    { id: 'dot', box: { x: 150, y: 10, w: 20, h: 30 } },
  ], { x: 5, y: 5, w: 80, h: 40 });

  assert.deepEqual(selected.map(item => item.id), ['m', 'e']);
});

test('thin candidates receive a usable hit area and win over larger overlapping candidates', () => {
  const hit = candidateAtPoint([
    { id: 'logo', box: { x: 0, y: 0, w: 100, h: 60 } },
    { id: 'line', box: { x: 10, y: 30, w: 40, h: 0.6 } },
  ], { x: 30, y: 31 }, 10);

  assert.equal(hit.id, 'line');
});

test('clearing an empty page selection does not affect another page', () => {
  const selections = new Map([
    ['page-0001', new Set(['page-0001--logo'])],
    ['page-0002', new Set(['page-0002--logo'])],
  ]);

  const cleared = clearPageSelection(selections, 'page-0001');

  assert.deepEqual([...selectionForPage(cleared, 'page-0001')], []);
  assert.deepEqual([...selectionForPage(cleared, 'page-0002')], ['page-0002--logo']);
});

test('version UI protects read-only legacy records and formats internal labels', () => {
  assert.equal(formatVersionLabel({ number: 2, read_only: false }), '第 2 版');
  assert.equal(versionActionState({ read_only: true }).canDelete, false);
  assert.equal(versionActionState({ read_only: true }).canRestore, true);
  assert.equal(versionActionState({ read_only: false }).canDelete, true);
});

test('production export asks for the selected frozen version', async () => {
  const originalFetch = globalThis.fetch;
  let request;
  globalThis.fetch = async (path, options) => {
    request = { path, options };
    return { ok: true, json: async () => ({ ok: true, data: { files: ['output/production/version-0001/印刷定位图.png'] } }) };
  };
  try {
    const result = await persistence.productionExport({ name: '客户 A' }, 'version-0001');
    assert.deepEqual(result.files, ['output/production/version-0001/印刷定位图.png']);
    assert.equal(request.path, '/api/projects/%E5%AE%A2%E6%88%B7%20A/versions/version-0001/production-export');
    assert.deepEqual(request.options, { method: 'POST' });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
