"""调查点管理 API 路由"""

from flask import Blueprint, request, jsonify
from backend.data_manager import (
    get_survey_points, get_point_detail, update_point_location,
    update_point_status, update_point_marker, save_point_records,
    get_project_stats, get_default_template,
    get_used_project_names, batch_set_project_name, batch_set_investigator,
)

points_bp = Blueprint("points", __name__)


@points_bp.route("/<int:project_id>/points", methods=["GET"])
def api_get_points(project_id):
    """获取调查点列表"""
    status = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 100, type=int)

    result = get_survey_points(project_id, status=status,
                               page=page, per_page=per_page)
    return jsonify({"error": False, "data": result})


@points_bp.route("/<int:project_id>/points/<int:point_id>", methods=["GET"])
def api_get_point(project_id, point_id):
    """获取调查点详情"""
    point = get_point_detail(point_id)
    if not point:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "调查点不存在"
        }), 404
    return jsonify({"error": False, "data": point})


@points_bp.route(
    "/<int:project_id>/points/<int:point_id>", methods=["PUT"]
)
def api_update_point(project_id, point_id):
    """更新调查点（状态、位置、调查记录）"""
    data = request.get_json(silent=True) or {}

    # 更新位置
    if "latitude" in data and "longitude" in data:
        update_point_location(
            point_id,
            data["latitude"],
            data["longitude"],
            data.get("altitude", 0)
        )

    # 更新状态
    if "status" in data:
        update_point_status(point_id, data["status"])

    # 更新奥维标记
    if "ovital_marker_id" in data:
        update_point_marker(point_id, data["ovital_marker_id"])

    # 更新调查记录
    if "records" in data:
        save_point_records(point_id, data["records"])

    # 返回更新后的详情
    point = get_point_detail(point_id)
    return jsonify({"error": False, "data": point})


@points_bp.route(
    "/<int:project_id>/points/<int:point_id>/location", methods=["PUT"]
)
def api_update_point_location(project_id, point_id):
    """单独更新调查点GPS位置"""
    data = request.get_json(silent=True) or {}
    lat = data.get("latitude")
    lng = data.get("longitude")
    if lat is None or lng is None:
        return jsonify({
            "error": True, "code": "VALIDATION_ERROR",
            "message": "需要提供经纬度"
        }), 400

    update_point_location(point_id, lat, lng, data.get("altitude", 0))
    return jsonify({"error": False, "message": "位置更新成功"})


@points_bp.route("/<int:project_id>/points/<int:point_id>/records", methods=["PUT"])
def api_save_records(project_id, point_id):
    """保存调查记录"""
    data = request.get_json(silent=True) or {}
    records = data.get("records", [])
    if not records:
        return jsonify({
            "error": True, "code": "VALIDATION_ERROR",
            "message": "请提供调查记录数据"
        }), 400

    save_point_records(point_id, records)
    return jsonify({"error": False, "message": "调查记录已保存"})


@points_bp.route("/project-names", methods=["GET"])
def api_project_names():
    """获取所有历史工程名称"""
    names = get_used_project_names()
    return jsonify({"error": False, "data": names})


@points_bp.route("/<int:project_id>/batch-project-name", methods=["PUT"])
def api_batch_project_name(project_id):
    """统一设置项目下所有调查点的工程名称"""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({
            "error": True, "code": "VALIDATION_ERROR",
            "message": "工程名称不能为空"
        }), 400
    count = batch_set_project_name(project_id, name)
    return jsonify({
        "error": False,
        "data": {"count": count},
        "message": f"已为 {count} 个调查点设置工程名称"
    })


@points_bp.route("/<int:project_id>/batch-investigator", methods=["PUT"])
def api_batch_investigator(project_id):
    """统一设置项目下所有调查点的调查人"""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({
            "error": True, "code": "VALIDATION_ERROR",
            "message": "调查人不能为空"
        }), 400
    count = batch_set_investigator(project_id, name)
    return jsonify({
        "error": False,
        "data": {"count": count},
        "message": f"已为 {count} 个调查点设置调查人"
    })


@points_bp.route("/<int:project_id>/stats", methods=["GET"])
def api_project_stats(project_id):
    """获取项目统计信息"""
    stats = get_project_stats(project_id)
    return jsonify({"error": False, "data": stats})
