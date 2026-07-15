"""照片处理模块 - 存储、缩略图、EXIF提取"""

import os
import io
import uuid
from datetime import datetime
from PIL import Image, ExifTags
from werkzeug.utils import secure_filename
from config import (
    PHOTO_FOLDER, THUMBNAIL_SIZE, MAX_PHOTO_DIMENSION, BASE_DIR
)


def process_photo(file_storage, project_id, point_id):
    """
    处理上传的照片：保存原图、生成缩略图、提取EXIF

    Args:
        file_storage: Flask FileStorage 对象
        project_id: 项目ID
        point_id: 调查点ID

    Returns:
        dict: {filename, storage_path, thumbnail_path, exif_data, width, height, file_size, taken_at}
    """
    # 安全文件名
    original_name = secure_filename(file_storage.filename or "photo.jpg")
    name, ext = os.path.splitext(original_name)
    if not ext:
        ext = ".jpg"
    unique_name = f"{uuid.uuid4().hex}_{name}{ext}"

    # 存储目录
    point_dir = os.path.join(PHOTO_FOLDER, str(project_id), str(point_id))
    os.makedirs(point_dir, exist_ok=True)

    # 读取图片数据
    file_storage.seek(0)
    img_data = file_storage.read()

    # 用Pillow打开处理
    try:
        img = Image.open(io.BytesIO(img_data))
    except Exception as e:
        raise ValueError(f"无法读取图片文件，文件可能已损坏: {str(e)}")

    # 提取EXIF
    exif_data = _extract_exif(img)

    # 如果图片过大，缩小
    width, height = img.size
    if max(width, height) > MAX_PHOTO_DIMENSION:
        ratio = MAX_PHOTO_DIMENSION / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        width, height = new_size

    # 保存原图
    storage_path = os.path.join(point_dir, unique_name)
    img.save(storage_path, quality=90, optimize=True)
    file_size = os.path.getsize(storage_path)

    # 生成缩略图
    thumb_name = f"thumb_{unique_name}"
    thumb_path = os.path.join(point_dir, thumb_name)
    img_copy = img.copy()
    img_copy.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    img_copy.save(thumb_path, quality=80, optimize=True)

    # 获取拍摄时间
    taken_at = exif_data.get("DateTimeOriginal", "")
    if taken_at:
        try:
            dt = datetime.strptime(taken_at, "%Y:%m:%d %H:%M:%S")
            taken_at = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            taken_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        taken_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 转为相对于BASE_DIR的路径
    rel_storage = os.path.relpath(storage_path, BASE_DIR)
    rel_thumb = os.path.relpath(thumb_path, BASE_DIR)

    return {
        "filename": unique_name,
        "storage_path": rel_storage,
        "thumbnail_path": rel_thumb,
        "exif_data": exif_data,
        "width": width,
        "height": height,
        "file_size": file_size,
        "taken_at": taken_at,
    }


def _extract_exif(img):
    """提取图片EXIF信息"""
    exif_data = {}
    try:
        raw_exif = img._getexif()
        if not raw_exif:
            return exif_data

        # EXIF标签名映射
        for tag_id, value in raw_exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            # 跳过二进制数据
            if isinstance(value, bytes):
                continue
            if isinstance(value, (int, float, str)):
                exif_data[tag_name] = str(value)

        # GPS信息
        if hasattr(img, '_getexif'):
            gps_info = {}
            for key in raw_exif:
                if ExifTags.TAGS.get(key) == 'GPSInfo':
                    gps_data = raw_exif[key]
                    if gps_data:
                        try:
                            for gps_key in gps_data:
                                gps_tag = ExifTags.GPSTAGS.get(gps_key, str(gps_key))
                                gps_info[gps_tag] = str(gps_data[gps_key])
                            exif_data["GPSInfo"] = gps_info
                        except Exception:
                            pass

    except Exception:
        pass

    return exif_data


def generate_thumbnail(source_path, target_path, size=(300, 300)):
    """对已有图片生成缩略图"""
    try:
        img = Image.open(source_path)
        img.thumbnail(size, Image.LANCZOS)
        img.save(target_path, quality=80, optimize=True)
        return True
    except Exception:
        return False


def delete_photo_files(photo_record):
    """删除照片物理文件"""
    paths = [
        photo_record.get("storage_path", ""),
        photo_record.get("thumbnail_path", ""),
    ]
    for path in paths:
        if path:
            full_path = os.path.join(BASE_DIR, path)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except OSError:
                    pass
