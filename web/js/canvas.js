/**
 * canvas.js —— 唯一 Canvas 层（架构文档 3.2）。
 *
 * 只绘制与交互，通过回调上报，**零业务状态**。
 * 铁律：全文不得出现 `state.xxx = ` 形式的业务状态赋值。
 *
 * 拖拽瞬时变量（drag、currentSnapshot 等）不属于业务状态，允许存在，
 * 但必须在 mouseup 时一次性通过回调提交（'product-rect-drawn' / 'logo-rect-drawn' / 'logo-placed'）。
 *
 * 坐标约定：Canvas 一律用图片原始像素坐标（非显示缩放坐标），
 * 显示缩放只在绘制时由 CSS 应用，鼠标坐标在进入交互时换算回原始像素。
 */
window.canvas = (function () {
  'use strict';

  const MIN_LOGO_SIZE = 10; // 最小 logo 尺寸（原始像素）
  const HANDLE_SIZE = 12;   // 四角控制点半边长（原始像素）

  let canvasEl = null;
  let ctx = null;
  let bagImage = null;        // 包图（渲染资源）
  let logoImage = null;       // logo SVG 图（渲染资源）
  let tool = 'none';          // none | product-rect | logo-rect | place
  let currentSnapshot = null; // 渲染输入缓存（非业务状态，每次 render 覆盖）
  let drag = null;            // 拖拽瞬时变量（非业务状态）
  const handlers = {};        // 交互回调

  // ---- 初始化 ----
  function init(el) {
    canvasEl = el;
    ctx = el.getContext('2d');
    canvasEl.addEventListener('mousedown', onMouseDown);
    canvasEl.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }

  function loadImage(url) {
    return new Promise(function (resolve, reject) {
      const img = new Image();
      img.onload = function () { bagImage = img; resolve(img); };
      img.onerror = function () { reject(new Error('图片加载失败：' + url)); };
      img.src = url;
    });
  }

  function loadLogo(url) {
    return new Promise(function (resolve, reject) {
      const img = new Image();
      img.onload = function () { logoImage = img; resolve(img); };
      img.onerror = function () { reject(new Error('logo 加载失败：' + url)); };
      img.src = url;
    });
  }

  function setTool(t) { tool = t || 'none'; }

  function on(event, handler) { handlers[event] = handler; }

  function emit(event, payload) {
    if (handlers[event]) handlers[event](payload);
  }

  function getLogoAspect() {
    if (!logoImage || !logoImage.naturalWidth || !logoImage.naturalHeight) return null;
    return logoImage.naturalWidth / logoImage.naturalHeight;
  }

  function hasImage() { return bagImage !== null; }

  // ---- 绘制 ----
  function render(snapshot) {
    currentSnapshot = snapshot;
    draw();
  }

  function draw() {
    if (!canvasEl || !ctx) return;
    if (!bagImage) {
      canvasEl.classList.remove('has-image');
      return;
    }
    canvasEl.width = bagImage.naturalWidth;
    canvasEl.height = bagImage.naturalHeight;
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    ctx.drawImage(bagImage, 0, 0);
    canvasEl.classList.add('has-image');

    const snap = currentSnapshot;
    if (!snap || !snap.project) return;
    const calib = snap.project.calibration || {};
    const frames = snap.project.frames || [];
    const schemes = snap.project.schemes || [];

    // 产品框
    if (calib.product_frame && calib.product_frame.w > 0 && calib.product_frame.h > 0) {
      strokeRect(calib.product_frame, '#22a06b', 2, [8, 5], '产品框');
    }

    // logo 框
    frames.forEach(function (f) {
      if (f.w > 0 && f.h > 0) {
        strokeRect(f, '#2f6fed', 2, [6, 4], f.name || f.id);
      }
    });

    // 当前方案 logo
    const scheme = currentScheme();
    if (scheme && logoImage && scheme.logo_px && scheme.logo_px.w > 0 && scheme.logo_px.h > 0) {
      drawLogo(scheme.logo_px);
    }

    // 拖拽中的临时预览矩形
    if (drag && drag.preview) {
      strokeRect(drag.preview, '#9aa5b1', 2, [4, 4], null);
    }
  }

  function strokeRect(r, color, width, dash, label) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.setLineDash(dash);
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    ctx.setLineDash([]);
    if (label) {
      ctx.fillStyle = color;
      ctx.font = '15px sans-serif';
      ctx.fillText(label, r.x, Math.max(r.y - 6, 12));
    }
  }

  function drawLogo(r) {
    ctx.drawImage(logoImage, r.x, r.y, r.w, r.h);
    ctx.strokeStyle = '#e24b4a';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    ctx.setLineDash([]);
    drawHandles(r);
  }

  function drawHandles(r) {
    const pts = corners(r);
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#e24b4a';
    ctx.lineWidth = 1.5;
    pts.forEach(function (p) {
      ctx.beginPath();
      ctx.rect(p.x - HANDLE_SIZE / 2, p.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
      ctx.fill();
      ctx.stroke();
    });
  }

  function corners(r) {
    return [
      { x: r.x, y: r.y },                       // tl
      { x: r.x + r.w, y: r.y },                 // tr
      { x: r.x, y: r.y + r.h },                 // bl
      { x: r.x + r.w, y: r.y + r.h },           // br
    ];
  }

  // ---- 快照读取（只读渲染输入，非业务状态） ----
  function currentScheme() {
    const snap = currentSnapshot;
    if (!snap || !snap.project) return null;
    const schemes = snap.project.schemes || [];
    for (let i = 0; i < schemes.length; i++) {
      if (schemes[i].id === snap.currentSchemeId) return schemes[i];
    }
    return null;
  }

  function currentFrame(scheme) {
    const snap = currentSnapshot;
    if (!snap || !snap.project || !scheme) return null;
    const frames = snap.project.frames || [];
    for (let i = 0; i < frames.length; i++) {
      if (frames[i].id === scheme.frame_id) return frames[i];
    }
    return null;
  }

  // ---- 坐标换算：显示坐标 → 原始像素 ----
  function toImageCoords(evt) {
    const rect = canvasEl.getBoundingClientRect();
    if (!rect.width || !rect.height) return { x: 0, y: 0 };
    return {
      x: (evt.clientX - rect.left) * canvasEl.width / rect.width,
      y: (evt.clientY - rect.top) * canvasEl.height / rect.height,
    };
  }

  // ---- 鼠标交互 ----
  function onMouseDown(evt) {
    if (!bagImage || tool === 'none') return;
    const p = toImageCoords(evt);

    if (tool === 'product-rect' || tool === 'logo-rect') {
      drag = { mode: 'rect', startX: p.x, startY: p.y, curX: p.x, curY: p.y, preview: null };
    } else if (tool === 'place') {
      const scheme = currentScheme();
      if (!scheme || !scheme.logo_px || !scheme.logo_px.w) return;
      const r = scheme.logo_px;
      const corner = hitCorner(p, r);
      if (corner) {
        drag = {
          mode: 'resize', corner: corner,
          anchor: anchorOf(corner, r),
          startW: r.w, startH: r.h,
          preview: null,
        };
      } else if (inRect(p, r)) {
        drag = { mode: 'move', startX: p.x, startY: p.y, origX: r.x, origY: r.y, preview: null };
      }
    }
  }

  function onMouseMove(evt) {
    if (!drag) return;
    const p = toImageCoords(evt);

    if (drag.mode === 'rect') {
      drag.curX = p.x;
      drag.curY = p.y;
      drag.preview = normalizeRect(drag.startX, drag.startY, p.x, p.y);
    } else if (drag.mode === 'move') {
      const scheme = currentScheme();
      const frame = currentFrame(scheme);
      const w = scheme.logo_px.w;
      const h = scheme.logo_px.h;
      let nx = drag.origX + (p.x - drag.startX);
      let ny = drag.origY + (p.y - drag.startY);
      if (frame) {
        nx = clamp(nx, frame.x, frame.x + frame.w - w);
        ny = clamp(ny, frame.y, frame.y + frame.h - h);
      }
      drag.preview = { x: nx, y: ny, w: w, h: h };
    } else if (drag.mode === 'resize') {
      const scheme = currentScheme();
      const frame = currentFrame(scheme);
      const dx = p.x - drag.anchor.x;
      const dy = p.y - drag.anchor.y;
      // 锁长宽比：取横纵两个方向缩放量的较大者（可缩小也可放大）
      let scale = Math.max(Math.abs(dx) / drag.startW, Math.abs(dy) / drag.startH);
      // 最小尺寸下限，同时保持长宽比（不把某一维单独钳到 MIN，避免破坏比例）
      scale = Math.max(scale, MIN_LOGO_SIZE / drag.startW, MIN_LOGO_SIZE / drag.startH);
      // 物理夹在框内：放大时以框的宽高为上限（#6）
      if (frame) {
        const maxScale = Math.min(frame.w / drag.startW, frame.h / drag.startH);
        scale = Math.min(scale, maxScale);
      }
      const newW = drag.startW * scale;
      const newH = drag.startH * scale;
      let nx;
      let ny;
      if (drag.corner === 'br') { nx = drag.anchor.x; ny = drag.anchor.y; }
      else if (drag.corner === 'tl') { nx = drag.anchor.x - newW; ny = drag.anchor.y - newH; }
      else if (drag.corner === 'tr') { nx = drag.anchor.x; ny = drag.anchor.y - newH; }
      else { nx = drag.anchor.x - newW; ny = drag.anchor.y; } // bl
      if (frame) {
        nx = clamp(nx, frame.x, frame.x + frame.w - newW);
        ny = clamp(ny, frame.y, frame.y + frame.h - newH);
      }
      drag.preview = { x: nx, y: ny, w: newW, h: newH };
    }

    draw();
  }

  function onMouseUp() {
    if (!drag) return;
    const d = drag;
    drag = null;

    if (d.mode === 'rect') {
      const r = normalizeRect(d.startX, d.startY, d.curX, d.curY);
      if (r.w > 0 && r.h > 0) {
        emit(tool === 'product-rect' ? 'product-rect-drawn' : 'logo-rect-drawn', r);
      }
    } else if (d.mode === 'move' || d.mode === 'resize') {
      if (d.preview && d.preview.w > 0 && d.preview.h > 0) {
        emit('logo-placed', d.preview);
      }
    }
    draw();
  }

  // ---- 命中检测 ----
  function hitCorner(p, r) {
    const names = ['tl', 'tr', 'bl', 'br'];
    const pts = corners(r);
    for (let i = 0; i < pts.length; i++) {
      if (Math.abs(p.x - pts[i].x) <= HANDLE_SIZE && Math.abs(p.y - pts[i].y) <= HANDLE_SIZE) {
        return names[i];
      }
    }
    return null;
  }

  function inRect(p, r) {
    return p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h;
  }

  function anchorOf(corner, r) {
    if (corner === 'br') return { x: r.x, y: r.y };               // 对角 = 左上
    if (corner === 'tl') return { x: r.x + r.w, y: r.y + r.h };   // 对角 = 右下
    if (corner === 'tr') return { x: r.x, y: r.y + r.h };         // 对角 = 左下
    return { x: r.x + r.w, y: r.y };                              // bl 对角 = 右上
  }

  function normalizeRect(x1, y1, x2, y2) {
    return {
      x: Math.min(x1, x2),
      y: Math.min(y1, y2),
      w: Math.abs(x2 - x1),
      h: Math.abs(y2 - y1),
    };
  }

  function clamp(v, lo, hi) {
    if (hi < lo) return lo;
    return Math.min(Math.max(v, lo), hi);
  }

  return {
    init: init,
    loadImage: loadImage,
    loadLogo: loadLogo,
    setTool: setTool,
    on: on,
    render: render,
    getLogoAspect: getLogoAspect,
    hasImage: hasImage,
  };
})();
