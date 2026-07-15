"""数据访问层：SQLite CRUD 操作"""

import sqlite3
import json
import os
from contextlib import contextmanager
from config import DATABASE_PATH


@contextmanager
def get_db():
    """获取数据库连接的上下文管理器，自动处理提交/回滚"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================== 项目管理 ====================

def create_project(name, description="", coord_system="EPSG:4544"):
    """创建新项目，返回项目ID"""
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO projects (name, description, coord_system) VALUES (?, ?, ?)",
            (name, description, coord_system)
        )
        return cursor.lastrowid


def get_project(project_id):
    """获取单个项目详情（含统计信息）"""
    with get_db() as db:
        project = db.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        if not project:
            return None

        result = dict(project)
        result["transform_params"] = json.loads(
            result.get("transform_params", "{}")
        )

        # 统计信息
        result["annotation_count"] = db.execute(
            "SELECT COUNT(*) FROM cad_annotations WHERE project_id=?",
            (project_id,)
        ).fetchone()[0]

        result["point_count"] = db.execute(
            "SELECT COUNT(*) FROM survey_points WHERE project_id=?",
            (project_id,)
        ).fetchone()[0]

        result["surveyed_count"] = db.execute(
            "SELECT COUNT(*) FROM survey_points WHERE project_id=? AND status='surveyed'",
            (project_id,)
        ).fetchone()[0]

        return result


def list_projects():
    """列出所有项目"""
    with get_db() as db:
        projects = db.execute(
            "SELECT *, (SELECT COUNT(*) FROM survey_points sp WHERE sp.project_id=p.id) as point_count,"
            " (SELECT COUNT(*) FROM survey_points sp WHERE sp.project_id=p.id AND sp.status='surveyed') as surveyed_count "
            "FROM projects p ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(p) for p in projects]


def update_project(project_id, **kwargs):
    """更新项目元数据"""
    allowed = {"name", "description", "coord_system", "transform_params", "template_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}

    if not updates:
        return False

    if "transform_params" in updates:
        updates["transform_params"] = json.dumps(
            updates["transform_params"], ensure_ascii=False
        )

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values())

    with get_db() as db:
        db.execute(
            f"UPDATE projects SET {set_clause}, updated_at=datetime('now','localtime') "
            f"WHERE id=?",
            values + [project_id]
        )
        return True


def delete_project(project_id):
    """删除项目及所有关联数据（级联删除由FK处理）"""
    with get_db() as db:
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return True


def update_cad_info(project_id, file_path, file_type):
    """更新项目的CAD文件信息"""
    with get_db() as db:
        db.execute(
            "UPDATE projects SET cad_file_path=?, cad_file_type=?, "
            "updated_at=datetime('now','localtime') WHERE id=?",
            (file_path, file_type, project_id)
        )


# ==================== 标注管理 ====================

def save_annotations(project_id, annotations):
    """批量保存CAD标注"""
    with get_db() as db:
        db.executemany(
            """INSERT INTO cad_annotations
               (project_id, text_content, matched_label, cad_x, cad_y, cad_z,
                entity_type, layer_name, entity_handle)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    project_id,
                    a.get("text_content", ""),
                    a.get("matched_label", ""),
                    a.get("cad_x", 0),
                    a.get("cad_y", 0),
                    a.get("cad_z", 0),
                    a.get("entity_type", ""),
                    a.get("layer_name", ""),
                    a.get("entity_handle", ""),
                )
                for a in annotations
            ]
        )
        return db.execute(
            "SELECT COUNT(*) FROM cad_annotations WHERE project_id=? AND is_confirmed=0",
            (project_id,)
        ).fetchone()[0]


def get_annotations(project_id, confirmed=None, page=1, per_page=50):
    """分页获取标注列表"""
    with get_db() as db:
        where = "project_id=?"
        params = [project_id]
        if confirmed is not None:
            where += " AND is_confirmed=?"
            params.append(1 if confirmed else 0)

        total = db.execute(
            f"SELECT COUNT(*) FROM cad_annotations WHERE {where}", params
        ).fetchone()[0]

        offset = (page - 1) * per_page
        rows = db.execute(
            f"SELECT * FROM cad_annotations WHERE {where} "
            f"ORDER BY id LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": [dict(r) for r in rows],
        }


