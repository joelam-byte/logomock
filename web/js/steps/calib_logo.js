/**
 * steps/calib_logo.js —— 步骤 2B：logo 框定基准（架构文档 B6）。
 *
 * 可建多个命名框；框超出产品框时黄色提示、允许继续（#5）；数据写入 frames[]。
 * 框命名选填；每条边须落在包身肉眼可辨的物理特征上（UI 明示）。
 */
window.steps = window.steps || {};

window.steps.calibLogo = (function () {
  'use strict';

  let el = null;
  let selectedId = null; // 选中的框 id（瞬态 UI 状态，非业务状态）

  function mount(root) {
    el = root;
    el.innerHTML =
      '<div class="section-title">2B logo 框（定基准 + 安全区）</div>' +
      '<div class="hint-box">每条边必须落在包身肉眼可辨的物理特征上（翻盖边 / 前袋边 / 缝线）。</div>' +
      '<div class="field">' +
        '<label>框命名（选填，先填再拖框即生效）</label>' +
        '<input type="text" id="logo-frame-name" placeholder="如 翻盖可印区">' +
      '</div>' +
      '<button class="btn btn-primary btn-block" id="logo-frame-new">新建 logo 框</button>' +
      '<div class="field">' +
        '<label>已有框（点选后可改命名 / 删除）</label>' +
        '<div class="frame-list" id="logo-frame-list"></div>' +
      '</div>' +
      '<button class="btn btn-block" id="logo-frame-delete">删除选中框</button>' +
      '<div id="logo-frame-warnings"></div>' +
      '<button class="btn btn-primary btn-block" id="logo-frame-next">完成并进入 3 摆放</button>';

    bindEvents();
    state.subscribe(refresh);
  }

  function bindEvents() {
    canvas.on('logo-rect-drawn', onFrameDrawn);

    el.querySelector('#logo-frame-new').addEventListener('click', function () {
      canvas.setTool('logo-rect');
      api.showToast('请在画布上拖出 logo 框');
    });

    el.querySelector('#logo-frame-name').addEventListener('change', function () {
      const proj = state.get('project');
      if (!proj || !selectedId) return;
      const name = el.querySelector('#logo-frame-name').value.trim();
      const frames = (proj.frames || []).map(function (f) {
        return f.id === selectedId ? Object.assign({}, f, { name: name }) : f;
      });
      const newProj = Object.assign({}, proj, { frames: frames });
      state.update({ project: newProj });
      api.saveProject(newProj);
    });

    el.querySelector('#logo-frame-delete').addEventListener('click', function () {
      const proj = state.get('project');
      if (!proj || !selectedId) {
        api.showToast('请先选择一个框');
        return;
      }
      const referenced = (proj.schemes || []).some(function (s) {
        return s.frame_id === selectedId;
      });
      if (referenced) {
        api.showToast('该框已被方案引用，无法删除');
        return;
      }
      const frames = (proj.frames || []).filter(function (f) {
        return f.id !== selectedId;
      });
      const newProj = Object.assign({}, proj, { frames: frames });
      selectedId = null;
      state.update({ project: newProj });
      api.saveProject(newProj);
    });

    el.querySelector('#logo-frame-next').addEventListener('click', function () {
      app.goStep('3');
    });
  }

  // 画布拖出 logo 框 → 新建 frame（canvas 仅上报像素矩形）
  function onFrameDrawn(r) {
    const proj = state.get('project');
    if (!proj) return;
    const frames = proj.frames || [];
    const nameInput = el.querySelector('#logo-frame-name');
    const name = nameInput.value.trim() || ('可印区' + (frames.length + 1));
    const frame = {
      id: nextFrameId(frames),
      name: name,
      x: r.x, y: r.y, w: r.w, h: r.h,
    };
    const newProj = Object.assign({}, proj, { frames: frames.concat([frame]) });
    selectedId = frame.id;
    state.update({ project: newProj });
    api.saveProject(newProj);
    // 绘制结束回到无工具态，避免连续误画；再点"新建 logo 框"可继续
    canvas.setTool('none');
  }

  function refresh(snapshot) {
    if (!el) return;
    const proj = snapshot.project;
    if (!proj) return;
    const frames = proj.frames || [];
    const pf = (proj.calibration && proj.calibration.product_frame) || null;

    // 帧列表
    const list = el.querySelector('#logo-frame-list');
    let html = '';
    frames.forEach(function (f) {
      const sel = f.id === selectedId ? ' selected' : '';
      html += '<div class="frame-item' + sel + '" data-frame-id="' + esc(f.id) + '">' +
        esc(f.name || f.id) + '</div>';
    });
    if (!frames.length) {
      html = '<div class="field-hint">尚未创建框，点上方"新建 logo 框"拖画。</div>';
    }
    list.innerHTML = html;

    list.querySelectorAll('.frame-item').forEach(function (item) {
      item.addEventListener('click', function () {
        selectedId = item.getAttribute('data-frame-id');
        const f = findFrame(frames, selectedId);
        if (f) el.querySelector('#logo-frame-name').value = f.name || '';
        refresh(state.get());
      });
    });

    // 超出产品框警告（#5）：只提示，允许继续
    const warns = [];
    frames.forEach(function (f) {
      const w = outsideWarning(f, pf);
      if (w) warns.push((f.name || f.id) + '：' + w);
    });
    el.querySelector('#logo-frame-warnings').innerHTML = warns.map(function (w) {
      return '<div class="warn-box">' + esc(w) + '</div>';
    }).join('');
  }

  function outsideWarning(f, pf) {
    if (!pf || !pf.w || !pf.h) return null;
    const inside =
      f.x >= pf.x &&
      f.y >= pf.y &&
      f.x + f.w <= pf.x + pf.w &&
      f.y + f.h <= pf.y + pf.h;
    if (inside) return null;
    return '该框超出产品框范围（#5 提示）。可印区可能确实略超出测量范围，已允许继续。';
  }

  function nextFrameId(frames) {
    let max = 0;
    frames.forEach(function (f) {
      const m = /^f(\d+)$/.exec(f.id);
      if (m) max = Math.max(max, parseInt(m[1], 10));
    });
    return 'f' + (max + 1);
  }

  function findFrame(frames, id) {
    for (let i = 0; i < frames.length; i++) {
      if (frames[i].id === id) return frames[i];
    }
    return null;
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  return { mount: mount };
})();
