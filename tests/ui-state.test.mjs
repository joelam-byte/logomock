import test from 'node:test';
import assert from 'node:assert/strict';
import { nextPrimaryAction, canCustomerExport, suggestedFilename } from '../web/workspace/state.mjs';
import { mergeCandidateIds, pickerReady } from '../web/workspace/assets.mjs';
import { formatVersionLabel, versionActionState } from '../web/workspace/versions.mjs';

const readyProject = () => ({
  name: '客户 A',
  inputs: {
    bag_image: 'input/bag.png',
    logo_source: 'input/source.svg',
    logo_preview: 'input/clean.png',
  },
  asset: { selected_candidate_ids: ['page-0001--candidate-1'] },
  calibration: { product_frame: { x: 0, y: 0, w: 400, h: 300 }, width_mm: 200 },
  frames: [{ id: 'front', x: 0, y: 0, w: 400, h: 300 }],
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
  assert.equal(nextPrimaryAction({ inputs: { bag_image: 'bag.png', logo_source: 'source.ai' }, schemes: [] }), 'choose-logo');
  assert.equal(nextPrimaryAction({ ...readyProject(), calibration: { width_mm: 0 } }), 'calibrate');
  assert.equal(nextPrimaryAction({ ...readyProject(), schemes: [] }), 'place-logo');
  assert.equal(nextPrimaryAction(readyProject()), 'export-customer');
});

test('customer export requires one calibrated active placement', () => {
  assert.equal(canCustomerExport({ calibration: { width_mm: 0 }, schemes: [] }), false);
  assert.equal(canCustomerExport(readyProject()), true);
});

test('suggested customer image uses the task name', () => {
  assert.equal(suggestedFilename(readyProject()), '客户 A_效果图.png');
});

test('candidate selection is page-aware and needs no raw object tools', () => {
  const selected = mergeCandidateIds(new Set(['page-0001--candidate-1']), 'page-0002--candidate-2');
  assert.deepEqual([...selected].sort(), ['page-0001--candidate-1', 'page-0002--candidate-2']);
  assert.equal(pickerReady(selected), true);
  assert.equal(pickerReady(new Set()), false);
});

test('version UI protects read-only legacy records and formats internal labels', () => {
  assert.equal(formatVersionLabel({ number: 2, read_only: false }), '第 2 版');
  assert.equal(versionActionState({ read_only: true }).canDelete, false);
  assert.equal(versionActionState({ read_only: true }).canRestore, true);
  assert.equal(versionActionState({ read_only: false }).canDelete, true);
});