def update_annotation(annotation_id, **kwargs):
    """更新单个标注"""
    allowed = {"matched_label", "text_content", "is_confirmed"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_db() as db:
        db.execute(
            f"UPDATE cad_annotations SET {set_clause} WHERE id=?",
            list(updates.values()) + [annotation_id]
        )
        return True


def confirm_annotations(annotation_ids, point_labels=None):
    """确认标注并创建调查点，自动将CAD投影坐标转为WGS84经纬度"""
    from config import DEFAULT_CAD_CRS
    from pyproj import Transformer

    # 获取项目CRS设置
    project_id = None
    with get_db() as db:
        for aid in annotation_ids[:1]:
            ann = db.execute(
                "SELECT project_id FROM cad_annotations WHERE id=?", (aid,)
            ).fetchone()
            if ann:
                project_id = ann["project_id"]
                break
        if project_id:
            proj = db.execute(
                "SELECT coord_system FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            crs = (proj["coord_system"] if proj and proj["coord_system"] and proj["coord_system"] != "local"
                   else DEFAULT_CAD_CRS)
        else:
            crs = DEFAULT_CAD_CRS

    # 坐标转换器
    try:
        transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    except Exception:
        transformer = None

    with get_db() as db:
        point_ids = []
        for i, aid in enumerate(annotation_ids):
            ann = db.execute(
                "SELECT * FROM cad_annotations WHERE id=?", (aid,)
            ).fetchone()
            if not ann:
                continue

            label = (
                point_labels[i] if point_labels and i < len(point_labels)
                else ann["matched_label"] or ann["text_content"]
            )

            # 投影坐标 → 经纬度
            cad_x, cad_y, cad_z = ann["cad_x"], ann["cad_y"], ann["cad_z"] or 0
            if transformer and cad_x != 0 and cad_y != 0:
                try:
                    lng, lat = transformer.transform(cad_x, cad_y)
                except Exception:
                    lng, lat = cad_x, cad_y  # 转换失败就用原值
            else:
                lng, lat = cad_x, cad_y

            cursor = db.execute(
                """INSERT INTO survey_points
                   (project_id, point_number, cad_x, cad_y, latitude, longitude, altitude,
                    annotation_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (ann["project_id"], label, cad_x, cad_y, lat, lng, cad_z, aid)
            )
            point_id = cursor.lastrowid
            point_ids.append(point_id)

            db.execute(
                "UPDATE cad_annotations SET is_confirmed=1, matched_point_id=? "
                "WHERE id=?",
                (point_id, aid)
            )

            # 从CAD文字中提取备注（/后面的内容）
            text_content = ann["text_content"] or ""
            remark = ""
            if " / " in text_content:
                remark = text_content.split(" / ", 1)[1].strip()
            elif "／" in text_content:
                remark = text_content.split("／", 1)[1].strip()

            # 自动填入备注
            if remark:
                db.execute(
                    "INSERT OR REPLACE INTO survey_records "
                    "(point_id, field_key, field_label, field_value, field_type, field_order) "
                    "VALUES (?, 'remarks', '备注', ?, 'multiline', 11)",
                    (point_id, remark)
                )

        return point_ids


# ==================== 调查点管理 ====================

def get_survey_points(project_id, status=None, page=1, per_page=100):
    """分页获取调查点列表"""
    with get_db() as db:
        where = "project_id=?"
        params = [project_id]
        if status:
            where += " AND status=?"
            params.append(status)

        total = db.execute(
            f"SELECT COUNT(*) FROM survey_points WHERE {where}", params
        ).fetchone()[0]

        offset = (page - 1) * per_page
        rows = db.execute(
            f"""SELECT sp.*,
                (SELECT COUNT(*) FROM photos WHERE point_id=sp.id) as photo_count
                FROM survey_points sp
                WHERE {where}
                ORDER BY
                    ROUND(sp.cad_y / 2000) DESC,
                    ROUND(sp.cad_x / 2000),
                    CAST(substr(sp.point_number,
                        length(sp.point_number) -
                        length(trim(sp.point_number, '0123456789')) + 1) AS INTEGER),
                    sp.point_number COLLATE NOCASE
                LIMIT ? OFFSET ?""",
            params + [per_page, offset]
        ).fetchall()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": [dict(r) for r in rows],
        }


def get_point_detail(point_id):
    """获取调查点详情（含调查记录和照片）"""
    with get_db() as db:
        point = db.execute(
            "SELECT * FROM survey_points WHERE id=?", (point_id,)
        ).fetchone()
        if not point:
            return None

        result = dict(point)

        # 调查记录（按字段顺序排列）
        records = db.execute(
            "SELECT * FROM survey_records WHERE point_id=? ORDER BY field_order",
            (point_id,)
        ).fetchall()
        result["records"] = [dict(r) for r in records]

        # 照片列表
        photos = db.execute(
            "SELECT * FROM photos WHERE point_id=? ORDER BY created_at DESC",
            (point_id,)
        ).fetchall()
        result["photos"] = []
        for p in photos:
            pd = dict(p)
            pd["exif_data"] = json.loads(pd.get("exif_data", "{}"))
            result["photos"].append(pd)

        return result


def update_point_location(point_id, lat, lng, alt=0):
    """更新调查点GPS坐标"""
    with get_db() as db:
        db.execute(
            "UPDATE survey_points SET latitude=?, longitude=?, altitude=? WHERE id=?",
            (lat, lng, alt, point_id)
        )


def update_point_status(point_id, status):
    """更新调查点状态"""
    with get_db() as db:
        if status == "surveyed":
            db.execute(
                "UPDATE survey_points SET status=?, "
                "surveyed_at=datetime('now','localtime') WHERE id=?",
                (status, point_id)
            )
        else:
            db.execute(
                "UPDATE survey_points SET status=? WHERE id=?", (status, point_id)
            )


def update_point_marker(point_id, marker_id):
    """更新奥维地图标记ID"""
    with get_db() as db:
        db.execute(
            "UPDATE survey_points SET ovital_marker_id=? WHERE id=?",
            (marker_id, point_id)
        )


def save_point_records(point_id, records):
    """保存调查点的调查记录（批量upsert）"""
    with get_db() as db:
        for rec in records:
            db.execute(
                """INSERT OR REPLACE INTO survey_records
                   (point_id, field_key, field_label, field_value, field_type, field_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    point_id,
                    rec["field_key"],
                    rec.get("field_label", rec["field_key"]),
                    rec.get("field_value", ""),
                    rec.get("field_type", "text"),
                    rec.get("field_order", 0),
                )
            )


# ==================== 照片管理 ====================

def save_photo(point_id, filename, storage_path, thumbnail_path="",
               exif_data=None, width=0, height=0, file_size=0, caption="",
               taken_at=None):
    """保存照片记录到数据库"""
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO photos
               (point_id, filename, storage_path, thumbnail_path, caption,
                exif_data, taken_at, file_size, width, height)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                point_id, filename, storage_path, thumbnail_path, caption,
                json.dumps(exif_data or {}, ensure_ascii=False),
                taken_at, file_size, width, height,
            )
        )
        return cursor.lastrowid


