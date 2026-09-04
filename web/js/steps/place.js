/**
 * steps/place.js —— 步骤 3：摆放（架构文档 B7）。
 *
 * - logo 物理夹在框内（#6）、四角缩放锁长宽比且有最小尺寸（#7）——已由 canvas.js 保证；
 *   本文件负责在交互结束（'logo-placed' 回调）那一刻算 mm 并写入 scheme。
 * - size_mm / offset_mm 只在交互结束算：mm = px ÷ px_per_mm，round(x, 2) 后存 state。
 * - offset_mm.left  = logo 左边到框左沿；offset_mm.bottom = logo 下边到框下沿。
 * - 色号选填，留空不阻断；方案切换/复制后数值各自独立（schemes.js 负责增删复制）。
 */
window.steps = window.steps || {};

window.steps.place = (function () {
  'use strict';

  let el = null;

  function mount(root) {
    el = root;
    el.innerHTML =
      '<div class="section-title">3 摆放</div>' +
      '<div class="hint-box">拖动移动 logo，四角控制点缩放（锁长宽比）。logo 被夹在 logo 框内。</div>' +
      '<div class="field"><label>当前方案</label><div class="readonly-value" id="place-scheme">—</div></div>' +
      '<div class="field"><label>logo 框</label><div class="readonly-value" id="place-frame">—</div></div>' +
      '<div class="field"><label>宽 (mm)</label><div class="readonly-value" id="place-w">—</div></div>' +
      '<div class="field"><label>高 (mm)</label><div class="readonly-value" id="place-h">—</div></div>' +
      '<div class="field"><label>距框左沿 (mm)</label><div class="readonly-value" id="place-left">—</div></div>' +
      '<div class="field"><label>距框下沿 (mm)</label><div class="readonly-value" id="place-bottom">—</div></div>' +
      '<div class="field">' +
        '<label>色号（选填，留空则不标注）</label>' +
        '<input type="text" id="place-color" placeholder="如 PANTONE 186 C">' +
      '</div>' +
      '<button class="btn btn-block" id="place-duplicate">复制当前方案</button>';

    bindEvents();
    state.subscribe(refresh);
  }

  function bindEvents() {
    // canvas 交互结束一次性上报像素矩形 → 本处算 mm 并落库
    canvas.on('logo-placed', onLogoPlaced);

    el.querySelector('#place-color').addEventListener('change', function () {
      const proj = state.get('project');
      const scheme = currentScheme(proj);
      if (!proj || !scheme) return;
      const raw = el.querySelector('#place-color').value.trim();
      const newScheme = Object.assign({}, scheme, { color: raw === '' ? null : raw });
      replaceScheme(proj, newScheme);
    });

    el.querySelector('#place-duplicate').addEventListener('click', function () {
      schemes.duplicate();
    });
  }

  // ---- 交互结束：算 mm 并写入 scheme ----
  function onLogoPlaced(rect) {
    const proj = state.get('project');
    const scheme = currentScheme(proj);
    if (!proj || !scheme) return;
    const ppm = (proj.calibration && proj.calibration.px_per_mm) || 0;
    const frame = findFrame(proj.frames || [], scheme.frame_id);
    const logo_px = { x: rect.x, y: rect.y, w: rect.w, h: rect.h };

    if (!frame || ppm <= 0) {
      // 无框或无比例尺：仅更新像素位置，不写 mm
      replaceScheme(proj, Object.assign({}, scheme, { logo_px: logo_px }));
      return;
    }

    const size_mm = { w: round2(rect.w / ppm), h: round2(rect.h / ppm) };
    const offset_mm = {
      left: round2((rect.x - frame.x) / ppm),
      bottom: round2((frame.y + frame.h - (rect.y + rect.h)) / ppm),
    };
    replaceScheme(proj, Object.assign({}, scheme, {
      logo_px: logo_px,
      size_mm: size_mm,
      offset_mm: offset_mm,
    }));
  }

  // ---- 当前方案为空（logo_px.w=0）时，自动居中放置并算 mm ----
  function maybeInitCurrentScheme(proj) {
    const scheme = currentScheme(proj);
    if (!scheme) return;
    if (scheme.logo_px && scheme.logo_px.w > 0) return;
    const frame = findFrame(proj.frames || [], scheme.frame_id);
    if (!frame) return;
    const ppm = (proj.calibration && proj.calibration.px_per_mm) || 0;
    if (ppm <= 0) return;
    const aspect = canvas.getLogoAspect();
    if (!aspect) return; // logo 尚未加载，等加载后由 refresh 再触发

    let w = frame.w * 0.5;
    let h = w / aspect;
    if (h > frame.h * 0.8) { h = frame.h * 0.8; w = h * aspect; }
    if (w > frame.w) { w = frame.w; h = w / aspect; }
    if (h > frame.h) { h = frame.h; w = h * aspect; }
    const x = frame.x + (frame.w - w) / 2;
    const y = frame.y + (frame.h - h) / 2;

    const size_mm = { w: round2(w / ppm), h: round2(h / ppm) };
    const offset_mm = {
      left: round2((x - frame.x) / ppm),
      bottom: round2((frame.y + frame.h - (y + h)) / ppm),
    };
    replaceScheme(proj, Object.assign({}, scheme, {
      logo_px: { x: x, y: y, w: w, h: h },
      size_mm: size_mm,
      offset_mm: offset_mm,
    }));
  }

  function refresh(snapshot) {
    if (!el) return;
    const proj = snapshot.project;
    if (!proj) return;

    // 仅在步骤 3 时自动初始化当前方案（空 logo_px → 居中放置）
    if (snapshot.currentStep === '3') {
      maybeInitCurrentScheme(proj);
    }

    const scheme = currentScheme(proj);
    const frame = findFrame(proj.frames || [], scheme ? scheme.frame_id : null);
    el.querySelector('#place-scheme').textContent = scheme ? scheme.id : '—';
    el.querySelector('#place-frame').textContent = frame ? (frame.name || frame.id) : '—';
    const size = (scheme && scheme.size_mm) || {};
    const off = (scheme && scheme.offset_mm) || {};
    el.querySelector('#place-w').textContent = fmt(size.w);
    el.querySelector('#place-h').textContent = fmt(size.h);
    el.querySelector('#place-left').textContent = fmt(off.left);
    el.querySelector('#place-bottom').textContent = fmt(off.bottom);

    const colorInput = el.querySelector('#place-color');
    if (document.activeElement !== colorInput) {
      colorInput.value = (scheme && scheme.color) || '';
    }
  }

  // ---- 工具 ----
  function currentScheme(proj) {
    const id = state.get('currentSchemeId');
    const schemes = proj.schemes || [];
    for (let i = 0; i < schemes.length; i++) {
      if (schemes[i].id === id) return schemes[i];
    }
    return null;
  }

  function findFrame(frames, id) {
    for (let i = 0; i < frames.length; i++) {
      if (frames[i].id === id) return frames[i];
    }
    return null;
  }

  function replaceScheme(proj, newScheme) {
    const schemes = (proj.schemes || []).map(function (s) {
      return s.id === newScheme.id ? newScheme : s;
    });
    const newProj = Object.assign({}, proj, { schemes: schemes });
    state.update({ project: newProj });
    api.saveProject(newProj);
  }

  function round2(x) {
    return Math.round(x * 100) / 100;
  }

  function fmt(v) {
    if (v === undefined || v === null) return '—';
    return Number(v).toFixed(2);
  }

  return { mount: mount };
})();
