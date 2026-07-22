"""奥维CAD转换插件 - 一键启动"""

import os
import sys
import webbrowser
import threading
import time

# PyInstaller 打包后设置 pyproj 数据路径
if getattr(sys, 'frozen', False):
    import pyproj
    proj_dir = os.path.join(sys._MEIPASS, "proj")
    if os.path.exists(proj_dir):
        os.environ["PROJ_DATA"] = proj_dir
        pyproj.datadir.set_data_dir(proj_dir)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.models import init_db
from backend.server import create_app
from backend.updater import check_update, download_update, apply_update
from config import (
    SERVER_HOST, SERVER_PORT, DEBUG, ensure_directories,
    BASE_DIR, DWG_CONVERTER_PATH, VERSION, UPDATE_URLS
)


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("114.114.114.114", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def check_dwg_converter():
    """检查DWG转换器，未安装则提示"""
    if os.path.exists(DWG_CONVERTER_PATH):
        return True

    print("""
  ⚠ 未检测到 DWG 转换器 (ODA FileConverter)
  上传 DWG 需要此工具。仅用 DXF 可忽略。
  下载: https://www.opendesign.com/guestfiles/oda_file_converter
  安装到 D:\\ODA\\
  --------------------------------------------------
""")
    return False


def auto_open_browser():
    """延迟2秒后自动打开浏览器"""
    time.sleep(2)
    url = f"http://127.0.0.1:{SERVER_PORT}"
    webbrowser.open(url)


def main():
    ensure_directories()

    # 初始化数据库
    init_db()

    # 检查DWG转换器
    check_dwg_converter()

    # 检查更新（后台静默进行）
    def _do_update_check():
        try:
            has, latest, dl_url = check_update(VERSION, UPDATE_URLS)
            if has:
                print(f"""
  ╔══════════════════════════════════════════╗
  ║  � 发现新版本 v{latest}（当前 v{VERSION}）║
  ║  正在自动下载更新 ...                     ║
  ╚══════════════════════════════════════════╝
""")
                new_exe = download_update(dl_url)
                current_exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
                apply_update(current_exe, new_exe)
                print("  更新已就绪，程序即将重启...")
                os._exit(0)
        except Exception:
            pass  # 更新失败不影响正常使用

    import threading
    threading.Thread(target=_do_update_check, daemon=True).start()

    # 创建应用
    app = create_app()

    # 自动打开浏览器
    threading.Thread(target=auto_open_browser, daemon=True).start()

    # 打印信息
    local_ip = get_local_ip()
    print(f"""
╔══════════════════════════════════════════════════╗
║      奥维互动地图 - CAD转换插件 v{VERSION}        ║
╚══════════════════════════════════════════════════╝

  本机访问: http://127.0.0.1:{SERVER_PORT}
  局域网:   http://{local_ip}:{SERVER_PORT}
  数据库:   data/survey.db

  浏览器已自动打开，如未打开请手动访问上述地址。
  手机/平板连同一WiFi，浏览器输入局域网地址即可。
  关闭此窗口即停止服务。
--------------------------------------------------
""")

    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=False,  # exe模式关闭debug
        threaded=True,
    )


if __name__ == "__main__":
    main()
