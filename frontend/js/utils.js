/* 通用工具函数 */

const Utils = {
  /**
   * Toast 消息提示
   */
  toast(msg, type = "info", duration = 3000) {
    const container = document.getElementById("toast-container");
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transition = "opacity 0.3s";
      setTimeout(() => el.remove(), 300);
    }, duration);
  },

  /**
   * 显示模态框
   */
  showModal(title, bodyHtml, footerHtml = "") {
    const overlay = document.getElementById("modal-overlay");
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-body").innerHTML = bodyHtml;
    document.getElementById("modal-footer").innerHTML = footerHtml;
    overlay.style.display = "flex";
  },

  /**
   * 关闭模态框
   */
  closeModal() {
    document.getElementById("modal-overlay").style.display = "none";
  },

  /**
   * 格式化日期
   */
  formatDate(dateStr) {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toISOString().slice(0, 10);
  },

  /**
   * 格式化日期时间
   */
  formatDateTime(dateStr) {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleString("zh-CN");
  },

  /**
   * 防抖
   */
  debounce(fn, delay = 300) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  },

  /**
   * 状态文字映射
   */
  statusLabel(status) {
    const map = {
      pending: "待调查",
      in_progress: "进行中",
      surveyed: "已完成",
      skipped: "已跳过",
    };
    return map[status] || status;
  },

  /**
   * 获取状态对应的CSS类
   */
  statusClass(status) {
    return `status-${status}`;
  },

  /**
   * 获取状态徽章HTML
   */
  statusBadge(status) {
    const label = Utils.statusLabel(status);
    return `<span class="badge badge-${status}">${label}</span>`;
  },

  /**
   * 自然排序比较
   */
  naturalCompare(a, b) {
    return String(a).localeCompare(String(b), undefined, {
      numeric: true,
      sensitivity: "base",
    });
  },

  /**
   * 确认对话框
   */
  confirm(msg) {
    return new Promise((resolve) => {
      const body = `<p style="text-align:center;padding:20px;">${msg}</p>`;
      const footer = `
        <button class="btn" onclick="Utils.closeModal();Utils._confirmResult=false">取消</button>
        <button class="btn btn-danger" onclick="Utils.closeModal();Utils._confirmResult=true">确认</button>
      `;
      Utils._confirmResult = false;
      Utils.showModal("确认操作", body, footer);
      const check = setInterval(() => {
        if (document.getElementById("modal-overlay").style.display === "none") {
          clearInterval(check);
          resolve(Utils._confirmResult);
        }
      }, 100);
    });
  },

  /**
   * 复制到剪贴板
   */
  async copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      Utils.toast("已复制到剪贴板", "success");
    } catch (e) {
      // 降级方案
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      Utils.toast("已复制到剪贴板", "success");
    }
  },

  /**
   * 转义HTML
   */
  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  },
};

// 模态框关闭按钮事件
document.addEventListener("click", function (e) {
  if (e.target.classList.contains("modal-overlay")) {
    Utils.closeModal();
  }
});
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") Utils.closeModal();
});
