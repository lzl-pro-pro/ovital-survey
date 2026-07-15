"""标注管理 API 路由"""

from flask import Blueprint, request, jsonify
from backend.data_manager import (
    get_annotations, update_annotation, confirm_annotations
)

annotations_bp = Blueprint("annotations", __name__)


@annotations_bp.route("/<int:project_id>/annotations", methods=["GET"])
def api_get_annotations(project_id):
    """获取标注列表"""
    confirmed = request.args.get("confirmed")
    if confirmed is not None:
        confirmed = confirmed.lower() == "true"
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    result = get_annotations(project_id, confirmed=confirmed,
                             page=page, per_page=per_page)
    return jsonify({"error": False, "data": result})


@annotations_bp.route(
    "/<int:project_id>/annotations/<int:annotation_id>", methods=["PUT"]
)
def api_update_annotation(project_id, annotation_id):
    """更新单个标注"""
    data = request.get_json(silent=True) or {}
    update_annotation(annotation_id, **data)
    return jsonify({"error": False, "message": "更新成功"})


@annotations_bp.route("/<int:project_id>/annotations/confirm", methods=["POST"])
def api_confirm_annotations(project_id):
    """确认标注并创建调查点"""
    data = request.get_json(silent=True) or {}
    annotation_ids = data.get("annotation_ids", [])
    point_labels = data.get("point_labels", [])

    if not annotation_ids:
        return jsonify({
            "error": True, "code": "VALIDATION_ERROR",
            "message": "请选择至少一个标注"
        }), 400

    point_ids = confirm_annotations(annotation_ids, point_labels)
    return jsonify({
        "error": False,
        "data": {"point_ids": point_ids, "count": len(point_ids)},
        "message": f"已创建 {len(point_ids)} 个调查点"
    })
