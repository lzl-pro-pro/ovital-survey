"""KMZ导出模块 - 带照片的奥维地图标记"""

import os
import zipfile
from datetime import datetime
from backend.data_manager import get_project, get_survey_points, get_point_detail
from config import EXPORT_FOLDER, BASE_DIR


def export_kmz(project_id):
    """导出KMZ文件（KML+照片），奥维可直接导入并查看照片"""
    project = get_project(project_id)
    if not project:
        raise ValueError("项目不存在")

    result = get_survey_points(project_id, per_page=10000)
    points = result["items"]

    if not points:
        raise ValueError("没有可导出的调查点")

    status_label = {"pending": "待调查", "in_progress": "进行中",
                    "surveyed": "已完成", "skipped": "已跳过"}

    images_added = {}  # 去重：同名照片只加一次
    kml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        f'  <name>{_escape(project["name"])} - 调查点</name>',
    ]

    # 图钉图标样式 — 直接用彩色图钉，不用颜色叠加（避免奥维误判为相机图标）
    # KML颜色格式: aabbggrr (仅用于文字标签)
    icon_styles = {
        "pending":     {"label_color": "ff0000ff", "icon": "http://maps.google.com/mapfiles/kml/pushpin/red-pushpin.png"},
        "in_progress": {"label_color": "ff00aaff", "icon": "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"},
        "surveyed":    {"label_color": "ff00ff00", "icon": "http://maps.google.com/mapfiles/kml/pushpin/grn-pushpin.png"},
        "skipped":     {"label_color": "ff888888", "icon": "http://maps.google.com/mapfiles/kml/pushpin/wht-pushpin.png"},
    }
    for sid, style in icon_styles.items():
        icon_url = style["icon"]
        label_color = style["label_color"]
        kml_parts.append(f'  <Style id="s_{sid}">')
        kml_parts.append(f'    <IconStyle><scale>1.2</scale>'
                         f'<Icon><href>{icon_url}</href></Icon></IconStyle>')
        kml_parts.append(f'    <LabelStyle><color>{label_color}</color><scale>0.9</scale></LabelStyle>')
        kml_parts.append(f'  </Style>')

    photo_count = 0
    img_files = []  # (filename, data) for KMZ

    for point in points:
        lat = point.get("latitude", 0) or 0
        lng = point.get("longitude", 0) or 0
        if lat == 0 and lng == 0:
            continue

        number = _escape(point.get("point_number", ""))
        status = point.get("status", "pending")
        detail = get_point_detail(point["id"]) or {}
        records = {r["field_key"]: r["field_value"] for r in detail.get("records", [])}
        photos = detail.get("photos", [])

        # 构建描述HTML（照片作为附件，不在描述中嵌入避免奥维显示相机图标）
        remark = records.get("remarks", "")
        location = records.get("location_desc", "")
        desc_parts = [
            f"<b>{number}</b><br/>",
            f"状态: {status_label.get(status, status)}<br/>",
            f"经度: {lng:.6f}  纬度: {lat:.6f}<br/>",
        ]
        if remark:
            desc_parts.append(f"备注: {remark}<br/>")
        if location:
            desc_parts.append(f"位置: {location}<br/>")

        # 照片放入 KMZ 附件，描述中只显示数量
        if photos:
            valid_count = 0
            for pi, photo in enumerate(photos[:10]):
                thumb_path = photo.get("thumbnail_path", "") or photo.get("storage_path", "")
                if not thumb_path:
                    continue
                full_path = os.path.normpath(os.path.join(BASE_DIR, str(thumb_path)))
                if not os.path.isfile(full_path):
                    continue
                img_name = f"photos/{point['id']}_{pi}.jpg"
                if img_name not in images_added:
                    with open(full_path, "rb") as f:
                        img_files.append((img_name, f.read()))
                    images_added[img_name] = True
                    photo_count += 1
                    valid_count += 1
            if valid_count > 0:
                desc_parts.append(f"<br/>📷 现场照片: {valid_count}张（见KMZ附件）")

        desc = "".join(desc_parts)

        kml_parts.append('  <Placemark>')
        kml_parts.append(f'    <name>{number}</name>')
        kml_parts.append(f'    <description><![CDATA[{desc}]]></description>')
        kml_parts.append(f'    <styleUrl>#s_{status}</styleUrl>')
        kml_parts.append('    <Point>')
        kml_parts.append(f'      <coordinates>{lng},{lat},0</coordinates>')
        kml_parts.append('    </Point>')
        kml_parts.append('  </Placemark>')

    kml_parts.append('</Document>')
    kml_parts.append('</kml>')

    # 打包 KMZ
    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"调查点_{project['name']}_{timestamp}.kmz"
    filepath = os.path.join(EXPORT_FOLDER, filename)

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", "\n".join(kml_parts))
        for img_name, img_data in img_files:
            zf.writestr(img_name, img_data)

    return filepath


def _escape(text):
    text = str(text or "")
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text
