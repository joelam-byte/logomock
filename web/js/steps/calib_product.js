/**
 * steps/calib_product.js —— 步骤 2A：产品框定比例尺（架构文档 B5）。
 *
 * 拖框 → 填实物宽度 → px_per_mm = 框宽px ÷ 宽度mm 写入 state。
 * 阻断：#1 宽度为空、#2 产品框零面积（无法进 2B）；
 * 提示：#3 高度偏差 >2%（三种成因）、#4 px_per_mm 超出经验区间 0.5～20。
 *
 * mm 换算只发生在这里与 place.js，均以 px ÷ px_per_mm 计算，无其他换算点。
 */
window.steps = window.steps || {};

window.steps.calibProduct = (function () {
  'use strict';

  const PX_PER_MM_MIN = 0.5;
  const PX_PER_MM_MAX = 20;
  const HEIGHT_DEV_PCT = 2;

  let el = null;

  function mount(root) {
    el = root;
    el.innerHTML =
      '<div class="section-title">2A 产品框（定比例尺）</div>' +
      '<div class="hint-box">只框包主体：提手 / 肩带 / 织带不计入。拖框后填写实物宽度。</div>' +
      '<div class="field">' +
        '<label>实物宽度 mm（必填）</label>' +
        '<input type="number" id="calib-width" min="0" step="0.1" placeholder="如 300">' +
      '</div>' +
      '<div class="field">' +
        '<label>实物高度 mm（选填，仅作提示）</label>' +
        '<input type="number" id="calib-height" min="0" step="0.1" placeholder="如 450">' +
      '</div>' +
      '<div class="field">' +
        '<label>比例尺 px_per_mm</label>' +
        '<div class="readonly-value" id="calib-ppm">—</div>' +
      '</div>' +
      '<div class="field" id="calib-computed-height-field" style="display:none">' +
        '<label>推算高度 mm（按宽度定标）</label>' +
        '<div class="readonly-value" id="calib-computed-height">—</div>' +
      '</div>' +
      '<div id="calib-warnings"></div>' +
      '<button class="btn btn-primary btn-block" id="calib-next">保存标定并进入 2B</button>';

    bindEvents();
  }

  function bindEvents() {
    el.querySelector('#calib-width').addEventListener('input', refreshLive);
    el.querySelector('#calib-width').addEventListener('change', commit);
    el.querySelector('#calib-height').addEventListener('input', refreshLive);
    el.querySelector('#calib-height').addEventListener('change', commit);
    el.querySelector('#calib-next').addEventListener('click', onNext);

    // 画布拖出产品框 → 写入 state（canvas 仅上报像素矩形）
    canvas.on('product-rect-drawn', function (r) {
      const proj = state.get('project');
      if (!proj) return;
      const calib = Object.assign({}, proj.calibration || {}, { product_frame: r });
      const newProj = Object.assign({}, proj, { calibration: calib });
      state.update({ project: newProj });
      api.saveProject(newProj);
      refreshLive();
    });
  }

  // 实时预览：读输入框即时值（不写 state），产品框读 state
  function refreshLive() {
    if (!el) return;
    const proj = state.get('project');
    const calib = (proj && proj.calibration) || {};
    const pf = calib.product_frame || {};
    const width = parseNum(el.querySelector('#calib-width').value);
    const height = parseOpt(el.querySelector('#calib-height').value);

    const ppm = (width > 0 && pf.w > 0) ? pf.w / width : 0;
    el.querySelector('#calib-ppm').textContent = ppm > 0 ? ppm.toFixed(4) : '—';

    const computedHeight = (ppm > 0 && pf.h > 0) ? pf.h / ppm : null;
    const hf = el.querySelector('#calib-computed-height-field');
    if (height !== null && computedHeight !== null) {
      hf.style.display = '';
      el.querySelector('#calib-computed-height').textContent = computedHeight.toFixed(1);
    } else {
      hf.style.display = 'none';
    }

    const warns = [];
    if (height !== null && computedHeight !== null && height > 0) {
      const dev = Math.abs(computedHeight - height) / height * 100;
      if (dev > HEIGHT_DEV_PCT) {
        warns.push('高度偏差 ' + dev.toFixed(1) + '%（>2%）。可能成因：①软包高度塌陷/填充不同（可忽略）②产品框画得不准（需重画）③拍摄有透视、非等比例（需换图/重拍）。');
      }
    }
    if (ppm > 0 && (ppm < PX_PER_MM_MIN || ppm > PX_PER_MM_MAX)) {
      warns.push('px_per_mm = ' + ppm.toFixed(3) + '，超出经验区间 ' + PX_PER_MM_MIN + '～' + PX_PER_MM_MAX + '，请检查宽度单位是否填错（mm / cm 混淆）。');
    }
    el.querySelector('#calib-warnings').innerHTML = warns.map(function (w) {
      return '<div class="warn-box">' + esc(w) + '</div>';
    }).join('');
  }

  // 提交：把输入写入 state 并保存
  function commit() {
    const proj = state.get('project');
    if (!proj) return;
    const calib = Object.assign({}, proj.calibration || {});
    calib.width_mm = parseNum(el.querySelector('#calib-width').value);
    calib.height_mm = parseOpt(el.querySelector('#calib-height').value);
    const pf = calib.product_frame || {};
    calib.px_per_mm = (calib.width_mm > 0 && pf.w > 0) ? pf.w / calib.width_mm : 0;
    const newProj = Object.assign({}, proj, { calibration: calib });
    state.update({ project: newProj });
    api.saveProject(newProj);
    refreshLive();
  }

  function onNext() {
    commit();
    app.goStep('2b');
  }

  function parseNum(str) {
    const s = String(str).trim();
    return s === '' ? 0 : (parseFloat(s) || 0);
  }

  function parseOpt(str) {
    const s = String(str).trim();
    return s === '' ? null : (parseFloat(s) || null);
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  return { mount: mount };
})();
