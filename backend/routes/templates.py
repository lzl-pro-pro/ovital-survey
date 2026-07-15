"""字段模板管理 API 路由"""

from flask import Blueprint, request, jsonify
from backend.data_manager import (
    get_templates, get_template, create_template,
    delete_template
)

templates_bp = Blueprint("templates", __name__)


@templates_bp.route("", methods=["GET"])
def api_list_templates():
    """列出所有模板"""
    templates = get_templates()
    return jsonify({"error": False, "data": templates})


@templates_bp.route("/<int:template_id>", methods=["GET"])
def api_get_template(template_id):
    """获取模板详情（含字段）"""
    template = get_template(template_id)
    if not template:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "模板不存在"
        }), 404
    return jsonify({"error": False, "data": template})


@templates_bp.route("", methods=["POST"])
def api_create_template():
    """创建新模板"""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    fields = data.get("fields", [])

    if not name:
        return jsonify({
            "error": True, "code": "VALIDATION_ERROR",
            "message": "模板名称不能为空"
        }), 400

    if not fields:
        return jsonify({
            "error": True, "code": "VALIDATION_ERROR",
            "message": "模板字段不能为空"
        }), 400

    try:
        template_id = create_template(name, fields)
        template = get_template(template_id)
        return jsonify({"error": False, "data": template}), 201
    except Exception as e:
        return jsonify({
            "error": True, "code": "CREATE_FAILED",
            "message": f"创建模板失败: {str(e)}"
        }), 400


@templates_bp.route("/<int:template_id>", methods=["DELETE"])
def api_delete_template(template_id):
    """删除模板"""
    result = delete_template(template_id)
    if not result:
        return jsonify({
            "error": True, "code": "FORBIDDEN",
            "message": "默认模板不可删除"
        }), 403
    return jsonify({"error": False, "message": "模板已删除"})
