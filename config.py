"""集中配置文件"""

import os
import sys

# 项目根目录（兼容 PyInstaller 打包）
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Flask 服务配置
VERSION = "1.3.1"
# 更新服务器URL（按优先级：jsDelivr CDN国内更快，GitHub Raw备用）
UPDATE_URLS = [
    "https://cdn.jsdelivr.net/gh/lzl-pro-pro/ovital-survey@main/version.json",
    "https://raw.githubusercontent.com/lzl-pro-pro/ovital-survey/main/version.json",
]

SERVER_HOST = os.environ.get("OVITAL_HOST", "0.0.0.0")  # 0.0.0.0 允许局域网访问
SERVER_PORT = int(os.environ.get("OVITAL_PORT", 8800))
DEBUG = os.environ.get("OVITAL_DEBUG", "true").lower() == "true"

# 数据库
DATABASE_PATH = os.path.join(BASE_DIR, "data", "survey.db")

# 存储路径
UPLOAD_FOLDER = os.path.join(BASE_DIR, "storage", "uploads", "cad")
PHOTO_FOLDER = os.path.join(BASE_DIR, "storage", "photos")
EXPORT_FOLDER = os.path.join(BASE_DIR, "exports")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")

# 文件限制
MAX_CAD_SIZE_MB = 50
MAX_CAD_SIZE_BYTES = MAX_CAD_SIZE_MB * 1024 * 1024
MAX_PHOTO_SIZE_MB = 20
MAX_PHOTO_SIZE_BYTES = MAX_PHOTO_SIZE_MB * 1024 * 1024
MAX_PHOTOS_PER_POINT = 20
THUMBNAIL_SIZE = (300, 300)
MAX_PHOTO_DIMENSION = 4096  # 最大边长

# 允许的文件类型
ALLOWED_CAD_EXTENSIONS = {".dxf", ".dwg"}
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

# DWG转换器路径 (ODA FileConverter 或 LibreDWG dwg2dxf)
# DWG转换器路径，按优先级自动检测，找到即用
DWG_CONVERTER_PATHS = [
    r"D:\ODA\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
]

def _find_dwg_converter():
    for p in DWG_CONVERTER_PATHS:
        if os.path.exists(p):
            return p
    return DWG_CONVERTER_PATHS[0]  # 默认返回第一个

DWG_CONVERTER_PATH = os.environ.get("DWG_CONVERTER", "") or _find_dwg_converter()

# CAD标注匹配正则 (工程编号 + 土地调查编号)
ANNOTATION_REGEX_PATTERNS = [
    r"K\d{1,6}\+\d{1,4}\.*\d*",              # 里程桩号: K1+234, K123+456.78
    r"[A-Z]{2,4}\d{2,6}",                      # 站点编号: AB0123, ZK001
    r"P\d{2,5}[A-Z]?",                         # 桩号: P001, P1234A
    r"\d{1,4}-\d{1,4}",                         # 断面编号: 1-1, 12-34
    r"[A-Z]\d{2,4}[A-Z]\d*",                   # 钻孔编号: ZK001A, J001B2
    r"[一-鿿]+\d{2,4}$",               # 中文+数字结尾: 某某村007, 双胜032
    r"[一-鿿]{2,6}[一-鿿]{2,8}\d{2,4}",  # 村名+地名+编号
    r"[A-Za-z]{0,3}\d{2,6}[A-Za-z]?\d*",      # 通用编号: A001, BZ1234
]

# CAD投影坐标系 → WGS84经纬度转换
# 中国常用坐标系列表，按优先级排列
CAD_COORD_SYSTEMS = [
    {"id": "EPSG:4544", "name": "CGCS2000 3度带 108E (重庆/贵州/广西)", "zone": 37},
    {"id": "EPSG:4543", "name": "CGCS2000 3度带 105E (四川/云南/甘肃)", "zone": 36},
    {"id": "EPSG:4545", "name": "CGCS2000 3度带 111E (湖南/湖北/广东)", "zone": 38},
    {"id": "EPSG:4542", "name": "CGCS2000 3度带 102E (西藏/青海)", "zone": 35},
    {"id": "EPSG:4546", "name": "CGCS2000 3度带 114E (福建/江西)", "zone": 39},
    {"id": "EPSG:4547", "name": "CGCS2000 3度带 117E (浙江/安徽)", "zone": 40},
    {"id": "EPSG:4509", "name": "CGCS2000 6度带 19 (108-114E)", "zone": 19},
    {"id": "EPSG:4508", "name": "CGCS2000 6度带 18 (102-108E)", "zone": 18},
    {"id": "EPSG:32648", "name": "WGS84 UTM 48N", "zone": 48},
    {"id": "EPSG:32649", "name": "WGS84 UTM 49N", "zone": 49},
    {"id": "EPSG:32650", "name": "WGS84 UTM 50N", "zone": 50},
]
DEFAULT_CAD_CRS = "EPSG:4544"  # 默认 CGCS2000 108E

# 默认调查字段模板
DEFAULT_SURVEY_FIELDS = [
    {"key": "point_number", "label": "编号", "type": "text", "required": True, "order": 1},
    {"key": "project_name", "label": "工程名称", "type": "text", "required": True, "order": 2},
    {"key": "location_desc", "label": "位置描述", "type": "multiline", "required": True, "order": 3},
    {"key": "station_number", "label": "桩号", "type": "text", "required": False, "order": 4},
    {"key": "investigator", "label": "调查人", "type": "text", "required": True, "order": 5},
    {"key": "survey_date", "label": "调查日期", "type": "date", "required": True, "order": 6},
    {"key": "weather", "label": "天气", "type": "select", "required": False, "order": 7,
     "options": ["晴", "多云", "阴", "小雨", "中雨", "大雨", "雾", "雪"]},
    {"key": "geo_desc", "label": "地质描述", "type": "multiline", "required": False, "order": 8},
    {"key": "landform_type", "label": "地貌类型", "type": "select", "required": False, "order": 9,
     "options": ["平原", "丘陵", "山地", "河谷", "台地", "沙漠", "戈壁", "其他"]},
    {"key": "vegetation_type", "label": "植被类型", "type": "select", "required": False, "order": 10,
     "options": ["无植被", "草地", "灌木", "针叶林", "阔叶林", "混交林", "农田", "其他"]},
    {"key": "remarks", "label": "备注", "type": "multiline", "required": False, "order": 11},
]


def ensure_directories():
    """确保所有必要的目录存在"""
    for path in [UPLOAD_FOLDER, PHOTO_FOLDER, EXPORT_FOLDER, LOG_FOLDER,
                 os.path.join(BASE_DIR, "data")]:
        os.makedirs(path, exist_ok=True)
