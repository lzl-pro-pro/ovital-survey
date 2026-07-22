"""自动更新模块"""

import os
import sys
import json
import urllib.request
import urllib.error
import tempfile
import subprocess
import shutil


def check_update(current_version, update_urls):
    """检查是否有新版本，多个URL依次尝试，返回 (has_update, latest_version, download_url)"""
    # 兼容旧版单个URL
    if isinstance(update_urls, str):
        update_urls = [update_urls]

    for url in update_urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "OvitalSurvey-Updater/1.0"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("version", "")
            dl_url = data.get("download_url", "")

            has_update = _version_newer(latest, current_version)
            return has_update, latest, dl_url
        except Exception:
            continue  # 尝试下一个URL

    return False, "", ""


def download_update(download_url, progress_callback=None):
    """下载新版本exe，返回临时文件路径"""
    tmp_path = os.path.join(tempfile.gettempdir(), "OvitalSurvey_update.exe")

    try:
        req = urllib.request.Request(download_url, headers={
            "User-Agent": "OvitalSurvey-Updater/1.0"
        })
        with urllib.request.urlopen(req, timeout=300) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)
        return tmp_path
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise e


def apply_update(exe_path, new_exe_path):
    """创建更新脚本并启动替换流程"""
    if sys.platform != "win32":
        # 非Windows：直接替换
        os.replace(new_exe_path, exe_path)
        return True

    # 生成替换脚本
    bat_path = os.path.join(os.path.dirname(exe_path), "_updater.bat")
    with open(bat_path, "w", encoding="gbk") as f:
        f.write(f"""@echo off
chcp 65001 >nul
echo Updating OvitalSurvey...
timeout /t 2 /nobreak >nul
move /Y "{new_exe_path}" "{exe_path}"
if %errorlevel% == 0 (
    echo Update complete! Restarting...
    start "" "{exe_path}"
) else (
    echo Update failed. Please manually copy:
    echo   From: {new_exe_path}
    echo   To:   {exe_path}
    pause
)
del "%~f0"
""")

    # 启动更新脚本
    subprocess.Popen(
        f'cmd /c "{bat_path}"',
        shell=True,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
    )
    return True


def _version_newer(a, b):
    """比较版本号"""
    try:
        pa = [int(x) for x in a.split(".")]
        pb = [int(x) for x in b.split(".")]
        for i in range(max(len(pa), len(pb))):
            va = pa[i] if i < len(pa) else 0
            vb = pb[i] if i < len(pb) else 0
            if va > vb: return True
            if va < vb: return False
        return False
    except Exception:
        return a.strip() != b.strip()


def make_version_json(version, download_url):
    """生成版本信息JSON（开发者用）"""
    return json.dumps({
        "version": version,
        "download_url": download_url,
        "release_date": "",
        "notes": "",
    }, ensure_ascii=False, indent=2)
