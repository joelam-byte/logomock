/**
 * main.js —— 启动装配：初始化 state、挂载步骤、订阅渲染（架构文档 B0/B4/B5-B7）。
 *
 * 步骤切换统一走 app.goStep(step)：先跑守卫（guard），通过才改 currentStep。
 * 步骤面板在启动时一次性挂载，切换仅控制显示/隐藏，避免输入框丢值。
 */
(function () {
  'use strict';

  const STEP_TOOL = {
    '1': 'none',
    '2a': 'product-rect',
    '2b': 'logo-rect',
    '3': 'place',
    '4': 'none',
  };

  const panels = {};

  function render(snapshot) {
    canvas.render(snapshot);
    sidebar.render(snapshot);
    schemes.render(snapshot);
  }

  // 进入某步骤的前置校验，返回错误文案或 null
  function guard(step) {
    const proj = state.get('project');
    if (step === '1') return null;

    if (step === '2a') {
      if (!proj || !proj.inputs || !proj.inputs.bag_image) {
        return '请先在步骤 1 创建项目并上传包图';
      }
      return null;
    }

    if (step === '2b') {
      if (!proj) return '请先创建项目';
      const calib = proj.calibration || {};
      const pf = calib.product_frame || {};
      if (!calib.width_mm || calib.width_mm <= 0) {
        return '阻断(#1)：请先填写实物宽度(mm)';
      }
      if (!pf.w || pf.w <= 0 || !pf.h || pf.h <= 0) {
        return '阻断(#2)：产品框面积为零，请重新拖框';
      }
      return null;
    }

    if (step === '3') {
      if (!proj) return '请先创建项目';
      if (!proj.inputs || !proj.inputs.logo_svg) {
        return '请先在步骤 1 上传并转换 logo';
      }
      if (!proj.frames || proj.frames.length === 0) {
        return '请先在 2B 画出 logo 框';
      }
      return null;
    }

    if (step === '4') {
      if (!proj) return '请先创建项目';
      if (!proj.inputs || !proj.inputs.logo_svg) {
        return '请先在步骤 1 上传并转换 logo';
      }
      if (!proj.inputs.bag_image) {
        return '请先上传包图';
      }
      if (!proj.schemes || proj.schemes.length === 0) {
        return '请先在步骤 3 摆放并生成至少一个方案';
      }
      return null;
    }

    return null;
  }

  function goStep(step) {
    const msg = guard(step);
    if (msg) {
      api.showToast(msg);
      return;
    }
    // 进入步骤 3 时若尚无方案，先自动建一个
    if (step === '3') {
      const proj = state.get('project');
      if (proj && (!proj.schemes || proj.schemes.length === 0)) {
        schemes.add();
      }
    }
    state.set('currentStep', step);
  }

  // 只读地应用步骤视图：高亮步骤条、切换面板、切换画布工具、切换中/右栏视图
  function applyStepView(step) {
    document.querySelectorAll('.step').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-step') === step);
    });
    Object.keys(panels).forEach(function (id) {
      panels[id].style.display = id === step ? 'block' : 'none';
    });
    canvas.setTool(STEP_TOOL[step] || 'none');

    // 步骤 4：中栏切到导出预览，右栏切到导出设置；否则显示画布 + 侧栏
    const isExport = step === '4';
    document.getElementById('export-preview').style.display = isExport ? 'flex' : 'none';
    document.getElementById('export-settings').style.display = isExport ? 'block' : 'none';
    document.getElementById('sidebar-content').style.display = isExport ? 'none' : '';
    document.getElementById('main-canvas').style.display = isExport ? 'none' : '';
    document.getElementById('canvas-placeholder').style.display = isExport ? 'none' : '';
  }

  function boot() {
    canvas.init(document.getElementById('main-canvas'));
    sidebar.init(document.getElementById('sidebar-content'));
    schemes.init(document.getElementById('scheme-bar'));

    // 左栏：为每个步骤建独立面板容器，一次性挂载
    const left = document.getElementById('left-panel');
    ['1', '2a', '2b', '3', '4'].forEach(function (id) {
      const div = document.createElement('div');
      div.className = 'step-panel';
      div.setAttribute('data-step-panel', id);
      left.appendChild(div);
      panels[id] = div;
    });

    steps.upload.init(panels['1']);
    steps.calibProduct.mount(panels['2a']);
    steps.calibLogo.mount(panels['2b']);
    steps.place.mount(panels['3']);
    steps.export.mount(panels['4']);

    // 步骤条点击 → 统一走守卫
    document.querySelectorAll('.step').forEach(function (btn) {
      btn.addEventListener('click', function () {
        goStep(btn.getAttribute('data-step'));
      });
    });

    // 订阅：state 变更 → Canvas / 侧边栏 / 方案条同步刷新
    state.subscribe(render);

    // 订阅：步骤视图（高亮 + 面板 + 画布工具）
    state.subscribe(function (snapshot) {
      applyStepView(snapshot.currentStep);
    });

    // 订阅：包图 URL 变化 → 加载进 Canvas（渲染资源加载，非业务状态）
    let lastBagImage = null;
    state.subscribe(function (snapshot) {
      const proj = snapshot.project;
      const rel = proj && proj.inputs ? proj.inputs.bag_image : null;
      const url = rel && snapshot.projectName
        ? api.fileUrl(snapshot.projectName, rel)
        : null;
      if (url === lastBagImage) return;
      lastBagImage = url;
      if (url) {
        canvas.loadImage(url).then(function () {
          state.update({ bagImageReady: true });
        }).catch(function (err) {
          state.update({ bagImageReady: false });
          api.showToast(err.message);
        });
      } else {
        state.update({ bagImageReady: false });
      }
    });

    // 订阅：logo.svg 变化 → 加载进 Canvas
    let lastLogo = null;
    state.subscribe(function (snapshot) {
      const proj = snapshot.project;
      const rel = proj && proj.inputs ? proj.inputs.logo_svg : null;
      const url = rel && snapshot.projectName
        ? api.fileUrl(snapshot.projectName, rel)
        : null;
      if (url === lastLogo) return;
      lastLogo = url;
      if (url) {
        canvas.loadLogo(url).then(function () {
          state.update({ logoReady: true });
        }).catch(function (err) {
          state.update({ logoReady: false });
          api.showToast(err.message);
        });
      } else {
        state.update({ logoReady: false });
      }
    });

    // 订阅：项目名显示
    state.subscribe(function (snapshot) {
      document.getElementById('project-name').textContent =
        snapshot.projectName || '未创建项目';
    });

    // 初始渲染
    state.emit();
  }

  window.app = { goStep: goStep };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
