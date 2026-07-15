/* 地图交互模块 */

const MapHelper = (function () {

  /**
   * 导航到指定GPS坐标
   */
  async function navigateTo(lat, lng, zoom) {
    if (!lat || !lng) {
      Utils.toast("该调查点尚未设置GPS坐标", "warning");
      return false;
    }
    try {
      await OvitalSDK.setMapLocation(lat, lng, zoom || 18);
      return true;
    } catch (e) {
      Utils.toast("地图导航失败", "error");
      return false;
    }
  }

  /**
   * 获取当前GPS位置并在表单中填充
   */
  async function getCurrentPosition() {
    try {
      const pos = await OvitalSDK.getCurrentLatLng();
      return pos;
    } catch (e) {
      Utils.toast("获取GPS位置失败", "error");
      return null;
    }
  }

  /**
   * 在当前位置添加临时标记
   */
  async function markCurrentPosition(name) {
    const pos = await OvitalSDK.getCurrentLatLng();
    if (pos) {
      return await OvitalSDK.addTmpSign(pos.lat, pos.lng, name || "当前位置");
    }
    return null;
  }

  /**
   * 批量在地图上显示调查点
   */
  async function showPointsOnMap(points, projectId) {
    if (!OvitalSDK.isAvailable()) {
      console.log("[MapHelper] 模拟模式，跳过批量添加标记");
      return;
    }

    let count = 0;
    for (const point of points) {
      if (point.latitude && point.longitude) {
        const markerId = await OvitalSDK.addTmpSign(
          point.latitude,
          point.longitude,
          point.point_number,
          _statusIcon(point.status)
        );
        if (markerId) {
          // 保存标记ID
          try {
            await API.points.update(projectId, point.id, {
              ovital_marker_id: markerId,
            });
          } catch (e) {
            // 忽略保存失败的标记ID
          }
          count++;
        }
      }
    }
    if (count > 0) {
      Utils.toast(`已在地图上显示 ${count} 个调查点`, "info");
    }
  }

  function _statusIcon(status) {
    const icons = {
      pending: 1,
      in_progress: 2,
      surveyed: 3,
      skipped: 4,
    };
    return icons[status] || 1;
  }

  /**
   * 设置调查点GPS为当前位置
   */
  async function setPointLocationToCurrent(projectId, pointId) {
    const pos = await getCurrentPosition();
    if (!pos) return false;

    try {
      await API.points.updateLocation(projectId, pointId, {
        latitude: pos.lat,
        longitude: pos.lng,
        altitude: pos.alt || 0,
      });
      Utils.toast(`GPS坐标已更新: ${pos.lat.toFixed(6)}, ${pos.lng.toFixed(6)}`, "success");
      return true;
    } catch (e) {
      Utils.toast("保存GPS坐标失败: " + e.message, "error");
      return false;
    }
  }

  return {
    navigateTo,
    getCurrentPosition,
    markCurrentPosition,
    showPointsOnMap,
    setPointLocationToCurrent,
  };
})();
