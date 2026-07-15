/* 导出模块 */

const ExportModule = (function () {
  var _pollTimer = null;

  function openExportPanel() {
    var projectId = App.getCurrentProjectId();
    if (!projectId) {
      Utils.toast("请先选择项目", "warning");
      return;
    }
    App.switchView("export");
  }

  async function triggerExport(exportType) {
    var projectId = App.getCurrentProjectId();
    if (!projectId) {
      Utils.toast("请先选择项目", "warning");
      return;
    }

    var progressDiv = document.getElementById("export-progress");
    var progressFill = document.getElementById("export-progress-fill");
    var statusText = document.getElementById("export-status-text");
    progressDiv.style.display = "block";
    progressFill.style.width = "10%";
    statusText.textContent = "正在生成导出文件...";

    try {
      var res = await API.exports.trigger(projectId, { type: exportType });
      if (res.error) {
        Utils.toast(res.message, "error");
        progressDiv.style.display = "none";
        return;
      }

      var exportId = res.data.export_id;
      progressFill.style.width = "30%";
      statusText.textContent = "处理中...";
      pollExportStatus(projectId, exportId, progressFill, statusText);
    } catch (e) {
      Utils.toast("导出失败: " + e.message, "error");
      progressDiv.style.display = "none";
    }
  }

  function pollExportStatus(projectId, exportId, progressFill, statusText) {
    if (_pollTimer) clearInterval(_pollTimer);
    var progress = 30;

    _pollTimer = setInterval(async function () {
      try {
        var res = await API.exports.status(projectId, exportId);
        if (res.error) {
          clearInterval(_pollTimer);
          Utils.toast("查询导出状态失败", "error");
          return;
        }

        var task = res.data;
        if (task.status === "completed") {
          clearInterval(_pollTimer);
          progressFill.style.width = "100%";
          statusText.textContent = "导出完成，正在下载...";
          setTimeout(async function () {
            try {
              await API.exports.download(projectId, exportId);
              Utils.toast("导出文件下载完成", "success");
            } catch (e) {
              Utils.toast("下载失败: " + e.message, "error");
            }
            setTimeout(function () {
              document.getElementById("export-progress").style.display = "none";
            }, 2000);
          }, 500);
        } else if (task.status === "failed") {
          clearInterval(_pollTimer);
          progressFill.style.width = "100%";
          progressFill.style.background = "#C62828";
          statusText.textContent = "导出失败: " + (task.error || "未知错误");
        } else {
          progress = Math.min(progress + 5 + Math.random() * 10, 90);
          progressFill.style.width = progress + "%";
          statusText.textContent = "正在处理... " + Math.round(progress) + "%";
        }
      } catch (e) {
        clearInterval(_pollTimer);
        Utils.toast("状态查询异常: " + e.message, "error");
      }
    }, 2000);
  }

  /**
   * 导出KMZ文件（带照片，给奥维地图用）
   */
  function exportKMZ() {
    var projectId = App.getCurrentProjectId();
    if (!projectId) {
      Utils.toast("请先选择项目", "warning");
      return;
    }

    Utils.toast("正在生成KMZ...", "info");
    var url = "/api/projects/" + projectId + "/export-kmz";
    var a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function() {
      Utils.toast('KMZ已导出！奥维菜单: 系统 -> 导入对象', "success");
    }, 1000);
  }

  // ===== 导出目录管理（按类型分开） =====

  var _exportDirs = {};

  async function loadExportDir() {
    try {
      var res = await fetch("/api/projects/export-dir");
      var data = await res.json();
      if (!data.error) {
        _exportDirs = data.data;
        updateDirDisplay();
      }
    } catch(e) {}
  }

  function updateDirDisplay() {
    var labels = { kmz: "导出到奥维", summary: "汇总表", individual: "记录表" };
    Object.keys(labels).forEach(function(key) {
      var btn = document.getElementById("btn-dir-" + key);
      if (btn) {
        btn.title = _exportDirs[key] ? "当前: " + _exportDirs[key] : "未设置(默认目录)";
      }
    });
  }

  async function setExportDir(etype, title) {
    var current = _exportDirs[etype] || "";
    var bodyHtml = `
      <div class="form-group">
        <label>${title} - 导出目录</label>
        <div style="display:flex;gap:8px;">
          <input type="text" id="modal-export-path" class="form-control"
                 value="${Utils.escapeHtml(current)}" placeholder="点击右侧浏览选择文件夹" style="flex:1;">
          <button class="btn btn-primary" id="modal-btn-pick-folder">📁 浏览...</button>
        </div>
      </div>
    `;
    var footerHtml = `
      <button class="btn" onclick="Utils.closeModal()">取消</button>
      <button class="btn" onclick="document.getElementById('modal-export-path').value='';document.getElementById('modal-btn-export-dir').click();">恢复默认</button>
      <button class="btn btn-primary" id="modal-btn-export-dir">保存</button>
    `;

    Utils.showModal("设置导出目录 - " + title, bodyHtml, footerHtml);

    document.getElementById("modal-btn-pick-folder").addEventListener("click", async function () {
      try {
        var resp = await fetch("/api/projects/pick-folder");
        var data = await resp.json();
        if (!data.error && data.data.path) {
          document.getElementById("modal-export-path").value = data.data.path;
        }
      } catch(e) {}
    });

    document.getElementById("modal-btn-export-dir").addEventListener("click", async function () {
      var path = document.getElementById("modal-export-path").value.trim();
      try {
        var resp = await fetch("/api/projects/export-dir", {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({path: path, type: etype})
        });
        var data = await resp.json();
        if (data.error) { Utils.toast(data.message, "warning"); return; }
        _exportDirs[etype] = path || "";
        updateDirDisplay();
        Utils.closeModal();
        Utils.toast(data.message || "已保存", "success");
      } catch(e) { Utils.toast("设置失败", "error"); }
    });
  }

  async function openExportDir() {
    try {
      await fetch("/api/projects/open-export-dir", {method: "POST"});
    } catch(e) {
      Utils.toast("无法打开目录", "warning");
    }
  }

  function initEvents() {
    document.getElementById("btn-export").addEventListener("click", function() {
      loadExportDir();
      openExportPanel();
    });
    document.getElementById("btn-export-csv").addEventListener("click", exportKMZ);

    document.getElementById("btn-set-export-dir").addEventListener("click", function() {
      setExportDir("all", "通用");
    });
    document.getElementById("btn-dir-kmz").addEventListener("click", function() {
      setExportDir("kmz", "导出到奥维");
    });
    document.getElementById("btn-open-export-dir").addEventListener("click", openExportDir);

    document.querySelectorAll(".export-trigger").forEach(function (btn) {
      btn.addEventListener("click", function () {
        triggerExport(this.dataset.type);
      });
    });

    loadExportDir();
  }

  return {
    openExportPanel: openExportPanel,
    triggerExport: triggerExport,
    exportKMZ: exportKMZ,
    initEvents: initEvents,
  };
})();
