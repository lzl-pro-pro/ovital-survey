"""通用工具函数"""

import re
import os
from datetime import datetime


def natural_sort_key(text):
    """自然排序键：合并数字部分按数值排序"""
    if not text:
        return []
    parts = re.split(r'(\d+)', str(text))
    result = []
    for part in parts:
        if part.isdigit():
            result.append(int(part))
        else:
            result.append(part.lower())
    return result


def format_datetime(dt_string):
    """格式化日期时间字符串"""
    if not dt_string:
        return ""
    try:
        # 尝试多种格式
        for fmt in [
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d", "%Y/%m/%d"
        ]:
            try:
                dt = datetime.strptime(dt_string, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return dt_string
    except Exception:
        return dt_string


def sanitize_filename(filename):
    """清理文件名，移除不安全字符但保留中文"""
    unsafe_chars = r'[<>:"/\\|?*\x00-\x1f]'
    filename = re.sub(unsafe_chars, '_', filename)
    # 去除首尾空格和点
    filename = filename.strip('. ')
    if not filename:
        filename = "unnamed"
    # 限制长度
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext
    return filename


def ensure_unique_filename(directory, filename):
    """确保文件名在目录中唯一，重名时自动添加序号"""
    base, ext = os.path.splitext(filename)
    counter = 1
    target = os.path.join(directory, filename)
    while os.path.exists(target):
        filename = f"{base}_{counter}{ext}"
        target = os.path.join(directory, filename)
        counter += 1
    return filename
