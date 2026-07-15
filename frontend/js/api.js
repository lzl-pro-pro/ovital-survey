/* HTTP API 客户端 */

const API = (function () {
  const BASE_URL = "";  // 同源

  /**
   * 通用请求函数
   */
  async function request(method, url, data, options) {
    options = options || {};
    const opts = {
      method: method,
      headers: {},
    };

    if (data instanceof FormData) {
      opts.body = data;
      // 不设置 Content-Type，让浏览器自动处理 multipart
    } else if (data && typeof data === "object") {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(data);
    }

    const controller = new AbortController();
    const timeout = options.timeout || 30000;
    const timer = setTimeout(() => controller.abort(), timeout);
    opts.signal = controller.signal;

    try {
      const response = await fetch(BASE_URL + url, opts);
      clearTimeout(timer);

      // 处理文件下载
      if (options.download && response.ok) {
        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition") || "";
        const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        let filename = match ? match[1].replace(/['"]/g, "") : "download";
        // URL decode
        try { filename = decodeURIComponent(filename); } catch (e) {}
        downloadBlob(blob, filename);
        return { error: false };
      }

      const json = await response.json();
      if (!response.ok) {
        throw new ApiError(
          json.message || `请求失败 (${response.status})`,
          json.code || "HTTP_ERROR",
          response.status
        );
      }
      return json;
    } catch (e) {
      clearTimeout(timer);
      if (e instanceof ApiError) throw e;
      if (e.name === "AbortError") {
        throw new ApiError("请求超时", "TIMEOUT", 0);
      }
      throw new ApiError(
        `网络连接失败: ${e.message}`,
        "NETWORK_ERROR",
        0
      );
    }
  }

  class ApiError extends Error {
    constructor(message, code, status) {
      super(message);
      this.code = code;
      this.status = status;
    }
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ===== 项目 API =====
  const projects = {
    list() { return request("GET", "/api/projects"); },
    get(id) { return request("GET", `/api/projects/${id}`); },
    create(data) { return request("POST", "/api/projects", data); },
    update(id, data) { return request("PUT", `/api/projects/${id}`, data); },
    delete(id) { return request("DELETE", `/api/projects/${id}`); },
    uploadCad(id, formData) {
      return request("POST", `/api/projects/${id}/upload-cad`, formData);
    },
    cadInfo(id) { return request("GET", `/api/projects/${id}/cad-info`); },
  };

  // ===== 标注 API =====
  const annotations = {
    list(projectId, params) {
      let qs = "";
      if (params) {
        const sp = new URLSearchParams();
        for (const [k, v] of Object.entries(params)) {
          if (v !== undefined && v !== null) sp.append(k, v);
        }
        qs = "?" + sp.toString();
      }
      return request("GET", `/api/projects/${projectId}/annotations${qs}`);
    },
    update(projectId, annId, data) {
      return request("PUT", `/api/projects/${projectId}/annotations/${annId}`, data);
    },
    confirm(projectId, data) {
      return request("POST", `/api/projects/${projectId}/annotations/confirm`, data);
    },
  };

  // ===== 调查点 API =====
  const points = {
    list(projectId, params) {
      let qs = "";
      if (params) {
        const sp = new URLSearchParams();
        for (const [k, v] of Object.entries(params)) {
          if (v !== undefined && v !== null) sp.append(k, v);
        }
        qs = "?" + sp.toString();
      }
      return request("GET", `/api/projects/${projectId}/points${qs}`);
    },
    get(projectId, pointId) {
      return request("GET", `/api/projects/${projectId}/points/${pointId}`);
    },
    update(projectId, pointId, data) {
      return request("PUT", `/api/projects/${projectId}/points/${pointId}`, data);
    },
    updateLocation(projectId, pointId, data) {
      return request("PUT", `/api/projects/${projectId}/points/${pointId}/location`, data);
    },
    saveRecords(projectId, pointId, data) {
      return request("PUT", `/api/projects/${projectId}/points/${pointId}/records`, data);
    },
    getProjectNames() {
      return request("GET", "/api/projects/project-names");
    },
    batchProjectName(projectId, name) {
      return request("PUT", "/api/projects/" + projectId + "/batch-project-name", { name: name });
    },
    batchInvestigator(projectId, name) {
      return request("PUT", "/api/projects/" + projectId + "/batch-investigator", { name: name });
    },
    stats(projectId) {
      return request("GET", `/api/projects/${projectId}/stats`);
    },
  };

  // ===== 照片 API =====
  const photos = {
    list(projectId, pointId) {
      return request("GET", `/api/projects/${projectId}/points/${pointId}/photos`);
    },
    upload(projectId, pointId, formData) {
      return request("POST", `/api/projects/${projectId}/points/${pointId}/photos`, formData);
    },
    delete(projectId, pointId, photoId) {
      return request("DELETE", `/api/projects/${projectId}/points/${pointId}/photos/${photoId}`);
    },
    getImageUrl(projectId, pointId, photoId) {
      return `/api/projects/${projectId}/points/${pointId}/photos/${photoId}/image`;
    },
    getThumbUrl(projectId, pointId, photoId) {
      return `/api/projects/${projectId}/points/${pointId}/photos/${photoId}/thumbnail`;
    },
  };

  // ===== 导出 API =====
  const exports = {
    trigger(projectId, data) {
      return request("POST", `/api/projects/${projectId}/export`, data);
    },
    status(projectId, exportId) {
      return request("GET", `/api/projects/${projectId}/export/status/${exportId}`);
    },
    download(projectId, exportId) {
      return request("GET", `/api/projects/${projectId}/export/download/${exportId}`, null, { download: true });
    },
  };

  // ===== 模板 API =====
  const templates = {
    list() { return request("GET", "/api/templates"); },
    get(id) { return request("GET", `/api/templates/${id}`); },
    create(data) { return request("POST", "/api/templates", data); },
    delete(id) { return request("DELETE", `/api/templates/${id}`); },
  };

  return {
    projects,
    annotations,
    points,
    photos,
    exports,
    templates,
    ApiError,
  };
})();
