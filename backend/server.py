"""Flask 应用工厂和后端服务"""

import os
import sys
import traceback
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from config import LOG_FOLDER, ensure_directories


def _version_newer(a, b):
    try:
        pa = [int(x) for x in a.split(".")]
        pb = [int(x) for x in b.split(".")]
        for i in range(max(len(pa), len(pb))):
            va = pa[i] if i < len(pa) else 0
            vb = pb[i] if i < len(pb) else 0
            if va > vb: return True
            if va < vb: return False
        return False
    except Exception:
        return a.strip() != b.strip()


def _get_frontend_path():
    """获取前端文件路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，文件在 _MEIPASS 临时目录
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "frontend")


def create_app():
    """创建 Flask 应用实例"""
    ensure_directories()

    app = Flask(
        __name__,
        static_folder=_get_frontend_path(),
        static_url_path=""
    )

    # CORS 允许奥维内嵌浏览器访问
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 配置日志
    _setup_logging(app)

    # 注册 API 路由 Blueprint
    from backend.routes.projects import projects_bp
    from backend.routes.annotations import annotations_bp
    from backend.routes.points import points_bp
    from backend.routes.photos import photos_bp
    from backend.routes.exports import exports_bp
    from backend.routes.templates import templates_bp
    from config import VERSION, UPDATE_URLS

    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(annotations_bp, url_prefix="/api/projects")
    app.register_blueprint(points_bp, url_prefix="/api/projects")
    app.register_blueprint(photos_bp, url_prefix="/api/projects")
    app.register_blueprint(exports_bp, url_prefix="/api/projects")
    app.register_blueprint(templates_bp, url_prefix="/api/templates")

    # 禁用缓存（开发阶段）
    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # 前端页面路由
    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "version": VERSION})

    @app.route("/api/version")
    def api_version():
        return jsonify({"version": VERSION, "update_url": UPDATE_URLS[0]})

    @app.route("/api/check-update")
    def api_check_update():
        import urllib.request
        for url in UPDATE_URLS:
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                latest = data.get("version", "")
                is_new = _version_newer(latest, VERSION)
                return jsonify({
                    "error": False,
                    "current": VERSION,
                    "latest": latest,
                    "has_update": is_new,
                    "download_url": data.get("download_url", ""),
                })
            except Exception:
                continue
        return jsonify({
            "error": False,
            "current": VERSION,
            "latest": "",
            "has_update": False,
            "message": "无法连接到更新服务器"
        })

    @app.route("/api/do-update", methods=["POST"])
    def api_do_update():
        """执行更新"""
        from backend.updater import check_update, download_update, apply_update
        import sys as _sys
        try:
            has, latest, dl_url = check_update(VERSION, UPDATE_URLS)
            if not has:
                return jsonify({"error": True, "message": "已经是最新版本"})
            new_exe = download_update(dl_url)
            current_exe = _sys.executable if getattr(_sys, 'frozen', False) else _sys.argv[0]
            apply_update(current_exe, new_exe)
            return jsonify({"error": False, "message": f"更新到 v{latest}，即将重启"})
        except Exception as e:
            return jsonify({"error": True, "message": f"更新失败: {str(e)}"})

    # 全局错误处理
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({
            "error": True, "code": "BAD_REQUEST",
            "message": str(e.description) if e.description else "请求参数错误"
        }), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "请求的资源不存在"
        }), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({
            "error": True, "code": "FILE_TOO_LARGE",
            "message": "上传文件超过大小限制"
        }), 413

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"500 Internal Error: {traceback.format_exc()}")
        return jsonify({
            "error": True, "code": "SERVER_ERROR",
            "message": "服务器内部错误，请查看日志"
        }), 500

    return app


def _setup_logging(app):
    """配置日志"""
    log_file = os.path.join(LOG_FOLDER, "error.log")
    os.makedirs(LOG_FOLDER, exist_ok=True)

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))
    app.logger.addHandler(handler)
