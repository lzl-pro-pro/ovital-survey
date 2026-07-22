/* 调查点列表模块 */

const SurveyPointList = (function () {
  let _points = [];
  let _selectedPointId = null;

  /**
   * 刷新调查点列表
   */
  async function refresh(status) {
    const projectId = App.getCurrentProjectId();
    if (!projectId) {
      document.getElementById("point-list-container").innerHTML =
        '<div class="empty-hint">请先选择项目</div>';
      return;
    }

    status = status || document.getElementById("status-filter").value;

    try {
      const res = await API.points.list(projectId, {
        status: status || undefined,
        per_page: 5000,
      });
      if (!res.error) {
        _points = res.data.items;
        render();
        updateStats();
      }
    } catch (e) {
      Utils.toast("加载调查点失败: " + e.message, "error");
    }
  }

  /**
   * 渲染调查点列表
   */
  function render() {
    const container = document.getElementById("point-list-container");
    const searchText = (
      document.getElementById("search-input").value || ""
    ).toLowerCase();

    let filtered = _points;
    if (searchText) {
      filtered = _points.filter(function (p) {
        return (p.point_number || "").toLowerCase().indexOf(searchText) >= 0;
      });
    }

    if (filtered.length === 0) {
      container.innerHTML =
        '<div class="empty-hint">暂无调查点<br><small>请先导入CAD并确认标注</small></div>';
      return;
    }

    container.innerHTML = "";
    filtered.forEach(function (point) {
      const div = document.createElement("div");
      div.className =
        "point-item" +
        (_selectedPointId === point.id ? " active" : "");
      div.dataset.id = point.id;

      div.innerHTML = `
        <span class="point-status status-${point.status}"></span>
        <span class="point-number">${Utils.escapeHtml(point.point_number || "-")}</span>
        <span class="point-meta">${point.photo_count || 0}张</span>
      `;

      div.addEventListener("click", function () {
        selectPoint(point.id);
      });

      // 右键菜单
      div.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        showContextMenu(e.clientX, e.clientY, point);
      });

      container.appendChild(div);
    });
  }

  /**
   * 选中调查点
   */
  async function selectPoint(pointId) {
    _selectedPointId = pointId;
    render();

    // 加载详情
    const projectId = App.getCurrentProjectId();
    try {
      const res = await API.points.get(projectId, pointId);
      if (!res.error) {
        SurveyForm.render(res.data);
        PhotoManager.render(res.data.photos || [], projectId, pointId);

        // 导航到该点
        if (res.data.latitude && res.data.longitude) {
          MapHelper.navigateTo(res.data.latitude, res.data.longitude);
        }
      }
    } catch (e) {
      Utils.toast("加载调查点详情失败: " + e.message, "error");
    }
  }

  /**
   * 右键菜单
   */
  function showContextMenu(x, y, point) {
    const items = [];

    if (point.status !== "surveyed") {
      items.push({
        label: "✅ 标记为已完成",
        action: async function () {
          await API.points.update(App.getCurrentProjectId(), point.id, {
            status: "surveyed",
          });
          Utils.toast("已标记为完成", "success");
          refresh();
        },
      });
    }
    if (point.status !== "skipped") {
      items.push({
        label: "⏭ 标记为跳过",
        action: async function () {
          await API.points.update(App.getCurrentProjectId(), point.id, {
            status: "skipped",
          });
          Utils.toast("已跳过", "info");
          refresh();
        },
      });
    }
    if (point.status !== "pending") {
      items.push({
        label: "🔄 重置为待调查",
        action: async function () {
          await API.points.update(App.getCurrentProjectId(), point.id, {
            status: "pending",
          });
          Utils.toast("已重置状态", "info");
          refresh();
        },
      });
    }

    items.push({
      label: "📍 设置GPS为当前位置",
      action: async function () {
        await MapHelper.setPointLocationToCurrent(
          App.getCurrentProjectId(),
          point.id
        );
        refresh();
      },
    });

    // 创建菜单DOM
    const menu = document.createElement("div");
    menu.style.cssText =
      "position:fixed;background:white;border:1px solid #ddd;border-radius:4px;" +
      "box-shadow:0 4px 12px rgba(0,0,0,0.15);z-index:3000;min-width:160px;padding:4px 0;";
    menu.style.left = x + "px";
    menu.style.top = y + "px";

    items.forEach(function (item) {
      const div = document.createElement("div");
      div.textContent = item.label;
      div.style.cssText =
        "padding:8px 16px;cursor:pointer;font-size:13px;" +
        "transition:background 0.1s;";
      div.addEventListener("mouseenter", function () {
        this.style.background = "#f0f0f0";
      });
      div.addEventListener("mouseleave", function () {
        this.style.background = "";
      });
      div.addEventListener("click", function () {
        item.action();
        menu.remove();
      });
      menu.appendChild(div);
    });

    document.body.appendChild(menu);

    function removeMenu() {
      menu.remove();
      document.removeEventListener("click", removeMenu);
    }
    setTimeout(function () {
      document.addEventListener("click", removeMenu);
    }, 0);
  }

  /**
   * 更新统计信息
   */
  function updateStats() {
    const total = _points.length;
    const surveyed = _points.filter(function (p) {
      return p.status === "surveyed";
    }).length;

    document.getElementById("point-stats").innerHTML =
      `共 <strong>${total}</strong> 个点 | 已完成: <strong>${surveyed}</strong>`;
  }

  /**
   * 绑定事件
   */
  function initEvents() {
    document
      .getElementById("status-filter")
      .addEventListener("change", function () {
        refresh(this.value);
      });

    document
      .getElementById("search-input")
      .addEventListener(
        "input",
        Utils.debounce(function () {
          render();
        }, 300)
      );
  }

  return {
    refresh,
    render,
    selectPoint,
    initEvents,
  };
})();
