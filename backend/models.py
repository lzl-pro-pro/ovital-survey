"""SQLite 数据模型和迁移管理"""

import sqlite3
import os
from config import DATABASE_PATH, DEFAULT_SURVEY_FIELDS

SCHEMA_VERSION = 1


def get_db_path():
    """获取数据库路径，确保目录存在"""
    db_dir = os.path.dirname(DATABASE_PATH)
    os.makedirs(db_dir, exist_ok=True)
    return DATABASE_PATH


def init_db():
    """初始化数据库：创建所有表和默认数据"""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cursor = conn.cursor()

    # 检查schema版本
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_info'"
    )
    if cursor.fetchone():
        version = cursor.execute(
            "SELECT version FROM schema_info"
        ).fetchone()[0]
    else:
        version = 0

    if version < SCHEMA_VERSION:
        _create_tables(cursor)
        _create_default_template(cursor)
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schema_info (version INTEGER)"
        )
        cursor.execute("DELETE FROM schema_info")
        cursor.execute("INSERT INTO schema_info (version) VALUES (?)",
                       (SCHEMA_VERSION,))

    conn.commit()
    conn.close()


def _create_tables(cursor):
    """创建所有数据表"""
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            cad_file_path TEXT DEFAULT '',
            cad_file_type TEXT DEFAULT '',
            coord_system TEXT DEFAULT 'local',
            transform_params TEXT DEFAULT '{}',
            template_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS cad_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            text_content TEXT NOT NULL,
            matched_label TEXT DEFAULT '',
            cad_x REAL NOT NULL,
            cad_y REAL NOT NULL,
            cad_z REAL DEFAULT 0,
            entity_type TEXT DEFAULT '',
            layer_name TEXT DEFAULT '',
            entity_handle TEXT DEFAULT '',
            is_confirmed INTEGER DEFAULT 0,
            matched_point_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS survey_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            point_number TEXT NOT NULL,
            latitude REAL DEFAULT 0,
            longitude REAL DEFAULT 0,
            altitude REAL DEFAULT 0,
            cad_x REAL DEFAULT 0,
            cad_y REAL DEFAULT 0,
            annotation_id INTEGER REFERENCES cad_annotations(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            ovital_marker_id TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            surveyed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS survey_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            point_id INTEGER NOT NULL REFERENCES survey_points(id) ON DELETE CASCADE,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_value TEXT DEFAULT '',
            field_type TEXT NOT NULL DEFAULT 'text',
            field_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE(point_id, field_key)
        );

        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            point_id INTEGER NOT NULL REFERENCES survey_points(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            thumbnail_path TEXT DEFAULT '',
            caption TEXT DEFAULT '',
            exif_data TEXT DEFAULT '{}',
            taken_at TEXT,
            file_size INTEGER DEFAULT 0,
            width INTEGER DEFAULT 0,
            height INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS field_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS template_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL REFERENCES field_templates(id) ON DELETE CASCADE,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_type TEXT NOT NULL DEFAULT 'text',
            field_order INTEGER NOT NULL DEFAULT 0,
            is_required INTEGER DEFAULT 1,
            options TEXT DEFAULT '[]',
            UNIQUE(template_id, field_key)
        );
    """)

    # 创建索引
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_annotations_project
            ON cad_annotations(project_id);
        CREATE INDEX IF NOT EXISTS idx_annotations_confirmed
            ON cad_annotations(is_confirmed);
        CREATE INDEX IF NOT EXISTS idx_points_project
            ON survey_points(project_id);
        CREATE INDEX IF NOT EXISTS idx_points_status
            ON survey_points(status);
        CREATE INDEX IF NOT EXISTS idx_records_point
            ON survey_records(point_id);
        CREATE INDEX IF NOT EXISTS idx_photos_point
            ON photos(point_id);
        CREATE INDEX IF NOT EXISTS idx_template_fields_template
            ON template_fields(template_id);
    """)


def _create_default_template(cursor):
    """创建默认调查字段模板"""
    import json

    cursor.execute("SELECT id FROM field_templates WHERE is_default=1")
    existing = cursor.fetchone()
    if existing:
        return existing[0]

    cursor.execute(
        "INSERT INTO field_templates (name, is_default) VALUES (?, 1)",
        ("默认调查模板",)
    )
    template_id = cursor.lastrowid

    for field in DEFAULT_SURVEY_FIELDS:
        options = json.dumps(field.get("options", []), ensure_ascii=False)
        cursor.execute(
            """INSERT INTO template_fields
               (template_id, field_key, field_label, field_type,
                field_order, is_required, options)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                template_id,
                field["key"],
                field["label"],
                field["type"],
                field["order"],
                1 if field.get("required", True) else 0,
                options,
            )
        )

    return template_id
