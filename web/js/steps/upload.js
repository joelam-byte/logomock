/**
 * steps/upload.js —— 步骤 1：上传包图与 logo（架构文档 B3）。
 *
 * 交互修复：把原来「隐藏 file input + 一堆 disabled 按钮」改成
 * 明确的分步引导 + 拖拽上传区（dropzone）+ 禁用态给出为什么不能点。
 *
 * 分层不变：只翻译用户操作 → api 调用 → state 变更，不绕过 state。
 */
window.steps = window.steps || {};

window.steps.upload = (function () {
  'use strict';

  let el = null;

  function init(root) {
    el = root;
    el.innerHTML =
      '<div class="section-title">1 · 上传素材</div>' +

      // ---- 第 1 步：创建项目 ----
      '<div class="field">' +
        '<label>第 1 步 · 项目名</label>' +
        '<input type="text" id="project-name-input" placeholder="如 2026-09-03_客户A_双肩包">' +
        '<div class="field-hint">格式「日期_客户_包型」，含中文亦可</div>' +
      '</div>' +
      '<button class="btn btn-primary btn-block" id="create-project-btn">创建项目</button>' +

      // ---- 第 2 步：上传包图 ----
      '<div class="section-title">第 2 步 · 包图（正视图）</div>' +
      '<input type="file" id="bag-file" accept="image/*" style="display:none">' +
      '<div class="dropzone disabled" id="bag-dropzone" tabindex="0">' +
        '<div class="dz-title">上传包图</div>' +
        '<div class="dz-hint">点击选择，或拖入图片文件</div>' +
        '<div class="dz-disabled-hint" id="bag-disabled-hint">⚠ 请先完成第 1 步「创建项目」</div>' +
      '</div>' +
      '<div class="file-status" id="bag-status"></div>' +

      // ---- 第 3 步：上传 logo ----
      '<div class="section-title">第 3 步 · 客户 logo</div>' +
      '<input type="file" id="logo-file" accept=".ai,.pdf,.svg" style="display:none">' +
      '<div class="dropzone disabled" id="logo-dropzone" tabindex="0">' +
        '<div class="dz-title">上传 logo</div>' +
        '<div class="dz-hint">AI / PDF / SVG，点击选择或拖入</div>' +
        '<div class="dz-disabled-hint" id="logo-disabled-hint">⚠ 请先完成第 1 步「创建项目」</div>' +
      '</div>' +
      '<div class="file-status" id="logo-status"></div>' +

      // ---- 第 4 步：转换 ----
      '<div class="section-title">第 4 步 · 转换</div>' +
      '<button class="btn btn-primary btn-block" id="convert-btn" disabled>转换为 logo.svg</button>' +
      '<div class="file-status" id="convert-status"></div>';

    bindEvents();
    refreshDrops();
  }

  function projectName() {
    return state.get('projectName');
  }

  function hasProject() {
    return !!projectName();
  }

  function hasLogoSource() {
    const p = state.get('project');
    return !!(p && p.inputs && p.inputs.logo_source);
  }

  // 更新 dropzone 与按钮的可用态 + 提示文案
  function refreshDrops() {
    const canUpload = hasProject();
    const bagDz = el.querySelector('#bag-dropzone');
    const logoDz = el.querySelector('#logo-dropzone');
    const convertBtn = el.querySelector('#convert-btn');

    updateDropzone(bagDz, canUpload, el.querySelector('#bag-disabled-hint'));
    updateDropzone(logoDz, canUpload, el.querySelector('#logo-disabled-hint'));
    convertBtn.disabled = !(canUpload && hasLogoSource());
  }

  function updateDropzone(dz, enabled, disabledHint) {
    if (!dz) return;
    if (enabled) {
      dz.classList.remove('disabled');
      dz.removeAttribute('disabled');
      dz.setAttribute('tabindex', '0');
      if (disabledHint) disabledHint.style.display = 'none';
    } else {
      dz.classList.add('disabled');
      dz.setAttribute('disabled', 'disabled');
      dz.removeAttribute('tabindex');
      if (disabledHint) disabledHint.style.display = '';
    }
  }

  function bindEvents() {
    // ---- 创建项目 ----
    el.querySelector('#create-project-btn').addEventListener('click', function () {
      const name = el.querySelector('#project-name-input').value.trim();
      if (!name) {
        api.showToast('请输入项目名');
        return;
      }
      api.post('/api/projects', { name: name }).then(function (proj) {
        state.update({ projectName: proj.name, project: proj });
        api.showToast('项目已创建：' + proj.name);
        refreshDrops();
      });
    });

    // ---- 包图上传（dropzone + 拖拽） ----
    bindDropzone('bag-dropzone', 'bag-file', '/upload/bag', 'bag-status', '包图');
    // ---- logo 上传 ----
    bindDropzone('logo-dropzone', 'logo-file', '/upload/logo', 'logo-status', 'logo');

    // ---- 转换 ----
    el.querySelector('#convert-btn').addEventListener('click', function () {
      const status = el.querySelector('#convert-status');
      status.textContent = '转换中…';
      status.className = 'file-status';
      api.post('/api/projects/' + encodeURIComponent(projectName()) + '/convert', {})
        .then(function (proj) {
          state.update({ project: proj });
          status.textContent = '已生成：' + proj.inputs.logo_svg;
          status.className = 'file-status ok';
        })
        .catch(function () {
          status.textContent = '转换失败（详见弹窗）';
          status.className = 'file-status err';
        });
    });
  }

  // 绑定一个 dropzone：点击触发 file input，拖拽支持拖入
  function bindDropzone(dzId, fileId, endpoint, statusId, label) {
    const dz = el.querySelector('#' + dzId);
    const fileInput = el.querySelector('#' + fileId);
    const status = el.querySelector('#' + statusId);

    dz.addEventListener('click', function () {
      if (!hasProject()) {
        api.showToast('请先完成第 1 步「创建项目」');
        return;
      }
      fileInput.click();
    });

    dz.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ' ') && hasProject()) {
        e.preventDefault();
        fileInput.click();
      }
    });

    dz.addEventListener('dragover', function (e) {
      e.preventDefault();
      if (hasProject()) dz.classList.add('dragover');
    });

    dz.addEventListener('dragleave', function () {
      dz.classList.remove('dragover');
    });

    dz.addEventListener('drop', function (e) {
      e.preventDefault();
      dz.classList.remove('dragover');
      if (!hasProject()) {
        api.showToast('请先完成第 1 步「创建项目」');
        return;
      }
      const files = e.dataTransfer.files;
      if (files && files.length) {
        uploadFile(files[0], endpoint, status, label);
      }
    });

    fileInput.addEventListener('change', function (e) {
      const file = e.target.files[0];
      if (!file) return;
      uploadFile(file, endpoint, status, label);
      fileInput.value = ''; // 允许连续选择同一文件
    });
  }

  function uploadFile(file, endpoint, status, label) {
    const url = '/api/projects/' + encodeURIComponent(projectName()) + endpoint;
    status.textContent = '上传中：' + file.name;
    status.className = 'file-status';
    api.upload(url, file)
      .then(function (proj) {
        state.update({ project: proj });
        const saved = endpoint === '/upload/bag' ? proj.inputs.bag_image : proj.inputs.logo_source;
        status.textContent = '已上传：' + saved;
        status.className = 'file-status ok';
        refreshDrops();
      })
      .catch(function () {
        status.textContent = '上传失败：' + file.name;
        status.className = 'file-status err';
      });
  }

  return { init: init, refreshDrops: refreshDrops };
})();
