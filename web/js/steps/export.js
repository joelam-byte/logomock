/**
 * steps/export.js —— 步骤 4：导出（架构文档 B10）。
 *
 * - 左栏：三张交付物卡片（选款图 / 工艺尺寸图 / 定位图）
 * - 中栏：三 Tab 预览（切换显示三份交付物）
 * - 右栏：格式多选（按引擎能力置灰 + 原因）、导出按钮、结果块
 * - 方案条选中态：导出成功后蓝色 → 绿色带对勾（经 state.exportedSchemeIds）
 *
 * 导出结果：绿色汇总（成功）/ 黄色信息条（降级，如引擎缺失跳过 PDF）/ 打开文件夹。
 * 阻断级错误由 api.js 统一弹窗，本文件不重复渲染。
 */
window.steps = window.steps || {};

window.steps.export = (function () {
  'use strict';

  let el = null;          // 左栏面板容器
  let previewEl = null;   // 中栏预览容器
  let settingsEl = null;  // 右栏设置容器
  let engineAvailable = true; // 引擎能力（浅探测）
  let lastResult = null;      // 最近一次导出结果
  let currentTab = 'selection';

  function mount(root) {
    el = root;
    previewEl = document.getElementById('export-preview');
    settingsEl = document.getElementById('export-settings');
    renderLeft();
    renderSettings();
    renderPreviewTabs();
    bindEvents();
    fetchHealth();
    state.subscribe(refresh);
  }

  // ---- 左栏：三张交付物卡片 ----
  function renderLeft() {
    el.innerHTML =
      '<div class="section-title">4 导出</div>' +
      '<div class="hint-box">一次产出 5 个文件：选款图 PNG + 工艺尺寸图 / 定位图各 PDF 与 SVG。</div>' +
      '<div class="export-card' + (currentTab === 'selection' ? ' active' : '') + '" data-tab="selection">' +
        '<div class="export-card-title">客户选款图</div>' +
        '<div class="export-card-desc">selection.png · 客户圈选</div>' +
      '</div>' +
      '<div class="export-card' + (currentTab === 'spec' ? ' active' : '') + '" data-tab="spec">' +
        '<div class="export-card-title">工艺尺寸图</div>' +
        '<div class="export-card-desc">spec.pdf / spec.svg · 1:1 打印可量</div>' +
      '</div>' +
      '<div class="export-card' + (currentTab === 'placement' ? ' active' : '') + '" data-tab="placement">' +
        '<div class="export-card-title">定位图</div>' +
        '<div class="export-card-desc">placement.pdf / placement.svg · 距框边尺寸链</div>' +
      '</div>';
  }

  // ---- 右栏：设置 + 结果块 ----
  function renderSettings() {
    settingsEl.innerHTML =
      '<div class="section-title">导出设置</div>' +
      '<div class="field"><label>输出格式</label>' +
        '<label class="check"><input type="checkbox" id="fmt-pdf" checked> PDF（主交付，转曲）</label>' +
        '<label class="check"><input type="checkbox" id="fmt-svg" checked> SVG（矢量源）</label>' +
        '<div class="field-hint" id="fmt-pdf-reason"></div>' +
      '</div>' +
      '<div class="field">' +
        '<label class="check"><input type="checkbox" id="include-unselected"> 同时导出未选方案</label>' +
      '</div>' +
      '<button class="btn btn-primary btn-block" id="export-btn">导出</button>' +
      '<div id="export-result"></div>';
    applyEngineCapability();
  }

  function applyEngineCapability() {
    const pdf = settingsEl.querySelector('#fmt-pdf');
    const reason = settingsEl.querySelector('#fmt-pdf-reason');
    if (!engineAvailable) {
      pdf.disabled = true;
      pdf.checked = false;
      reason.textContent = 'PDF 需 Inkscape：未检测到引擎，已置灰（SVG + 选款图仍可导出）。';
      reason.className = 'field-hint warn-text';
    } else {
      reason.textContent = '';
    }
  }

  // ---- 中栏：三 Tab 预览 ----
  function renderPreviewTabs() {
    previewEl.innerHTML =
      '<div class="preview-tabs">' +
        '<button class="preview-tab' + (currentTab === 'selection' ? ' active' : '') + '" data-tab="selection">选款图</button>' +
        '<button class="preview-tab' + (currentTab === 'spec' ? ' active' : '') + '" data-tab="spec">工艺尺寸图</button>' +
        '<button class="preview-tab' + (currentTab === 'placement' ? ' active' : '') + '" data-tab="placement">定位图</button>' +
      '</div>' +
      '<div class="preview-body" id="preview-body">' +
        '<div class="preview-empty">尚未导出。点击右栏「导出」后在此预览。</div>' +
      '</div>';
    bindTabClicks();
  }

  function bindTabClicks() {
    previewEl.querySelectorAll('.preview-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        setTab(btn.getAttribute('data-tab'));
      });
    });
  }

  function setTab(tab) {
    currentTab = tab;
    previewEl.querySelectorAll('.preview-tab').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === tab);
    });
    el.querySelectorAll('.export-card').forEach(function (c) {
      c.classList.toggle('active', c.getAttribute('data-tab') === tab);
    });
    if (lastResult) renderPreview(lastResult);
  }

  function bindEvents() {
    el.querySelectorAll('.export-card').forEach(function (card) {
      card.addEventListener('click', function () {
        setTab(card.getAttribute('data-tab'));
      });
    });
    settingsEl.querySelector('#export-btn').addEventListener('click', doExport);
  }

  function fetchHealth() {
    api.get('/api/health').then(function (data) {
      engineAvailable = !!data.available;
      applyEngineCapability();
    }).catch(function () {
      engineAvailable = true; // 探测失败不阻断，交导出时降级处理
    });
  }

  // ---- 导出 ----
  function doExport() {
    const proj = state.get('project');
    const name = state.get('projectName');
    const currentId = state.get('currentSchemeId');
    if (!proj || !name) {
      api.showToast('请先创建项目');
      return;
    }
    if (!currentId) {
      api.showToast('请先在底部方案条选择一个方案');
      return;
    }

    const formats = [];
    if (settingsEl.querySelector('#fmt-pdf').checked) formats.push('pdf');
    if (settingsEl.querySelector('#fmt-svg').checked) formats.push('svg');
    if (!formats.length) {
      api.showToast('至少选择一种输出格式');
      return;
    }

    const payload = {
      scheme_ids: [currentId],
      formats: formats,
      include_unselected: settingsEl.querySelector('#include-unselected').checked,
    };

    const btn = settingsEl.querySelector('#export-btn');
    btn.disabled = true;
    btn.textContent = '导出中…';

    api.post('/api/projects/' + encodeURIComponent(name) + '/export', payload)
      .then(function (res) {
        lastResult = res;
        const exported = (state.get('exportedSchemeIds') || []).slice();
        (res.scheme_ids || []).forEach(function (id) {
          if (exported.indexOf(id) < 0) exported.push(id);
        });
        state.update({ exportedSchemeIds: exported });
        renderResult(res);
        renderPreview(res);
      })
      .catch(function () {
        lastResult = null;
        renderResult(null);
      })
      .then(function () {
        btn.disabled = false;
        btn.textContent = '导出';
      });
  }

  function renderResult(res) {
    const box = settingsEl.querySelector('#export-result');
    if (!res) {
      box.innerHTML = '';
      return;
    }
    const files = res.files || [];
    const skipped = res.skipped || [];
    const warnings = res.warnings || [];

    let html = '';
    if (res.degraded) {
      html += '<div class="warn-box">导出完成（降级）：部分交付物被跳过。';
      html += '<ul class="result-list">' +
        skipped.map(function (s) { return '<li>' + esc(s.file) + '：' + esc(s.reason) + '</li>'; }).join('') +
        '</ul>';
      html += '</div>';
    } else {
      html += '<div class="export-success">导出完成：' + files.length + ' 个文件</div>';
    }
    if (warnings.length) {
      html += warnings.map(function (w) {
        return '<div class="warn-box">' + esc(w.message) + '</div>';
      }).join('');
    }
    html += '<button class="btn btn-block" id="open-folder-btn">打开输出文件夹</button>';
    box.innerHTML = html;

    const openBtn = box.querySelector('#open-folder-btn');
    if (openBtn) {
      openBtn.addEventListener('click', function () {
        api.post('/api/projects/' + encodeURIComponent(state.get('projectName')) + '/open-output', {})
          .catch(function () { /* 已在 api 层提示 */ });
      });
    }
  }

  // ---- 预览 ----
  function renderPreview(res) {
    if (!previewEl) return;
    const files = res.files || [];
    const name = state.get('projectName');
    const body = previewEl.querySelector('#preview-body');
    if (!body) return;

    const kinds = { selection: 'selection', spec: 'spec', placement: 'placement' };
    const kind = kinds[currentTab] || 'selection';

    const png = findFile(files, kind, 'png');
    const svg = findFile(files, kind, 'svg');
    const pdf = findFile(files, kind, 'pdf');

    let html = '';
    if (kind === 'selection' && png) {
      html += imgBlock(png, name, '选款图');
    } else {
      if (svg) html += imgBlock(svg, name, 'SVG 预览');
      if (pdf) html += linkBlock(pdf, name, 'PDF（已转曲）');
      if (!svg && !pdf) html += '<div class="preview-empty">该格式未生成。</div>';
    }

    if (!html) html = '<div class="preview-empty">尚未导出。</div>';
    body.innerHTML = html;
  }

  function imgBlock(rel, name, label) {
    const url = api.fileUrl(name, rel);
    return '<div class="preview-figure">' +
      '<div class="preview-figure-label">' + esc(label) + '</div>' +
      '<img class="preview-img" src="' + esc(url) + '" alt="' + esc(label) + '">' +
      '</div>';
  }

  function linkBlock(rel, name, label) {
    const url = api.fileUrl(name, rel);
    return '<a class="preview-link" href="' + esc(url) + '" target="_blank">' +
      esc(label) + '</a>';
  }

  function findFile(files, kind, ext) {
    const id = state.get('currentSchemeId');
    const base = 'output/' + kind;
    const withSuffix = base + '_' + id + '.' + ext;
    if (files.indexOf(withSuffix) >= 0) return withSuffix;
    const plain = base + '.' + ext;
    if (files.indexOf(plain) >= 0) return plain;
    for (let i = 0; i < files.length; i++) {
      if (files[i].indexOf(base) === 0 && files[i].indexOf('.' + ext) > 0) return files[i];
    }
    return null;
  }

  function refresh(snapshot) {
    if (!el) return;
    // 引擎能力变化时刷新右栏置灰态
    if (snapshot.currentStep === '4' && lastResult) {
      renderPreview(lastResult);
    }
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  return { mount: mount };
})();
