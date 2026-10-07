"""
run.py —— 一键启动聊天室前端（双击「启动前端.bat」跑的就是它）。

用 Python 自带的 http.server 在 5173 端口提供静态文件。
为什么不能直接双击 index.html 打开？因为 file:// 开头的页面会被浏览器
禁止向别的地址发请求，必须有个 http 来源才能调后端接口
（5173 已经在后端 config.py 的 CORS_ORIGINS 白名单里）。
"""

import functools
import os
import socket
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# 只服务 frontend 这个文件夹；用 __file__ 算出来，跑的时候在哪个目录都无所谓
BASE_DIR = Path(__file__).resolve().parent

# 默认只听本机（最安全）。想让同一 WiFi 的别人也能访问，就先设环境变量 CHAT_HOST=0.0.0.0
HOST = os.getenv("CHAT_HOST") or "127.0.0.1"
PORT = 5173

# 0.0.0.0 的意思是“监听所有网卡”，它本身不是一个能打开的地址，提示里换回 127.0.0.1
OPEN_HOST = "127.0.0.1" if HOST in ("0.0.0.0", "::") else HOST
HOME_URL = f"http://{OPEN_HOST}:{PORT}/"

# 设了这个环境变量就不自动开浏览器（自动化测试用）
NO_BROWSER = os.getenv("CHAT_NO_BROWSER") == "1"


def set_window_title(title: str) -> None:
    """改命令行窗口标题，方便区分前后端两个黑窗口（只在 Windows 上有效）。"""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


def port_in_use(host: str, port: int) -> bool:
    """端口上已经有服务在监听就返回 True。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def open_browser_later(url: str, seconds: float = 2.0) -> None:
    """等服务器起来再打开浏览器（放进线程里，因为下面主线程要一直跑服务器）。"""
    time.sleep(seconds)
    try:
        webbrowser.open(url)
    except Exception:
        print("   没能自动打开浏览器，请手动访问：" + url)


class QuietHandler(SimpleHTTPRequestHandler):
    """把默认那行又长又吵的英文日志换成一行中文。"""

    def log_message(self, format, *args):
        print("   浏览器取走了：" + self.path)


def main() -> None:
    set_window_title("聊天室前端(5173)   [按 Ctrl+C 停止]")

    line = "=" * 58
    print(line)
    print("   聊天室前端启动中，请稍等 2 秒 ...")
    print(f"   前端地址：{HOME_URL}")
    print("   别忘了另开一个窗口启动后端（8000 端口）。")
    print("   也可以直接用后端的 http://127.0.0.1:8000/ 打开，页面由后端一起发。")
    if HOST == "0.0.0.0":
        print("   局域网模式：别人用 http://<你的IPv4>:5173/ 访问（ipconfig 查 IPv4，要同一 WiFi）")
    print("   这个窗口不要关，关了前端就停了；按 Ctrl+C 停止。")
    print(line)

    if port_in_use("127.0.0.1", PORT):  # 固定查回环地址：0.0.0.0 不是一个能连的地址
        print("   注意：5173 端口已经有服务在跑，本次不再重复启动。")
        if not NO_BROWSER:
            webbrowser.open(HOME_URL)
        return

    if not NO_BROWSER:
        threading.Thread(target=open_browser_later, args=(HOME_URL,), daemon=True).start()

    # ThreadingHTTPServer 能同时处理多个请求（页面一次要拉 html / css / js 三个文件）；
    # functools.partial 用来把 directory 参数提前绑到处理器上。
    handler = functools.partial(QuietHandler, directory=str(BASE_DIR))
    server = ThreadingHTTPServer((HOST, PORT), handler)

    try:
        server.serve_forever()  # 一直循环，直到按 Ctrl+C
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("   前端已停止。")


if __name__ == "__main__":
    main()
