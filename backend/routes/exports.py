"""导出管理 API 路由"""

import os
import json
import uuid
import threading
from flask import Blueprint, request, jsonify, send_file
from backend.data_manager import get_project
from backend.excel_exporter import (
    export_summary, export_individual, export_all
)
from backend.kml_exporter import export_kml
from backend.csv_exporter import export_csv
from backend.kmz_exporter import export_kmz
from config import EXPORT_FOLDER, BASE_DIR
import subprocess as _sp

# 导出目录配置（持久化到文件，按类型分开）
import atexit
import json as _json

_EXPORT_DIR_FILE = os.path.join(BASE_DIR, "data", ".export_dirs")


def _load_export_dirs():
    if os.path.exists(_EXPORT_DIR_FILE):
        try:
            with open(_EXPORT_DIR_FILE) as f:
                return _json.load(f)
        except Exception:
            pass
    return {}


def _save_export_dirs(dirs):
    os.makedirs(os.path.dirname(_EXPORT_DIR_FILE), exist_ok=True)
    with open(_EXPORT_DIR_FILE, "w") as f:
        _json.dump(dirs, f)


def _get_export_dir(export_type="all"):
    """按类型获取导出目录：kmz / summary / individual / all"""
    dirs = _load_export_dirs()
    d = dirs.get(export_type, "")
    if d and os.path.isdir(d):
        return d
    d = dirs.get("all", "")
    if d and os.path.isdir(d):
        return d
    return EXPORT_FOLDER

exports_bp = Blueprint("exports", __name__)

# 内存中跟踪导出任务状态
_export_tasks = {}


@exports_bp.route("/<int:project_id>/export", methods=["POST"])
def api_trigger_export(project_id):
    """触发导出任务"""
    project = get_project(project_id)
    if not project:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "项目不存在"
        }), 404

    data = request.get_json(silent=True) or {}
    export_type = data.get("type", "all")  # all, summary, individual
    point_ids = data.get("point_ids", [])  # 指定导出的点，空=全部

    task_id = str(uuid.uuid4())[:8]
    _export_tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "file_path": "",
        "error": "",
    }

    # 在后台线程执行导出（避免超时）
    thread = threading.Thread(
        target=_run_export,
        args=(task_id, project_id, export_type, point_ids),
        daemon=True
    )
    thread.start()

    return jsonify({
        "error": False,
        "data": {"export_id": task_id},
        "message": "导出任务已启动"
    })


def _run_export(task_id, project_id, export_type, point_ids):
    """后台执行导出任务"""
    try:
        os.makedirs(EXPORT_FOLDER, exist_ok=True)

        if export_type == "summary":
            file_path = export_summary(project_id, point_ids)
        elif export_type == "individual":
            file_path = export_individual(project_id, point_ids)
        else:
            file_path = export_all(project_id, point_ids)

        dest = _get_export_dir(export_type)
        file_path = _move_export(file_path, dest)

        _export_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "file_path": file_path,
            "error": "",
        }
    except Exception as e:
        _export_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "file_path": "",
            "error": str(e),
        }


@exports_bp.route(
    "/<int:project_id>/export/status/<export_id>", methods=["GET"]
)
def api_export_status(project_id, export_id):
    """查询导出任务状态"""
    task = _export_tasks.get(export_id)
    if not task:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "导出任务不存在"
        }), 404
    return jsonify({"error": False, "data": task})


@exports_bp.route(
    "/<int:project_id>/export/download/<export_id>", methods=["GET"]
)
def api_export_download(project_id, export_id):
    """下载导出文件"""
    task = _export_tasks.get(export_id)
    if not task:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "导出任务不存在"
        }), 404

    if task["status"] != "completed":
        return jsonify({
            "error": True, "code": "NOT_READY",
            "message": "导出尚未完成"
        }), 400

    file_path = task["file_path"]
    if not os.path.exists(file_path):
        return jsonify({
            "error": True, "code": "FILE_MISSING",
            "message": "导出文件不存在，请重新导出"
        }), 404

    filename = os.path.basename(file_path)
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
    )


@exports_bp.route("/<int:project_id>/export-kml", methods=["GET"])
def api_export_kml(project_id):
    """导出KML文件"""
    try:
        file_path = export_kml(project_id)
        return send_file(file_path, as_attachment=True,
                         download_name=os.path.basename(file_path))
    except ValueError as e:
        return jsonify({"error": True, "code": "EXPORT_FAILED", "message": str(e)}), 400


@exports_bp.route("/<int:project_id>/export-csv", methods=["GET"])
def api_export_csv(project_id):
    """导出CSV文件（奥维通用导入格式）"""
    try:
        file_path = export_csv(project_id)
        return send_file(file_path, as_attachment=True,
                         download_name=os.path.basename(file_path))
    except ValueError as e:
        return jsonify({"error": True, "code": "EXPORT_FAILED", "message": str(e)}), 400


@exports_bp.route("/<int:project_id>/export-kmz", methods=["GET"])
def api_export_kmz(project_id):
    """导出KMZ文件（奥维地图带照片标记）"""
    try:
        file_path = export_kmz(project_id)
        file_path = _move_export(file_path, _get_export_dir("kmz"))
        return send_file(file_path, as_attachment=True,
                         download_name=os.path.basename(file_path))
    except ValueError as e:
        return jsonify({"error": True, "code": "EXPORT_FAILED", "message": str(e)}), 400


# ===== 导出目录管理 =====

@exports_bp.route("/export-dir", methods=["GET"])
def api_get_export_dir():
    dirs = _load_export_dirs()
    return jsonify({"error": False, "data": {
        "kmz": dirs.get("kmz", ""),
        "summary": dirs.get("summary", ""),
        "individual": dirs.get("individual", ""),
    }})


@exports_bp.route("/export-dir", methods=["PUT"])
def api_set_export_dir():
    data = request.get_json(silent=True) or {}
    path = data.get("path", "").strip()
    etype = data.get("type", "all")  # kmz / summary / individual / all

    dirs = _load_export_dirs()
    if not path:
        dirs.pop(etype, None)
        _save_export_dirs(dirs)
        return jsonify({"error": False, "message": "已恢复默认"})
    if not os.path.isdir(path):
        return jsonify({"error": True, "code": "INVALID_PATH", "message": "目录不存在"}, 400)

    dirs[etype] = path
    _save_export_dirs(dirs)
    return jsonify({"error": False, "data": {"type": etype, "path": path}, "message": "已更新"})


@exports_bp.route("/open-export-dir", methods=["POST"])
def api_open_export_dir():
    d = _get_export_dir()
    os.makedirs(d, exist_ok=True)
    try:
        if os.name == "nt":
            _sp.Popen(["explorer", os.path.abspath(d)])
        return jsonify({"error": False})
    except Exception:
        return jsonify({"error": True, "message": "无法打开"}), 500


@exports_bp.route("/pick-folder", methods=["GET"])
def api_pick_folder():
    """打开原生文件夹选择器"""
    try:
        from tkinter import Tk, filedialog
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="选择导出目录")
        root.destroy()
        if path:
            return jsonify({"error": False, "data": {"path": path}})
        return jsonify({"error": False, "data": {"path": ""}})
    except Exception:
        return jsonify({"error": True, "message": "无法打开文件夹选择器"}), 500


def _move_export(src_path, dest_dir):
    import shutil
    if dest_dir == EXPORT_FOLDER:
        return src_path
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(src_path))
    shutil.move(src_path, dest)
    return dest
