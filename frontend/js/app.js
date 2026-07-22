/* 应用主入口：状态管理、视图路由、初始化 */

const App = (function () {
  // ===== 全局状态 =====
  const state = {
    currentProject: null,
    currentView: "welcome",
  };

  // ===== 视图切换 =====
  function switchView(viewName) {
    state.currentView = viewName;

    // 隐藏所有视图
    document.querySelectorAll(".view").forEach(function (v) {
      v.style.display = "none";
      v.classList.remove("active");
    });

    // 显示目标视图
    const target = document.getElementById("view-" + viewName);
    if (target) {
      target.style.display = "block";
      target.classList.add("active");
    }

    // 调查视图特殊处理：显示左侧表单和右侧照片
    if (viewName === "survey") {
      document.getElementById("view-survey").style.display = "block";
    }
  }

  // ===== 项目管理 =====

  function getCurrentProjectId() {
    return state.currentProject ? state.currentProject.id : null;
  }

  function getCurrentProject() {
    return state.currentProject;
  }

  async function loadProjects() {
    try {
      const res = await API.projects.list();
      if (!res.error) {
        renderProjectSelector(res.data);
      }
    } catch (e) {
      Utils.toast("加载项目列表失败", "error");
    }
  }

  function renderProjectSelector(projects) {
    const selector = document.getElementById("project-selector");
    // 保留第一个选项
    selector.innerHTML = '<option value="">-- 选择项目 --</option>';

    projects.forEach(function (p) {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name;
      if (state.currentProject && state.currentProject.id === p.id) {
        opt.selected = true;
      }
      selector.appendChild(opt);
    });
  }

  async function selectProject(projectId) {
    if (!projectId) {
      state.currentProject = null;
      switchView("welcome");
      document.getElementById("point-list-container").innerHTML =
        '<div class="empty-hint">请先选择项目</div>';
      document.getElementById("welcome-stats").style.display = "none";
      document.getElementById("btn-delete-project").style.display = "none";
      return;
    }

    try {
      const res = await API.projects.get(projectId);
      if (res.error) {
        Utils.toast(res.message, "error");
        return;
      }

      state.currentProject = res.data;
      document.getElementById("btn-delete-project").style.display = "inline-flex";
      await refreshCurrentProject();
      switchView("welcome");
      SurveyPointList.refresh();
    } catch (e) {
      Utils.toast("加载项目失败: " + e.message, "error");
    }
  }

  async function refreshCurrentProject() {
    if (!state.currentProject) return;

    try {
      const res = await API.projects.get(state.currentProject.id);
      if (!res.error) {
        state.currentProject = res.data;
        updateWelcomeStats();
      }
    } catch (e) {
      console.warn("刷新项目信息失败", e);
    }
  }

  function updateWelcomeStats() {
    const p = state.currentProject;
    if (!p) return;

    document.getElementById("welcome-stats").style.display = "block";
    document.getElementById("stat-total").textContent = p.point_count || 0;
    document.getElementById("stat-surveyed").textContent = p.surveyed_count || 0;

    // 获取详细统计
    API.points.stats(p.id).then(function (res) {
      if (!res.error) {
        document.getElementById("stat-pending").textContent = res.data.pending || 0;
        document.getElementById("stat-progress").textContent = res.data.in_progress || 0;
      }
    }).catch(function () {});
  }

  // ===== 新建项目 =====
  async function createNewProject() {
    const bodyHtml = `
      <div class="form-group">
        <label>项目名称 <span class="required">*</span></label>
        <input type="text" id="modal-project-name" class="form-control" placeholder="输入项目名称">
      </div>
      <div class="form-group">
        <label>项目描述</label>
        <textarea id="modal-project-desc" class="form-control" rows="3" placeholder="可选项目描述"></textarea>
      </div>
      <div class="form-group">
        <label>CAD坐标系 <small style="color:#999;">（自动转为WGS84经纬度）</small></label>
        <select id="modal-project-crs" class="form-control">
          <option value="EPSG:4544">CGCS2000 3度带 108E（重庆/贵州/广西）</option>
          <option value="EPSG:4543">CGCS2000 3度带 105E（四川/云南）</option>
          <option value="EPSG:4545">CGCS2000 3度带 111E（湖南/湖北/广东）</option>
          <option value="EPSG:4509">CGCS2000 6度带 19（108-114E）</option>
          <option value="EPSG:4508">CGCS2000 6度带 18（102-108E）</option>
          <option value="EPSG:32648">WGS84 UTM 48N</option>
          <option value="EPSG:32649">WGS84 UTM 49N</option>
          <option value="EPSG:32650">WGS84 UTM 50N</option>
        </select>
      </div>
    `;
    const footerHtml = `
      <button class="btn" onclick="Utils.closeModal()">取消</button>
      <button class="btn btn-primary" id="modal-btn-create">创建</button>
    `;

    Utils.showModal("新建项目", bodyHtml, footerHtml);

    document.getElementById("modal-btn-create").addEventListener("click", async function () {
      const name = document.getElementById("modal-project-name").value.trim();
      if (!name) {
        Utils.toast("请输入项目名称", "warning");
        return;
      }

      try {
        const res = await API.projects.create({
          name: name,
          description: document.getElementById("modal-project-desc").value.trim(),
          coord_system: document.getElementById("modal-project-crs").value,
        });
        if (!res.error) {
          Utils.closeModal();
          Utils.toast("项目创建成功", "success");
          await loadProjects();
          await selectProject(res.data.id);
        }
      } catch (e) {
        Utils.toast("创建失败: " + e.message, "error");
      }
    });

    // 回车提交
    document.getElementById("modal-project-name").addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        document.getElementById("modal-btn-create").click();
      }
    });
  }

  // ===== 删除项目 =====
  async function deleteCurrentProject() {
    if (!state.currentProject) {
      Utils.toast("请先选择项目", "warning");
      return;
    }

    const projectName = state.currentProject.name;
    const confirmed = await Utils.confirm(
      `确认删除项目 "${projectName}"？<br><br>
      <strong style="color:red;">此操作不可恢复！</strong><br>
      将同时删除该项目下的所有标注、调查记录和照片。`
    );
    if (!confirmed) return;

    try {
      await API.projects.delete(state.currentProject.id);
      Utils.toast(`项目 "${projectName}" 已删除`, "success");
      state.currentProject = null;
      document.getElementById("btn-delete-project").style.display = "none";
      document.getElementById("welcome-stats").style.display = "none";
      document.getElementById("point-list-container").innerHTML =
        '<div class="empty-hint">请先选择项目</div>';
      switchView("welcome");
      await loadProjects();
    } catch (e) {
      Utils.toast("删除失败: " + e.message, "error");
    }
  }

  // ===== 事件绑定 =====
  function bindEvents() {
    // 项目选择器
    document.getElementById("project-selector").addEventListener("change", function () {
      selectProject(this.value ? parseInt(this.value) : null);
    });

    // 新建项目
    document.getElementById("btn-new-project").addEventListener("click", createNewProject);

    // 删除项目
    document.getElementById("btn-delete-project").addEventListener("click", deleteCurrentProject);

    // 统一工程名称
    document.getElementById("btn-batch-name").addEventListener("click", function () {
      if (!state.currentProject) {
        Utils.toast("请先选择项目", "warning");
        return;
      }

      var names = window._cachedProjectNames || [];
      var optionsHtml = names.map(function (n) {
        return '<option value="' + Utils.escapeHtml(n) + '">' + Utils.escapeHtml(n) + '</option>';
      }).join("");

      var bodyHtml = `
        <div class="form-group">
          <label>工程名称</label>
          <input type="text" id="modal-batch-name" class="form-control"
                 placeholder="输入工程名称" list="batch-name-list"
                 value="${Utils.escapeHtml(state.currentProject.name || '')}">
          <datalist id="batch-name-list">${optionsHtml}</datalist>
        </div>
        <p style="color:#999;font-size:12px;">将把此项目下所有调查点的"工程名称"统一设置为该值</p>
      `;
      var footerHtml = `
        <button class="btn" onclick="Utils.closeModal()">取消</button>
        <button class="btn btn-primary" id="modal-btn-batch-name">统一设置</button>
      `;

      Utils.showModal("统一工程名称", bodyHtml, footerHtml);

      document.getElementById("modal-btn-batch-name").addEventListener("click", async function () {
        var name = document.getElementById("modal-batch-name").value.trim();
        if (!name) { Utils.toast("请输入工程名称", "warning"); return; }
        try {
          var res = await API.points.batchProjectName(state.currentProject.id, name);
          if (!res.error) {
            Utils.closeModal();
            Utils.toast(res.message, "success");
            SurveyPointList.refresh();
          }
        } catch (e) {
          Utils.toast("设置失败: " + e.message, "error");
        }
      });

      document.getElementById("modal-batch-name").addEventListener("keydown", function (e) {
        if (e.key === "Enter") document.getElementById("modal-btn-batch-name").click();
      });
    });

    // 统一调查人
    document.getElementById("btn-batch-inv").addEventListener("click", function () {
      if (!state.currentProject) {
        Utils.toast("请先选择项目", "warning");
        return;
      }
      var lastInv = "";
      try { lastInv = localStorage.getItem("ovital_last_investigator") || ""; } catch(e) {}

      var bodyHtml = `
        <div class="form-group">
          <label>调查人</label>
          <input type="text" id="modal-batch-inv" class="form-control"
                 placeholder="输入调查人姓名" value="${Utils.escapeHtml(lastInv)}">
        </div>
        <p style="color:#999;font-size:12px;">将把此项目下所有调查点的"调查人"统一设置为该值</p>
      `;
      var footerHtml = `
        <button class="btn" onclick="Utils.closeModal()">取消</button>
        <button class="btn btn-primary" id="modal-btn-batch-inv">统一设置</button>
      `;

      Utils.showModal("统一调查人", bodyHtml, footerHtml);

      document.getElementById("modal-btn-batch-inv").addEventListener("click", async function () {
        var name = document.getElementById("modal-batch-inv").value.trim();
        if (!name) { Utils.toast("请输入调查人", "warning"); return; }
        try {
          var res = await API.points.batchInvestigator(state.currentProject.id, name);
          if (!res.error) {
            Utils.closeModal();
            Utils.toast(res.message, "success");
            try { localStorage.setItem("ovital_last_investigator", name); } catch(e) {}
          }
        } catch (e) {
          Utils.toast("设置失败: " + e.message, "error");
        }
      });
    });

    // 检查更新
    document.getElementById("btn-check-update").addEventListener("click", async function () {
      Utils.toast("正在检查更新...", "info");
      try {
        var res = await (await fetch("/api/check-update")).json();
        if (res.has_update) {
          Utils.toast("发现新版本 v" + res.latest + "（当前 v" + res.current + "），正在下载...", "info");
          // 触发下载更新
          var dlRes = await fetch("/api/do-update", { method: "POST" });
          var dlData = await dlRes.json();
          if (!dlData.error) {
            Utils.toast("更新已下载！程序将自动重启", "success");
          }
        } else {
          Utils.toast("已是最新版本 v" + res.current, "success");
        }
      } catch (e) {
        Utils.toast("检查更新失败：无法连接更新服务器", "warning");
      }
    });

    // 导入CAD
    document.getElementById("btn-import-cad").addEventListener("click", function () {
      if (!state.currentProject) {
        Utils.toast("请先选择项目", "warning");
        return;
      }
      CadImport.importCad(state.currentProject.id);
    });

    // 各模块事件初始化
    CadImport.initEvents();
    SurveyPointList.initEvents();
    SurveyForm.initEvents();
    PhotoManager.initEvents();
    ExportModule.initEvents();

    // 点击调查点列表项 -> 切换到调查视图
    document.getElementById("point-list-container").addEventListener("click", function (e) {
      const item = e.target.closest(".point-item");
      if (item) {
        switchView("survey");
      }
    });
  }

  // ===== 初始化 =====
  async function init() {
    console.log("[App] 正在初始化奥维CAD转换插件...");

    // 初始化奥维SDK
    OvitalSDK.init();

    // 加载项目列表
    await loadProjects();

    // 绑定事件
    bindEvents();

    // 检查URL参数是否有项目ID
    const urlParams = new URLSearchParams(window.location.search);
    const pid = urlParams.get("project_id");
    if (pid) {
      await selectProject(parseInt(pid));
    }

    console.log("[App] 初始化完成。SDK可用:", OvitalSDK.isAvailable());
    Utils.toast("奥维CAD转换插件已就绪", "info", 2000);
  }

  // DOM加载完成后初始化
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return {
    switchView,
    getCurrentProjectId,
    getCurrentProject,
    loadProjects,
    selectProject,
    refreshCurrentProject,
    createNewProject,
  };
})();
