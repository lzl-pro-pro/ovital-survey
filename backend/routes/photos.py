"""照片管理 API 路由"""

import os
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
from backend.data_manager import (
    get_point_detail, save_photo, get_photos,
    get_photo, delete_photo
)
from backend.photo_handler import process_photo
from config import (
    PHOTO_FOLDER, MAX_PHOTO_SIZE_BYTES,
    ALLOWED_PHOTO_EXTENSIONS, MAX_PHOTOS_PER_POINT
)

photos_bp = Blueprint("photos", __name__)


@photos_bp.route(
    "/<int:project_id>/points/<int:point_id>/photos", methods=["POST"]
)
def api_upload_photo(project_id, point_id):
    """上传调查点照片"""
    # 验证调查点存在
    point = get_point_detail(point_id)
    if not point:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "调查点不存在"
        }), 404

    # 检查照片数量限制
    existing = get_photos(point_id)
    if len(existing) >= MAX_PHOTOS_PER_POINT:
        return jsonify({
            "error": True, "code": "TOO_MANY_PHOTOS",
            "message": f"每个调查点最多 {MAX_PHOTOS_PER_POINT} 张照片"
        }), 400

    if "file" not in request.files:
        return jsonify({
            "error": True, "code": "NO_FILE",
            "message": "请选择照片文件"
        }), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({
            "error": True, "code": "NO_FILE",
            "message": "文件名为空"
        }), 400

    # 检查扩展名
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        return jsonify({
            "error": True, "code": "INVALID_FORMAT",
            "message": f"不支持的图片格式: {ext}"
        }), 400

    # 检查文件大小
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_PHOTO_SIZE_BYTES:
        return jsonify({
            "error": True, "code": "FILE_TOO_LARGE",
            "message": f"照片大小 {size/1024/1024:.1f}MB 超过限制"
        }), 413

    # 处理照片（存储+缩略图+EXIF）
    caption = request.form.get("caption", "")
    try:
        result = process_photo(file, project_id, point_id)
    except Exception as e:
        return jsonify({
            "error": True, "code": "PHOTO_PROCESS_FAILED",
            "message": f"照片处理失败: {str(e)}"
        }), 500

    # 保存到数据库
    photo_id = save_photo(
        point_id=point_id,
        filename=result["filename"],
        storage_path=result["storage_path"],
        thumbnail_path=result.get("thumbnail_path", ""),
        exif_data=result.get("exif_data"),
        width=result.get("width", 0),
        height=result.get("height", 0),
        file_size=result.get("file_size", 0),
        caption=caption,
        taken_at=result.get("taken_at"),
    )

    return jsonify({
        "error": False,
        "data": {"id": photo_id, **result},
        "message": "照片上传成功"
    }), 201


@photos_bp.route(
    "/<int:project_id>/points/<int:point_id>/photos", methods=["GET"]
)
def api_get_photos(project_id, point_id):
    """获取调查点照片列表"""
    photos = get_photos(point_id)
    return jsonify({"error": False, "data": photos})


@photos_bp.route(
    "/<int:project_id>/points/<int:point_id>/photos/<int:photo_id>",
    methods=["DELETE"]
)
def api_delete_photo(project_id, point_id, photo_id):
    """删除照片"""
    result = delete_photo(photo_id)
    if not result:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "照片不存在"
        }), 404

    # 删除实际文件
    import config
    for path_key in ["storage_path", "thumbnail_path"]:
        if result.get(path_key):
            full_path = os.path.join(config.BASE_DIR, result[path_key])
            if os.path.exists(full_path):
                os.remove(full_path)

    return jsonify({"error": False, "message": "照片已删除"})


@photos_bp.route(
    "/<int:project_id>/points/<int:point_id>/photos/<int:photo_id>/image",
    methods=["GET"]
)
def api_serve_photo(project_id, point_id, photo_id):
    """提供照片原图"""
    photo = get_photo(photo_id)
    if not photo:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "照片不存在"
        }), 404

    import config
    full_path = os.path.join(config.BASE_DIR, photo["storage_path"])
    if not os.path.exists(full_path):
        return jsonify({
            "error": True, "code": "FILE_MISSING",
            "message": "照片文件缺失"
        }), 404

    return send_file(full_path)


@photos_bp.route(
    "/<int:project_id>/points/<int:point_id>/photos/<int:photo_id>/thumbnail",
    methods=["GET"]
)
def api_serve_thumbnail(project_id, point_id, photo_id):
    """提供照片缩略图"""
    photo = get_photo(photo_id)
    if not photo:
        return jsonify({
            "error": True, "code": "NOT_FOUND",
            "message": "照片不存在"
        }), 404

    import config
    thumb_path = photo.get("thumbnail_path", "")
    if thumb_path:
        full_path = os.path.join(config.BASE_DIR, thumb_path)
    else:
        full_path = os.path.join(config.BASE_DIR, photo["storage_path"])

    if not os.path.exists(full_path):
        return jsonify({
            "error": True, "code": "FILE_MISSING",
            "message": "照片文件缺失"
        }), 404

    return send_file(full_path)
