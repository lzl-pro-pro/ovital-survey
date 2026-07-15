/* 照片管理模块 */

const PhotoManager = (function () {
  let _currentProjectId = null;
  let _currentPointId = null;
  let _photos = [];

  /**
   * 渲染照片画廊
   */
  function render(photos, projectId, pointId) {
    _currentProjectId = projectId;
    _currentPointId = pointId;
    _photos = photos || [];

    const gallery = document.getElementById("photo-gallery");
    const countEl = document.getElementById("photo-count");

    if (countEl) countEl.textContent = `(${_photos.length})`;

    if (_photos.length === 0) {
      gallery.innerHTML =
        '<div class="empty-hint" style="padding:20px;">暂无照片</div>';
      return;
    }

    gallery.innerHTML = "";
    _photos.forEach(function (photo) {
      const card = createPhotoCard(photo);
      gallery.appendChild(card);
    });
  }

  /**
   * 创建照片卡片
   */
  function createPhotoCard(photo) {
    const div = document.createElement("div");
    div.className = "photo-card";
    div.dataset.id = photo.id;

    const thumbUrl = API.photos.getThumbUrl(
      _currentProjectId,
      _currentPointId,
      photo.id
    );
    const imageUrl = API.photos.getImageUrl(
      _currentProjectId,
      _currentPointId,
      photo.id
    );

    const takenAt = photo.taken_at
      ? Utils.formatDateTime(photo.taken_at)
      : "";

    div.innerHTML = `
      <img src="${thumbUrl}" alt="${Utils.escapeHtml(photo.filename || '')}" loading="lazy"
           onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/><text x=%2250%22 y=%2255%22 text-anchor=%22middle%22 fill=%22%23999%22>无图片</text></svg>'">
      <div class="photo-info">${Utils.escapeHtml(takenAt)}</div>
      <div class="photo-actions">
        <button class="view-btn" data-url="${imageUrl}">🔍查看</button>
        <button class="delete-btn">🗑删除</button>
      </div>
    `;

    // 查看大图
    div.querySelector(".view-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      showLightbox(imageUrl);
    });

    // 点击图片查看大图
    div.querySelector("img").addEventListener("click", function () {
      showLightbox(imageUrl);
    });

    // 删除
    div.querySelector(".delete-btn").addEventListener("click", async function (e) {
      e.stopPropagation();
      const confirmed = await Utils.confirm("确认删除这张照片？");
      if (!confirmed) return;

      try {
        await API.photos.delete(_currentProjectId, _currentPointId, photo.id);
        Utils.toast("照片已删除", "success");

        // 从列表中移除
        _photos = _photos.filter(function (p) {
          return p.id !== photo.id;
        });
        render(_photos, _currentProjectId, _currentPointId);
      } catch (e) {
        Utils.toast("删除失败: " + e.message, "error");
      }
    });

    return div;
  }

  /**
   * 显示全屏查看
   */
  function showLightbox(url) {
    const lb = document.createElement("div");
    lb.className = "photo-lightbox";

    const img = document.createElement("img");
    img.src = url;
    img.onerror = function () {
      lb.innerHTML =
        '<div style="color:white;text-align:center;padding:40px;">图片加载失败</div>';
    };

    lb.appendChild(img);
    lb.addEventListener("click", function () {
      lb.remove();
    });
    document.addEventListener("keydown", function handler(e) {
      if (e.key === "Escape") {
        lb.remove();
        document.removeEventListener("keydown", handler);
      }
    });

    document.body.appendChild(lb);
  }

  /**
   * 触发照片添加（点击上传按钮）
   */
  function triggerUpload() {
    const input = document.getElementById("photo-file-input");
    if (input) {
      input.click();
    }
  }

  /**
   * 上传照片文件
   */
  async function uploadPhotos(files) {
    if (!files || files.length === 0) return;

    let success = 0;
    let failed = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      // 验证文件类型
      if (!file.type.startsWith("image/")) {
        Utils.toast(`跳过非图片文件: ${file.name}`, "warning");
        failed++;
        continue;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await API.photos.upload(
          _currentProjectId,
          _currentPointId,
          formData
        );
        if (!res.error) {
          success++;
          _photos.push(res.data);
        } else {
          failed++;
        }
      } catch (e) {
        failed++;
        Utils.toast(`上传失败: ${file.name} - ${e.message}`, "error");
      }
    }

    if (success > 0) {
      Utils.toast(`成功上传 ${success} 张照片` + (failed > 0 ? `，${failed} 张失败` : ""), "success");
      render(_photos, _currentProjectId, _currentPointId);
      SurveyPointList.refresh();
    } else if (failed > 0) {
      Utils.toast("所有照片上传失败", "error");
    }
  }

  /**
   * 拖放上传支持
   */
  function setupDragDrop() {
    const zone = document.getElementById("photo-upload-area");
    if (!zone) return;

    zone.addEventListener("dragover", function (e) {
      e.preventDefault();
      zone.classList.add("drop-highlight");
    });

    zone.addEventListener("dragleave", function () {
      zone.classList.remove("drop-highlight");
    });

    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      zone.classList.remove("drop-highlight");
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        uploadPhotos(files);
      }
    });
  }

  /**
   * 初始化事件
   */
  function initEvents() {
    // 照片上传按钮
    document.getElementById("btn-add-photo").addEventListener("click", function () {
      if (!_currentPointId) {
        Utils.toast("请先选择一个调查点", "warning");
        return;
      }
      triggerUpload();
    });

    // 文件选择事件
    document.getElementById("photo-file-input").addEventListener("change", function (e) {
      const files = e.target.files;
      if (files.length > 0) {
        uploadPhotos(files);
      }
      // 重置以允许重复选择同一文件
      this.value = "";
    });

    // 拖放支持
    setupDragDrop();
  }

  return {
    render,
    uploadPhotos,
    triggerUpload,
    initEvents,
  };
})();