def get_photos(point_id):
    """获取调查点的所有照片"""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM photos WHERE point_id=? ORDER BY created_at DESC",
            (point_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_photo(photo_id):
    """获取单张照片"""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM photos WHERE id=?", (photo_id,)
        ).fetchone()
        return dict(row) if row else None


def get_project_photos(project_id):
    """获取项目所有照片（用于导出）"""
    with get_db() as db:
        rows = db.execute(
            """SELECT p.* FROM photos p
               JOIN survey_points sp ON p.point_id = sp.id
               WHERE sp.project_id=?""",
            (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_photo(photo_id):
    """删除照片记录，返回存储路径用于清理文件"""
    with get_db() as db:
        row = db.execute(
            "SELECT storage_path, thumbnail_path FROM photos WHERE id=?",
            (photo_id,)
        ).fetchone()
        if not row:
            return None

        paths = {"storage_path": row["storage_path"],
                 "thumbnail_path": row["thumbnail_path"]}
        db.execute("DELETE FROM photos WHERE id=?", (photo_id,))
        return paths


# ==================== 字段模板管理 ====================

def get_templates():
    """列出所有字段模板"""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM field_templates ORDER BY is_default DESC, created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_template(template_id):
    """获取模板详情（含字段列表）"""
    with get_db() as db:
        template = db.execute(
            "SELECT * FROM field_templates WHERE id=?", (template_id,)
        ).fetchone()
        if not template:
            return None

        result = dict(template)
        fields = db.execute(
            "SELECT * FROM template_fields WHERE template_id=? ORDER BY field_order",
            (template_id,)
        ).fetchall()
        result["fields"] = []
        for f in fields:
            fd = dict(f)
            fd["options"] = json.loads(fd.get("options", "[]"))
            result["fields"].append(fd)

        return result


def create_template(name, fields):
    """创建新模板"""
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO field_templates (name) VALUES (?)", (name,)
        )
        template_id = cursor.lastrowid

        for i, field in enumerate(fields):
            options = json.dumps(field.get("options", []), ensure_ascii=False)
            db.execute(
                """INSERT INTO template_fields
                   (template_id, field_key, field_label, field_type,
                    field_order, is_required, options)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    template_id,
                    field["field_key"],
                    field["field_label"],
                    field.get("field_type", "text"),
                    field.get("field_order", i + 1),
                    1 if field.get("is_required", True) else 0,
                    options,
                )
            )
        return template_id


def delete_template(template_id):
    """删除模板（默认模板不可删除）"""
    with get_db() as db:
        template = db.execute(
            "SELECT is_default FROM field_templates WHERE id=?", (template_id,)
        ).fetchone()
        if not template:
            return False
        if template["is_default"]:
            return False
        db.execute("DELETE FROM field_templates WHERE id=?", (template_id,))
        return True


def get_default_template():
    """获取默认模板"""
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM field_templates WHERE is_default=1"
        ).fetchone()
        if row:
            return get_template(row["id"])
        return None


# ==================== 统计辅助 ====================

# ==================== 工程名称辅助 ====================

def get_used_project_names():
    """获取所有填写过的工程名称（用于自动补全）"""
    with get_db() as db:
        rows = db.execute(
            "SELECT DISTINCT field_value FROM survey_records "
            "WHERE field_key='project_name' AND field_value != '' "
            "ORDER BY field_value"
        ).fetchall()
        return [r["field_value"] for r in rows]


def batch_set_project_name(project_id, name):
    """统一设置项目下所有调查点的工程名称"""
    with get_db() as db:
        point_ids = db.execute(
            "SELECT id FROM survey_points WHERE project_id=?", (project_id,)
        ).fetchall()

        count = 0
        for pt in point_ids:
            db.execute(
                "INSERT OR REPLACE INTO survey_records "
                "(point_id, field_key, field_label, field_value, field_type, field_order) "
                "VALUES (?, 'project_name', '工程名称', ?, 'text', 2)",
                (pt["id"], name)
            )
            count += 1
        return count


def batch_set_investigator(project_id, name):
    """统一设置项目下所有调查点的调查人"""
    with get_db() as db:
        point_ids = db.execute(
            "SELECT id FROM survey_points WHERE project_id=?", (project_id,)
        ).fetchall()
        count = 0
        for pt in point_ids:
            db.execute(
                "INSERT OR REPLACE INTO survey_records "
                "(point_id, field_key, field_label, field_value, field_type, field_order) "
                "VALUES (?, 'investigator', '调查人', ?, 'text', 5)",
                (pt["id"], name)
            )
            count += 1
        return count


def get_project_stats(project_id):
    """获取项目统计信息"""
    with get_db() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM survey_points WHERE project_id=?", (project_id,)
        ).fetchone()[0]
        surveyed = db.execute(
            "SELECT COUNT(*) FROM survey_points WHERE project_id=? AND status='surveyed'",
            (project_id,)
        ).fetchone()[0]
        pending = db.execute(
            "SELECT COUNT(*) FROM survey_points WHERE project_id=? AND status='pending'",
            (project_id,)
        ).fetchone()[0]
        in_progress = db.execute(
            "SELECT COUNT(*) FROM survey_points WHERE project_id=? AND status='in_progress'",
            (project_id,)
        ).fetchone()[0]
        skipped = db.execute(
            "SELECT COUNT(*) FROM survey_points WHERE project_id=? AND status='skipped'",
            (project_id,)
        ).fetchone()[0]

        return {
            "total": total,
            "surveyed": surveyed,
            "pending": pending,
            "in_progress": in_progress,
            "skipped": skipped,
        }
