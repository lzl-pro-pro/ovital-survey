/* 奥维 OPEN+ SDK 封装层
 *
 * 在奥维PC客户端中打开时，OPEN+ SDK 通过 omapjsSDK.js 注入全局函数。
 * 在普通浏览器中打开时，自动使用模拟数据，方便开发调试。
 */

const OvitalSDK = (function () {
  let _available = false;

  // SDK 函数可能在 window 上，也可能在 window.omap 上
  function _getFn(name) {
    // 直接全局函数（奥维SDK通常这样暴露）
    if (typeof window[name] === "function") return window[name];
    // 在 window.omap 命名空间下
    if (window.omap && typeof window.omap[name] === "function") return window.omap[name];
    // 其他可能的命名空间
    if (window.ovitalMap && typeof window.ovitalMap[name] === "function") return window.ovitalMap[name];
    return null;
  }

  function init() {
    // 检测关键函数是否存在
    var hasGetLatLng = _getFn("getLatLng") !== null;
    var hasSetMapLocation = _getFn("setMapLocation") !== null;
    var hasAddTmpSign = _getFn("addTmpSign") !== null;

    _available = hasGetLatLng && hasSetMapLocation && hasAddTmpSign;

    updateStatusBadge();
    console.log(
      "[OvitalSDK] " + (_available ? "✓ 奥维SDK已连接" : "○ 模拟模式（非奥维环境，GPS/地图功能使用模拟数据）")
    );
  }

  function updateStatusBadge() {
    var badge = document.getElementById("sdk-status");
    if (badge) {
      badge.textContent = _available ? "🟢" : "🟡";
      badge.title = _available
        ? "奥维地图SDK已连接 — 可使用GPS定位、地图导航等功能"
        : "模拟模式 — 在奥维PC端OPEN+面板中打开此页面即可启用全部功能";
    }
  }

  function isAvailable() {
    return _available;
  }

  // ================ 位置相关 ================

  var _mockLat = 30.5928;
  var _mockLng = 114.3055;

  function mockGpsPosition() {
    _mockLat += (Math.random() - 0.5) * 0.0001;
    _mockLng += (Math.random() - 0.5) * 0.0001;
    return { lat: _mockLat, lng: _mockLng, alt: 30 + Math.random() * 5 };
  }

  async function getCurrentLatLng() {
    if (_available) {
      try {
        var fn = _getFn("getLatLng");
        // SDK的getLatLng可能是回调模式也可能是Promise模式
        var pos = await new Promise(function (resolve, reject) {
          try {
            var result = fn();
            // 如果返回Promise
            if (result && typeof result.then === "function") {
              result.then(resolve, reject);
            } else {
              resolve(result);
            }
          } catch (e) {
            reject(e);
          }
        });
        if (pos) {
          return { lat: pos.lat || pos.latitude || 0, lng: pos.lng || pos.longitude || 0, alt: pos.alt || pos.altitude || 0 };
        }
      } catch (e) {
        console.warn("[OvitalSDK] getLatLng error:", e);
      }
    }
    return mockGpsPosition();
  }

  // ================ 地图控制 ================

  async function setMapLocation(lat, lng, zoom) {
    zoom = zoom || 18;
    if (_available) {
      try {
        var fn = _getFn("setMapLocation");
        fn(lat, lng, zoom);
        return true;
      } catch (e) {
        console.warn("[OvitalSDK] setMapLocation error:", e);
      }
    }
    console.log("[OvitalSDK Mock] setMapLocation: " + lat.toFixed(6) + ", " + lng.toFixed(6) + " zoom=" + zoom);
    return true;
  }

  async function addTmpSign(lat, lng, name, iconId) {
    iconId = iconId || 1;
    if (_available) {
      try {
        var fn = _getFn("addTmpSign");
        var markerId = fn(lat, lng, name, iconId);
        return markerId || "marker_" + Date.now();
      } catch (e) {
        console.warn("[OvitalSDK] addTmpSign error:", e);
      }
    }
    var mockId = "mock_marker_" + Date.now();
    console.log("[OvitalSDK Mock] addTmpSign: '" + name + "' at " + lat.toFixed(6) + ", " + lng.toFixed(6));
    return mockId;
  }

  async function removeTmpSign(markerId) {
    if (_available) {
      try {
        var fn = _getFn("removeTmpSign");
        fn(markerId);
        return true;
      } catch (e) {
        console.warn("[OvitalSDK] removeTmpSign error:", e);
      }
    }
    console.log("[OvitalSDK Mock] removeTmpSign: " + markerId);
    return true;
  }

  // ================ 收藏夹操作 ================

  async function getOmapObjectList() {
    if (_available) {
      try {
        var fn = _getFn("getOmapObjectList");
        return fn() || [];
      } catch (e) {
        console.warn("[OvitalSDK] getOmapObjectList error:", e);
      }
    }
    return [];
  }

  async function getOmapObject(id) {
    if (_available) {
      try {
        var fn = _getFn("getOmapObject");
        return fn(id);
      } catch (e) {
        console.warn("[OvitalSDK] getOmapObject error:", e);
      }
    }
    return null;
  }

  async function setOmapObject(id, data) {
    if (_available) {
      try {
        var fn = _getFn("setOmapObject");
        fn(id, data);
        return true;
      } catch (e) {
        console.warn("[OvitalSDK] setOmapObject error:", e);
      }
    }
    return false;
  }

  async function delOmapObject(id) {
    if (_available) {
      try {
        var fn = _getFn("delOmapObject");
        fn(id);
        return true;
      } catch (e) {
        console.warn("[OvitalSDK] delOmapObject error:", e);
      }
    }
    return false;
  }

  // ================ 用户信息 ================

  async function getUserInfo() {
    if (_available) {
      try {
        var fn = _getFn("getUserInfo");
        var info = fn();
        return info || { uid: "", name: "" };
      } catch (e) {
        console.warn("[OvitalSDK] getUserInfo error:", e);
      }
    }
    return { uid: "dev_user", name: "开发测试" };
  }

  async function getVipGrade() {
    if (_available) {
      try {
        var fn = _getFn("getVipGrade");
        return fn() || 0;
      } catch (e) {}
    }
    return 0;
  }

  async function getVersion() {
    if (_available) {
      try {
        var fn = _getFn("getVersion");
        return fn() || "unknown";
      } catch (e) {}
    }
    return "dev-1.0.0";
  }

  // 延迟初始化：等 SDK 脚本加载完成
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    // 如果 SDK 脚本还在加载，等一会
    setTimeout(init, 1000);
  }

  return {
    init: init,
    isAvailable: isAvailable,
    getCurrentLatLng: getCurrentLatLng,
    setMapLocation: setMapLocation,
    addTmpSign: addTmpSign,
    removeTmpSign: removeTmpSign,
    getOmapObjectList: getOmapObjectList,
    getOmapObject: getOmapObject,
    setOmapObject: setOmapObject,
    delOmapObject: delOmapObject,
    getUserInfo: getUserInfo,
    getVipGrade: getVipGrade,
    getVersion: getVersion,
  };
})();
