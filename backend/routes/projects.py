"""项目管理 API 路由"""

import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from backend.data_manager import (
    create_project, get_project, list_projects, update_project,
    delete_project, update_cad_info
)
from backend.cad_parser import parse_cad_file
from config import (
    UPLOAD_FOLDER, MAX_CAD_SIZE_BYTES, ALLOWED_CAD_EXTENSIONS
)

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("", methods=["POST"])
def api_create_project():
    """创建新项目"""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({
            "error": True, "code": "VALIDATION_ERROR",
            "message": "项目名称不能为空"
        }), 400

    project_id = create_project(
        name=name,
        description=data.get("description", ""),
        coord_system=data.get("coord_system", "EPSG:4544"),
    )
    project = get_project(project_id)
    return jsonify({"error": False, "data": project}), 201


@projects_bp.route("", methods=["GET"])
def api_list_projects():
    """列出所有项目"""
    projects = list_projects()
    return jsonify({"error": False, "data": projects})


@projects_bp.route("/<int:project_id>", methods=["GET"])
def api_get_project(project_id):
    """获取项目详情"""
    project = get_project(project_id)
    if not project:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "项目不存在"
        }), 404
    return jsonify({"error": False, "data": project})


@projects_bp.route("/<int:project_id>", methods=["PUT"])
def api_update_project(project_id):
    """更新项目"""
    data = request.get_json(silent=True) or {}
    update_project(project_id, **data)
    project = get_project(project_id)
    return jsonify({"error": False, "data": project})


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
def api_delete_project(project_id):
    """删除项目"""
    project = get_project(project_id)
    if not project:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "项目不存在"
        }), 404
    delete_project(project_id)
    return jsonify({"error": False, "message": "项目已删除"})


@projects_bp.route("/<int:project_id>/upload-cad", methods=["POST"])
def api_upload_cad(project_id):
    """上传CAD文件并解析"""
    project = get_project(project_id)
    if not project:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "项目不存在"
        }), 404

    if "file" not in request.files:
        return jsonify({
            "error": True, "code": "NO_FILE",
            "message": "请选择要上传的CAD文件"
        }), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({
            "error": True, "code": "NO_FILE",
            "message": "文件名为空"
        }), 400

    # 检查扩展名
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_CAD_EXTENSIONS:
        return jsonify({
            "error": True, "code": "INVALID_FORMAT",
            "message": f"不支持的文件格式: {ext}，支持: {', '.join(ALLOWED_CAD_EXTENSIONS)}"
        }), 400

    # 保存文件（保留原始扩展名，防止中文名被裁掉扩展名）
    original_ext = os.path.splitext(file.filename)[1].lower()
    safe_base = secure_filename(os.path.splitext(file.filename)[0]) or "cad_file"
    from backend.utils import sanitize_filename
    safe_name = sanitize_filename(safe_base + original_ext)
    project_dir = os.path.join(UPLOAD_FOLDER, str(project_id))
    os.makedirs(project_dir, exist_ok=True)
    file_path = os.path.join(project_dir, safe_name)

    # 检查并限制文件大小
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_CAD_SIZE_BYTES:
        return jsonify({
            "error": True, "code": "FILE_TOO_LARGE",
            "message": f"文件大小 {size/1024/1024:.1f}MB 超过限制 {MAX_CAD_SIZE_BYTES/1024/1024:.0f}MB"
        }), 413

    file.save(file_path)
    current_app.logger.info(f"CAD file saved: {file_path}")

    # 更新项目CAD信息
    file_type = ext.lstrip(".")
    update_cad_info(project_id, file_path, file_type)

    # 解析CAD文件
    try:
        result = parse_cad_file(file_path, project_id)
        return jsonify({"error": False, "data": result})
    except Exception as e:
        current_app.logger.error(f"CAD parse error: {str(e)}")
        return jsonify({
            "error": True, "code": "CAD_PARSE_FAILED",
            "message": f"CAD文件解析失败: {str(e)}"
        }), 500


@projects_bp.route("/<int:project_id>/cad-info", methods=["GET"])
def api_cad_info(project_id):
    """获取CAD解析信息"""
    project = get_project(project_id)
    if not project:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "项目不存在"
        }), 404

    from backend.data_manager import get_annotations
    annotations = get_annotations(project_id, per_page=1)
    total = annotations["total"] if annotations else 0

    return jsonify({
        "error": False,
        "data": {
            "cad_file_path": project.get("cad_file_path", ""),
            "cad_file_type": project.get("cad_file_type", ""),
            "annotation_count": total,
            "coord_system": project.get("coord_system", "local"),
        }
    })
