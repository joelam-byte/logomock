/**
 * schemes.js —— 底部方案条（架构文档 3.2）。
 *
 * 方案增删/切换/复制。点卡片切换；"+"新建；"复制"复制当前方案。
 * 新建仅生成空方案（logo_px 为空），初始摆放由 place.js 在步骤 3 自动完成。
 */
window.schemes = (function () {
  'use strict';

  const IDS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  let el = null;

  function init(root) {
    el = root;
  }

  function render(snapshot) {
    if (!el) return;
    const proj = snapshot.project;
    const schemes = (proj && proj.schemes) || [];
    const currentId = snapshot.currentSchemeId;
    const exported = snapshot.exportedSchemeIds || [];

    let html = '';
    schemes.forEach(function (s) {
      const active = s.id === currentId ? ' active' : '';
      const done = exported.indexOf(s.id) >= 0 ? ' done' : '';
      const check = exported.indexOf(s.id) >= 0 ? '<span class="scheme-check">✓</span>' : '';
      const size = s.size_mm || {};
      const mm = fmtMm(size.w) + ' × ' + fmtMm(size.h) + ' mm';
      html += '<div class="scheme-card' + active + done + '" data-scheme-id="' + esc(s.id) + '">' +
        '<div class="scheme-id">' + esc(s.id) + '</div>' +
        '<div class="scheme-mm">' + esc(mm) + '</div>' +
        check +
        '</div>';
    });

    html += '<button class="scheme-add" data-action="add" title="新建方案">+</button>' +
      '<button class="scheme-copy" data-action="copy" title="复制当前方案"' +
      (currentId ? '' : ' disabled') + '>复制</button>';
    el.innerHTML = html;

    el.querySelectorAll('.scheme-card').forEach(function (card) {
      card.addEventListener('click', function () {
        state.set('currentSchemeId', card.getAttribute('data-scheme-id'));
      });
    });

    const addBtn = el.querySelector('[data-action="add"]');
    if (addBtn) addBtn.addEventListener('click', add);

    const copyBtn = el.querySelector('[data-action="copy"]');
    if (copyBtn) copyBtn.addEventListener('click', duplicate);
  }

  function add() {
    const proj = state.get('project');
    if (!proj) return;
    const frames = proj.frames || [];
    if (!frames.length) {
      api.showToast('请先在 2B 画出 logo 框');
      return;
    }
    const schemes = proj.schemes || [];
    const id = nextId(schemes);
    const scheme = {
      id: id,
      frame_id: frames[0].id,
      logo_px: { x: 0, y: 0, w: 0, h: 0 },
      size_mm: { w: 0, h: 0 },
      offset_mm: { left: 0, bottom: 0 },
      color: null,
    };
    const newProj = Object.assign({}, proj, { schemes: schemes.concat([scheme]) });
    state.update({ project: newProj, currentSchemeId: id });
    api.saveProject(newProj);
  }

  function duplicate() {
    const proj = state.get('project');
    if (!proj) return;
    const schemes = proj.schemes || [];
    const currentId = state.get('currentSchemeId');
    const src = findScheme(schemes, currentId);
    if (!src) {
      api.showToast('请先选择一个方案');
      return;
    }
    const id = nextId(schemes);
    const copy = Object.assign({}, src, {
      id: id,
      logo_px: Object.assign({}, src.logo_px || {}),
      size_mm: Object.assign({}, src.size_mm || {}),
      offset_mm: Object.assign({}, src.offset_mm || {}),
    });
    const newProj = Object.assign({}, proj, { schemes: schemes.concat([copy]) });
    state.update({ project: newProj, currentSchemeId: id });
    api.saveProject(newProj);
  }

  function nextId(schemes) {
    let maxIdx = -1;
    schemes.forEach(function (s) {
      const idx = IDS.indexOf(s.id);
      if (idx > maxIdx) maxIdx = idx;
    });
    const next = maxIdx + 1;
    return next < IDS.length ? IDS[next] : 'S' + (next + 1);
  }

  function findScheme(schemes, id) {
    for (let i = 0; i < schemes.length; i++) {
      if (schemes[i].id === id) return schemes[i];
    }
    return null;
  }

  function fmtMm(v) {
    if (v === undefined || v === null) return '0.0';
    return Number(v).toFixed(1);
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  return { init: init, render: render, add: add, duplicate: duplicate };
})();
