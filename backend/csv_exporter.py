"""CSV导出模块 - 奥维通用导入格式"""

import os
import csv
from datetime import datetime
from backend.data_manager import get_project, get_survey_points, get_point_detail
from config import EXPORT_FOLDER


def export_csv(project_id):
    """导出CSV（奥维地图可直接导入，描述含备注）"""
    project = get_project(project_id)
    if not project:
        raise ValueError("项目不存在")

    result = get_survey_points(project_id, per_page=10000)
    points = result["items"]

    if not points:
        raise ValueError("没有可导出的调查点")

    status_label = {
        "pending": "待调查",
        "in_progress": "进行中",
        "surveyed": "已完成",
        "skipped": "已跳过",
    }

    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"调查点_{project['name']}_{timestamp}.csv"
    filepath = os.path.join(EXPORT_FOLDER, filename)

    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)

        writer.writerow(["经度", "纬度", "名称", "图标", "描述", "文件夹"])

        for point in points:
            lat = point.get("latitude", 0) or 0
            lng = point.get("longitude", 0) or 0
            number = point.get("point_number", "")

            if lat == 0 and lng == 0:
                continue

            icon = {"pending": "1", "in_progress": "2",
                    "surveyed": "3", "skipped": "4"}.get(
                point.get("status", "pending"), "1"
            )

            # 查备注
            remark = ""
            try:
                detail = get_point_detail(point["id"])
                if detail and detail.get("records"):
                    for r in detail["records"]:
                        if r.get("field_key") == "remarks" and r.get("field_value"):
                            remark = r["field_value"]
                            break
            except Exception:
                pass

            status = status_label.get(point.get("status", "pending"), "")
            desc = f"{number} | {status}"
            if remark:
                desc += f" | {remark[:100]}"

            folder = status

            writer.writerow([lng, lat, number, icon, desc, folder])

    return filepath
