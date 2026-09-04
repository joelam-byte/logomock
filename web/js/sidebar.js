/**
 * sidebar.js —— 右侧参数面板，订阅 state 重绘（架构文档 3.2）。
 *
 * 只读 state，不反向写数据。
 */
window.sidebar = (function () {
  'use strict';

  let el = null;

  function init(root) {
    el = root;
  }

  function render(snapshot) {
    if (!el) return;
    const proj = snapshot.project;

    let html = '<div class="section-title">项目状态</div>';
    if (!proj) {
      html += '<div class="file-status">尚未创建项目</div>';
      el.innerHTML = html;
      return;
    }

    const inputs = proj.inputs || {};
    html += '<div class="field"><label>项目名</label>' +
      '<input type="text" value="' + esc(proj.name || '') + '" disabled></div>';

    html += '<div class="field"><label>包图</label>' +
      '<div class="file-status ' + (inputs.bag_image ? 'ok' : '') + '">' +
      (inputs.bag_image ? esc(inputs.bag_image) : '未上传') + '</div></div>';

    html += '<div class="field"><label>logo 源文件</label>' +
      '<div class="file-status ' + (inputs.logo_source ? 'ok' : '') + '">' +
      (inputs.logo_source ? esc(inputs.logo_source) : '未上传') + '</div></div>';

    html += '<div class="field"><label>logo.svg（转换结果）</label>' +
      '<div class="file-status ' + (inputs.logo_svg ? 'ok' : '') + '">' +
      (inputs.logo_svg ? esc(inputs.logo_svg) : '未转换') + '</div></div>';

    const calib = proj.calibration || {};
    html += '<div class="section-title">标定</div>';
    html += '<div class="field"><label>比例尺 px_per_mm</label>' +
      '<input type="number" value="' + (calib.px_per_mm || 0) + '" disabled></div>';

    html += '<div class="section-title">logo 框（' + (proj.frames || []).length + '）</div>';
    html += '<div class="section-title">方案（' + (proj.schemes || []).length + '）</div>';

    el.innerHTML = html;
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  return { init: init, render: render };
})();
