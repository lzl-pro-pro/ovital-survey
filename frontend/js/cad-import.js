/* CAD导入和标注审核模块 */

const CadImport = (function () {
  let _currentProjectId = null;
  let _annotations = [];
  let _currentPage = 1;
  let _totalPages = 1;

  /**
   * 触发CAD文件导入
   */
  async function importCad(projectId) {
    _currentProjectId = projectId;

    // 创建文件选择器
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".dxf,.dwg";
    input.onchange = async function (e) {
      const file = e.target.files[0];
      if (!file) return;

      console.log('[CAD] Uploading file:', file.name, 'size:', file.size, 'type:', file.type);
      Utils.toast("正在上传并解析CAD文件...", "info");
      var formData = new FormData();
      formData.append("file", file);

      try {
        var res = await API.projects.uploadCad(projectId, formData);
        console.log('[CAD] Server response:', res);
        if (res.error) {
          console.error('[CAD] Server error:', res.message, res.code);
          Utils.toast(res.message, "error");
          return;
        }

        var data = res.data;
        console.log('[CAD] Parsed:', data.annotation_count, 'annotations');
        showAnnotationReview(data);
        Utils.toast(
          "CAD解析完成：发现 " + data.annotation_count + " 个标注",
          "success"
        );
      } catch (e) {
        console.error('[CAD] Upload failed:', e, e.message, e.code, e.status);
        Utils.toast("CAD导入失败: " + (e.message || JSON.stringify(e)), "error");
      }
    };
    input.click();
  }

  /**
   * 显示标注审核界面
   */
  function showAnnotationReview(parseResult) {
    // 切换到标注审核视图
    App.switchView("annotation-review");

    // 显示解析信息
    const infoBar = document.getElementById("annotation-info");
    let warningsHtml = "";
    if (parseResult.warnings && parseResult.warnings.length > 0) {
      warningsHtml =
        '<div style="color:#E65100;">⚠ ' +
        parseResult.warnings.join("; ") +
        "</div>";
    }
    infoBar.innerHTML = `
      解析完成 | 标注总数: <strong>${parseResult.annotation_count}</strong> |
      图层数: <strong>${parseResult.layer_count}</strong>
      ${parseResult.has_more ? ' | <span style="color:#E65100;">仅显示前500条</span>' : ""}
      ${warningsHtml}
    `;

    _annotations = parseResult.annotations || [];
    _currentPage = 1;
    _totalPages = Math.ceil(parseResult.annotation_count / 50);
    renderAnnotationTable(1);
  }

  /**
   * 加载标注数据（服务器分页）
   */
  async function loadAnnotations(page) {
    if (!_currentProjectId) return;

    try {
      const res = await API.annotations.list(_currentProjectId, {
        confirmed: false,
        page: page,
        per_page: 50,
      });
      if (!res.error) {
        _annotations = res.data.items;
        _currentPage = res.data.page;
        _totalPages = Math.ceil(res.data.total / res.data.per_page);
        renderAnnotationTable();
      }
    } catch (e) {
      Utils.toast("加载标注失败: " + e.message, "error");
    }
  }

  /**
   * 渲染标注表格
   */
  function renderAnnotationTable() {
    const tbody = document.getElementById("annotation-tbody");
    tbody.innerHTML = "";

    if (_annotations.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="8" class="empty-hint">暂无待确认的标注</td></tr>';
      return;
    }

    _annotations.forEach(function (ann, index) {
      const tr = document.createElement("tr");
      const globalIndex = (_currentPage - 1) * 50 + index + 1;

      tr.innerHTML = `
        <td><input type="checkbox" class="ann-checkbox" data-id="${ann.id}"></td>
        <td>${globalIndex}</td>
        <td class="editable-cell" data-field="matched_label" data-id="${ann.id}">${Utils.escapeHtml(ann.matched_label || "")}</td>
        <td title="${Utils.escapeHtml(ann.text_content)}">${Utils.escapeHtml((ann.text_content || "").substring(0, 40))}${(ann.text_content || "").length > 40 ? "..." : ""}</td>
        <td>${ann.cad_x != null ? ann.cad_x.toFixed(2) : ""}</td>
        <td>${ann.cad_y != null ? ann.cad_y.toFixed(2) : ""}</td>
        <td>${Utils.escapeHtml(ann.layer_name || "-")}</td>
        <td>${ann.entity_type || "-"}</td>
      `;

      tbody.appendChild(tr);
    });

    // 渲染分页
    renderPagination();

    // 绑定可编辑单元格事件
    bindEditableCells();
  }

  function renderPagination() {
    const container = document.getElementById("annotation-pagination");
    container.innerHTML = `
      <button ${_currentPage <= 1 ? "disabled" : ""} data-page="${_currentPage - 1}">上一页</button>
      <span class="page-current">第 ${_currentPage} / ${_totalPages} 页</span>
      <button ${_currentPage >= _totalPages ? "disabled" : ""} data-page="${_currentPage + 1}">下一页</button>
    `;

    container.querySelectorAll("button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const page = parseInt(this.dataset.page);
        if (page > 0 && page <= _totalPages) {
          loadAnnotations(page);
        }
      });
    });
  }

  function bindEditableCells() {
    document.querySelectorAll(".editable-cell").forEach(function (cell) {
      cell.addEventListener("dblclick", function () {
        if (cell.querySelector("input")) return;

        const original = cell.textContent;
        const input = document.createElement("input");
        input.type = "text";
        input.value = original;
        input.style.width = "100%";
        input.style.padding = "2px";
        input.style.border = "1px solid #4472C4";
        input.style.borderRadius = "2px";

        cell.textContent = "";
        cell.appendChild(input);
        cell.classList.add("editing");
        input.focus();

        function save() {
          const newValue = input.value.trim();
          cell.textContent = newValue || original;
          cell.classList.remove("editing");

          const annId = parseInt(cell.dataset.id);
          const field = cell.dataset.field;
          if (annId && newValue !== original) {
            const data = {};
            data[field] = newValue;
            API.annotations
              .update(_currentProjectId, annId, data)
              .catch(function (e) {
                Utils.toast("保存失败: " + e.message, "error");
              });
          }
        }

        input.addEventListener("blur", save);
        input.addEventListener("keydown", function (e) {
          if (e.key === "Enter") {
            input.blur();
          }
          if (e.key === "Escape") {
            input.value = original;
            input.blur();
          }
        });
      });
    });
  }

  /**
   * 获取选中的标注ID列表
   */
  function getSelectedAnnotationIds() {
    const checkboxes = document.querySelectorAll(".ann-checkbox:checked");
    return Array.from(checkboxes).map(function (cb) {
      return parseInt(cb.dataset.id);
    });
  }

  /**
   * 确认标注并创建调查点
   */
  async function confirmAnnotations() {
    const ids = getSelectedAnnotationIds();
    if (ids.length === 0) {
      Utils.toast("请至少选择一个标注", "warning");
      return;
    }

    // 获取对应的标签
    const labels = [];
    ids.forEach(function (id) {
      const cell = document.querySelector(
        `.editable-cell[data-id="${id}"]`
      );
      labels.push(cell ? cell.textContent.trim() : "");
    });

    try {
      const res = await API.annotations.confirm(_currentProjectId, {
        annotation_ids: ids,
        point_labels: labels,
      });

      if (!res.error) {
        Utils.toast(`已创建 ${res.data.count} 个调查点`, "success");
        // 刷新项目并返回调查视图
        await App.refreshCurrentProject();
        SurveyPointList.refresh();
        App.switchView("welcome");
      }
    } catch (e) {
      Utils.toast("创建调查点失败: " + e.message, "error");
    }
  }

  /**
   * 初始化事件绑定
   */
  function initEvents() {
    document.getElementById("btn-import-cad").addEventListener("click", function () {
      if (!App.getCurrentProjectId()) {
        Utils.toast("请先选择项目", "warning");
        return;
      }
      importCad(App.getCurrentProjectId());
    });

    // 标注审核界面按钮
    document.getElementById("check-all-ann").addEventListener("change", function () {
      const checkboxes = document.querySelectorAll(".ann-checkbox");
      checkboxes.forEach(function (cb) {
        cb.checked = this.checked;
      }, this);
    });

    document.getElementById("btn-select-all-ann").addEventListener("click", function () {
      document.querySelectorAll(".ann-checkbox").forEach(function (cb) {
        cb.checked = true;
      });
      document.getElementById("check-all-ann").checked = true;
    });

    document.getElementById("btn-deselect-all-ann").addEventListener("click", function () {
      document.querySelectorAll(".ann-checkbox").forEach(function (cb) {
        cb.checked = false;
      });
      document.getElementById("check-all-ann").checked = false;
    });

    document.getElementById("btn-confirm-ann").addEventListener("click", confirmAnnotations);
  }

  return {
    importCad,
    initEvents,
    confirmAnnotations,
  };
})();
