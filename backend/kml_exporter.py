"""KML导出模块 - 将调查点导出为奥维可导入的KML文件"""

import os
from datetime import datetime
from backend.data_manager import get_project, get_survey_points
from config import EXPORT_FOLDER


def export_kml(project_id):
    """将项目的所有调查点导出为KML文件（奥维地图可直接导入）"""
    project = get_project(project_id)
    if not project:
        raise ValueError("项目不存在")

    result = get_survey_points(project_id, per_page=10000)
    points = result["items"]

    if not points:
        raise ValueError("没有可导出的调查点")

    # 状态颜色映射（奥维图标ID）
    icon_map = {
        "pending": "1",        # 红色
        "in_progress": "2",    # 黄色
        "surveyed": "3",       # 绿色
        "skipped": "4",        # 灰色
    }

    status_label = {
        "pending": "待调查",
        "in_progress": "进行中",
        "surveyed": "已完成",
        "skipped": "已跳过",
    }

    kml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        f'  <name>{_escape(project["name"])} - 调查点</name>',
        f'  <description>导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}</description>',
    ]

    # 按状态分文件夹
    for status in ["pending", "in_progress", "surveyed", "skipped"]:
        status_points = [p for p in points if p["status"] == status]
        if not status_points:
            continue

        kml_parts.append(f'  <Folder>')
        kml_parts.append(f'    <name>{status_label[status]} ({len(status_points)}个)</name>')
        kml_parts.append(f'    <open>1</open>')

        for point in status_points:
            lat = point.get("latitude", 0) or 0
            lng = point.get("longitude", 0) or 0
            number = _escape(point["point_number"] or "-")
            icon = icon_map.get(status, "1")

            # 跳过没有GPS坐标的点
            if lat == 0 and lng == 0:
                continue

            kml_parts.append('    <Placemark>')
            kml_parts.append(f'      <name>{number}</name>')
            kml_parts.append(f'      <description><![CDATA['
                             f'编号: {number}<br/>'
                             f'状态: {status_label[status]}<br/>'
                             f'经度: {lng:.6f}<br/>'
                             f'纬度: {lat:.6f}<br/>'
                             f']]></description>')
            kml_parts.append(f'      <styleUrl>#icon-{icon}</styleUrl>')
            kml_parts.append('      <Point>')
            kml_parts.append(f'        <coordinates>{lng},{lat},0</coordinates>')
            kml_parts.append('      </Point>')
            kml_parts.append('    </Placemark>')

        kml_parts.append('  </Folder>')

    # 样式定义
    icon_colors = {
        "1": ("ff0000ff", "待调查"),     # 红色
        "2": ("ff00aaff", "进行中"),     # 黄色
        "3": ("ff00ff00", "已完成"),     # 绿色
        "4": ("ff888888", "已跳过"),     # 灰色
    }
    for iid, (color, label) in icon_colors.items():
        kml_parts.append(f'  <Style id="icon-{iid}">')
        kml_parts.append('    <IconStyle>')
        kml_parts.append(f'      <color>{color}</color>')
        kml_parts.append(f'      <scale>1.0</scale>')
        kml_parts.append('      <Icon>')
        kml_parts.append('        <href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href>')
        kml_parts.append('      </Icon>')
        kml_parts.append('    </IconStyle>')
        kml_parts.append('    <LabelStyle>')
        kml_parts.append(f'      <color>{color}</color>')
        kml_parts.append('      <scale>0.8</scale>')
        kml_parts.append('    </LabelStyle>')
        kml_parts.append('  </Style>')

    kml_parts.append('</Document>')
    kml_parts.append('</kml>')

    # 保存文件
    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"调查点_{project['name']}_{timestamp}.kml"
    filepath = os.path.join(EXPORT_FOLDER, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(kml_parts))

    return filepath


def _escape(text):
    """转义XML特殊字符"""
    text = str(text or "")
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text
