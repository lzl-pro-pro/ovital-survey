/* 动态调查表单模块 */

const SurveyForm = (function () {
  let _currentPoint = null;
  let _templateFields = [];
  let _autoSaveTimer = null;
  let _lastInvestigator = "";

  // 从localStorage恢复最后使用的调查人
  try {
    _lastInvestigator = localStorage.getItem("ovital_last_investigator") || "";
  } catch (e) {}

  /**
   * 渲染调查表单
   */
  function render(pointDetail) {
    _currentPoint = pointDetail;
    const formContainer = document.getElementById("survey-form");

    // 更新标题
    document.getElementById("survey-point-title").textContent =
      "调查点: " + (pointDetail.point_number || "");

    // 状态徽章
    const statusBadge = Utils.statusBadge(pointDetail.status);

    // 获取模板字段
    loadTemplateFields().then(function (fields) {
      _templateFields = fields;

      // 调查记录转为key-value映射
      const records = {};
      (pointDetail.records || []).forEach(function (r) {
        records[r.field_key] = r.field_value || "";
      });

      var hasGps = pointDetail.longitude && pointDetail.latitude;
      var gpsText = hasGps
        ? "经度: " + pointDetail.longitude.toFixed(6) + "  纬度: " + pointDetail.latitude.toFixed(6) + "  高程: " + (pointDetail.altitude||0).toFixed(1) + "m"
        : "未设置 - 请点击「📍 一键定位」";

      let html = `
        <div style="margin-bottom:12px;">
          ${statusBadge}
        </div>
        <div id="gps-display" style="margin-bottom:16px;padding:10px 14px;background:#F5F5F5;border-radius:6px;font-size:13px;${hasGps ? 'color:#2E7D32;font-weight:bold;' : 'color:#C62828;'}">
          ${gpsText}
        </div>
      `;

      fields.forEach(function (field) {
        const value = records[field.field_key] || "";
        html += renderField(field, value);
      });

      formContainer.innerHTML = html;

      // 自动填充
      autoFill(fields, records);

      // 绑定自动保存
      bindAutoSave();

      // 工程名称自动补全
      setupNameAutocomplete();
    });
  }

  /**
   * 工程名称自动补全
   */
  function setupNameAutocomplete() {
    var field = document.getElementById("field-project_name");
    if (!field) return;

    // 移除旧的下拉
    var old = document.getElementById("name-suggestions");
    if (old) old.remove();

    var wrapper = document.createElement("div");
    wrapper.style.cssText = "position:relative;";
    field.parentNode.insertBefore(wrapper, field);
    wrapper.appendChild(field);

    var dropdown = document.createElement("div");
    dropdown.id = "name-suggestions";
    dropdown.style.cssText = "display:none;position:absolute;top:100%;left:0;right:0;" +
      "background:white;border:1px solid #ddd;border-radius:0 0 4px 4px;" +
      "max-height:200px;overflow-y:auto;z-index:100;box-shadow:0 4px 8px rgba(0,0,0,0.1);";
    wrapper.appendChild(dropdown);

    // 加载历史名称
    API.points.getProjectNames().then(function (res) {
      var names = res.data || [];
      window._cachedProjectNames = names;

      field.addEventListener("input", function () {
        var val = this.value.toLowerCase();
        var matches = names.filter(function (n) {
          return n.toLowerCase().indexOf(val) >= 0 && n !== this.value;
        }.bind(this));

        if (matches.length === 0) {
          dropdown.style.display = "none";
          return;
        }

        dropdown.innerHTML = matches.slice(0, 8).map(function (n) {
          return '<div class="name-option" style="padding:6px 10px;cursor:pointer;font-size:13px;' +
            'border-bottom:1px solid #f0f0f0;">' + Utils.escapeHtml(n) + '</div>';
        }).join("");

        dropdown.style.display = "block";
        dropdown.querySelectorAll(".name-option").forEach(function (opt) {
          opt.addEventListener("mousedown", function (e) {
            e.preventDefault();
            field.value = opt.textContent;
            dropdown.style.display = "none";
          });
        });
      });

      field.addEventListener("blur", function () {
        setTimeout(function () { dropdown.style.display = "none"; }, 200);
      });
    }).catch(function () {});
  }

  /**
   * 加载模板字段
   */
  async function loadTemplateFields() {
    try {
      const res = await API.templates.list();
      if (!res.error && res.data.length > 0) {
        // 优先使用默认模板
        const defaultTpl = res.data.find(function (t) {
          return t.is_default === 1;
        });
        const tplId = defaultTpl ? defaultTpl.id : res.data[0].id;
        const detail = await API.templates.get(tplId);
        if (!detail.error) {
          return detail.data.fields || [];
        }
      }
    } catch (e) {
      console.warn("加载模板失败，使用内置默认字段", e);
    }

    // 降级：内置默认字段
    return [
      { field_key: "point_number", field_label: "编号", field_type: "text", field_order: 1, is_required: 1 },
      { field_key: "project_name", field_label: "工程名称", field_type: "text", field_order: 2, is_required: 1 },
      { field_key: "location_desc", field_label: "位置描述", field_type: "multiline", field_order: 3, is_required: 1 },
      { field_key: "station_number", field_label: "桩号", field_type: "text", field_order: 4, is_required: 0 },
      { field_key: "investigator", field_label: "调查人", field_type: "text", field_order: 5, is_required: 1 },
      { field_key: "survey_date", field_label: "调查日期", field_type: "date", field_order: 6, is_required: 1 },
      { field_key: "weather", field_label: "天气", field_type: "select", field_order: 7, is_required: 0, options: ["晴","多云","阴","小雨","中雨","大雨","雾","雪"] },
      { field_key: "geo_desc", field_label: "地质描述", field_type: "multiline", field_order: 8, is_required: 0 },
      { field_key: "landform_type", field_label: "地貌类型", field_type: "select", field_order: 9, is_required: 0, options: ["平原","丘陵","山地","河谷","台地","沙漠","戈壁","其他"] },
      { field_key: "vegetation_type", field_label: "植被类型", field_type: "select", field_order: 10, is_required: 0, options: ["无植被","草地","灌木","针叶林","阔叶林","混交林","农田","其他"] },
      { field_key: "remarks", field_label: "备注", field_type: "multiline", field_order: 11, is_required: 0 },
    ];
  }

  /**
   * 渲染单个字段
   */
  function renderField(field, value) {
    const required = field.is_required ? '<span class="required">*</span>' : "";
    let inputHtml = "";

    switch (field.field_type) {
      case "select":
        const options = field.options || [];
        inputHtml = `<select id="field-${field.field_key}" class="form-field" data-key="${field.field_key}" data-type="select">
          <option value="">-- 请选择 --</option>
          ${options.map(function(opt) {
            const selected = opt === value ? " selected" : "";
            return `<option value="${Utils.escapeHtml(opt)}"${selected}>${Utils.escapeHtml(opt)}</option>`;
          }).join("")}
        </select>`;
        break;

      case "multiline":
        inputHtml = `<textarea id="field-${field.field_key}" class="form-field" data-key="${field.field_key}" data-type="multiline" rows="3">${Utils.escapeHtml(value)}</textarea>`;
        break;

      case "date":
        inputHtml = `<input type="date" id="field-${field.field_key}" class="form-field" data-key="${field.field_key}" data-type="date" value="${Utils.escapeHtml(value)}">`;
        break;

      case "number":
        inputHtml = `<input type="number" id="field-${field.field_key}" class="form-field" data-key="${field.field_key}" data-type="number" value="${Utils.escapeHtml(value)}" step="any">`;
        break;

      default: // text
        inputHtml = `<input type="text" id="field-${field.field_key}" class="form-field" data-key="${field.field_key}" data-type="text" value="${Utils.escapeHtml(value)}">`;
    }

    return `
      <div class="form-group">
        <label for="field-${field.field_key}">${field.field_label}${required}</label>
        ${inputHtml}
        <span class="error-text" id="error-${field.field_key}">此字段为必填项</span>
      </div>
    `;
  }

  /**
   * 自动填充
   */
  function autoFill(fields, records) {
    const today = new Date().toISOString().slice(0, 10);

    // 自动填充调查人（如果为空）
    const invField = document.getElementById("field-investigator");
    if (invField && !invField.value.trim() && _lastInvestigator) {
      invField.value = _lastInvestigator;
    }

    // 自动填充日期（如果为空）
    const dateField = document.getElementById("field-survey_date");
    if (dateField && !dateField.value.trim()) {
      dateField.value = today;
    }

    // 自动填充编号
    const numField = document.getElementById("field-point_number");
    if (numField && !numField.value.trim() && _currentPoint) {
      numField.value = _currentPoint.point_number || "";
    }

    // 从Ovital获取用户信息填充调查人
    if (invField && !invField.value.trim()) {
      OvitalSDK.getUserInfo().then(function (info) {
        if (info && info.name && info.name !== "测试用户") {
          invField.value = info.name;
          _lastInvestigator = info.name;
          try { localStorage.setItem("ovital_last_investigator", info.name); } catch(e) {}
        }
      });
    }
  }

  /**
   * 收集表单数据
   */
  function collectData() {
    const fields = document.querySelectorAll(".form-field");
    const records = [];

    fields.forEach(function (field) {
      records.push({
        field_key: field.dataset.key,
        field_label: document.querySelector(`label[for="${field.id}"]`)?.textContent.replace("*", "").trim() || field.dataset.key,
        field_value: field.value || "",
        field_type: field.dataset.type || "text",
        field_order: _templateFields.findIndex(function(f) { return f.field_key === field.dataset.key; }) + 1,
      });
    });

    // 保存调查人
    const invField = document.getElementById("field-investigator");
    if (invField && invField.value.trim()) {
      _lastInvestigator = invField.value.trim();
      try { localStorage.setItem("ovital_last_investigator", _lastInvestigator); } catch(e) {}
    }

    return records;
  }

  /**
   * 验证表单
   */
  function validate() {
    let valid = true;
    _templateFields.forEach(function (field) {
      if (!field.is_required) return;

      const el = document.getElementById("field-" + field.field_key);
      const errEl = document.getElementById("error-" + field.field_key);

      if (el && !el.value.trim()) {
        el.classList.add("field-error");
        if (errEl) errEl.style.display = "block";
        valid = false;
      } else {
        if (el) el.classList.remove("field-error");
        if (errEl) errEl.style.display = "none";
      }
    });
    return valid;
  }

  /**
   * 保存草稿
   */
  async function saveDraft() {
    if (!_currentPoint) return;

    const records = collectData();
    try {
      await API.points.saveRecords(
        App.getCurrentProjectId(),
        _currentPoint.id,
        { records: records }
      );
      await API.points.update(App.getCurrentProjectId(), _currentPoint.id, {
        status: "in_progress",
      });
      Utils.toast("草稿已保存", "success");
      SurveyPointList.refresh();
    } catch (e) {
      Utils.toast("保存失败: " + e.message, "error");
    }
  }

  /**
   * 标记完成
   */
  async function markDone() {
    if (!_currentPoint) return;

    if (!validate()) {
      Utils.toast("请填写所有必填字段", "warning");
      return;
    }

    const records = collectData();
    try {
      await API.points.saveRecords(
        App.getCurrentProjectId(),
        _currentPoint.id,
        { records: records }
      );
      await API.points.update(App.getCurrentProjectId(), _currentPoint.id, {
        status: "surveyed",
      });
      Utils.toast("✅ 调查完成！", "success");
      SurveyPointList.refresh();

      // 更新当前状态显示
      if (_currentPoint) {
        _currentPoint.status = "surveyed";
        document.getElementById("survey-point-title").textContent =
          "调查点: " + (_currentPoint.point_number || "") + " ✅";
      }
    } catch (e) {
      Utils.toast("保存失败: " + e.message, "error");
    }
  }

  /**
   * 绑定自动保存
   */
  function bindAutoSave() {
    document.querySelectorAll(".form-field").forEach(function (field) {
      field.addEventListener("input", function () {
        clearTimeout(_autoSaveTimer);
        _autoSaveTimer = setTimeout(function () {
          if (_currentPoint) {
            const records = collectData();
            API.points
              .saveRecords(App.getCurrentProjectId(), _currentPoint.id, {
                records: records,
              })
              .catch(function () {});
          }
        }, 5000);
      });
    });
  }

  /**
   * 绑定界面事件
   */
  function initEvents() {
    document.getElementById("btn-save-draft").addEventListener("click", saveDraft);
    document.getElementById("btn-mark-done").addEventListener("click", markDone);

    // 一键定位：获取当前GPS并保存到调查点
    document.getElementById("btn-gps-locate").addEventListener("click", function () {
      if (!_currentPoint) return;
      oneClickLocate();
    });
  }

  /**
   * 一键定位：浏览器GPS → 保存 → 刷新显示
   */
  async function oneClickLocate() {
    var btn = document.getElementById("btn-gps-locate");
    btn.disabled = true;
    btn.textContent = "📍 定位中...";

    try {
      var pos = await getCurrentPosition();
      if (!pos) {
        Utils.toast("无法获取GPS，请检查定位权限", "error");
        return;
      }

      // 保存到后端
      await API.points.updateLocation(
        App.getCurrentProjectId(),
        _currentPoint.id,
        { latitude: pos.lat, longitude: pos.lng, altitude: pos.alt || 0 }
      );

      // 更新界面显示
      _currentPoint.latitude = pos.lat;
      _currentPoint.longitude = pos.lng;
      _currentPoint.altitude = pos.alt || 0;

      // 刷新表单上的GPS显示
      var gpsEl = document.getElementById("gps-display");
      if (gpsEl) {
        gpsEl.textContent = "经度: " + pos.lng.toFixed(6) + "  纬度: " + pos.lat.toFixed(6) + "  高程: " + (pos.alt||0).toFixed(1) + "m";
        gpsEl.style.color = "#2E7D32";
        gpsEl.style.fontWeight = "bold";
      }

      Utils.toast("GPS已定位: " + pos.lat.toFixed(6) + ", " + pos.lng.toFixed(6), "success");
      SurveyPointList.refresh();
    } catch (e) {
      Utils.toast("定位失败: " + (e.message || "未知错误"), "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "📍 一键定位";
    }
  }

  /**
   * 获取当前GPS位置
   * 优先浏览器原生API（手机/平板/笔记本都支持）
   * 其次奥维SDK
   */
  function getCurrentPosition() {
    return new Promise(function (resolve) {
      // 方法1：浏览器 Geolocation API
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          function (geoPos) {
            resolve({
              lat: geoPos.coords.latitude,
              lng: geoPos.coords.longitude,
              alt: geoPos.coords.altitude || 0,
              accuracy: geoPos.coords.accuracy,
            });
          },
          function (err) {
            console.warn("[GPS] Browser geolocation failed:", err.message);
            // 回退到奥维SDK
            tryOvitalSDK(resolve);
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
      } else {
        tryOvitalSDK(resolve);
      }
    });
  }

  function tryOvitalSDK(resolve) {
    if (OvitalSDK && OvitalSDK.isAvailable()) {
      OvitalSDK.getCurrentLatLng().then(function (pos) {
        if (pos && pos.lat && pos.lng) {
          resolve(pos);
        } else {
          resolve(null);
        }
      }).catch(function () {
        resolve(null);
      });
    } else {
      Utils.toast("请允许浏览器获取位置权限，或在奥维中查看坐标后手动填入", "warning", 5000);
      resolve(null);
    }
  }

  return {
    render,
    collectData,
    saveDraft,
    markDone,
    initEvents,
  };
})();
