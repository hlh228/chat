"""
run.py —— 一键启动聊天室后端（双击「启动后端.bat」跑的就是它）。

做的事情：打印提示 → 检查端口是否已被占用 → 3 秒后自动打开浏览器 → 启动 uvicorn。
"""

import os
import socket
import threading
import time
import webbrowser

import uvicorn

# 默认只听本机（最安全）。想让同一 WiFi 的别人也能访问，就先设环境变量 CHAT_HOST=0.0.0.0
HOST = os.getenv("CHAT_HOST") or "127.0.0.1"
PORT = 8000

# 0.0.0.0 的意思是“监听所有网卡”，它本身不是一个能打开的地址，
# 所以打印提示、自动打开浏览器时都换回 127.0.0.1。
OPEN_HOST = "127.0.0.1" if HOST in ("0.0.0.0", "::") else HOST
HOME_URL = f"http://{OPEN_HOST}:{PORT}/"
DOCS_URL = f"http://{OPEN_HOST}:{PORT}/docs"
HEALTH_URL = f"http://{OPEN_HOST}:{PORT}/api/health"


def set_window_title(title: str) -> None:
    """改命令行窗口标题，方便区分前后端两个黑窗口（只在 Windows 上有效，失败也不影响服务）。"""
    if os.name != "nt":
        return
    try:
        import ctypes

        # SetConsoleTitleW 末尾的 W 表示支持中文等宽字符
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


def port_in_use(host: str, port: int) -> bool:
    """端口上已经有服务在监听就返回 True（连得上说明有人在）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def open_browser_later(url: str, seconds: float = 3.0) -> None:
    """等几秒再打开浏览器，免得浏览器先于服务器就绪、只看到“连不上”。

    放进线程里执行，因为下面的 uvicorn.run() 会一直占用主线程。
    """
    time.sleep(seconds)
    try:
        webbrowser.open(url)
    except Exception:
        print("   没能自动打开浏览器，请手动访问：" + url)


def main() -> None:
    set_window_title("聊天室后端(8000)   [按 Ctrl+C 停止]")

    line = "=" * 58
    print(line)
    print("   聊天室后端启动中，请稍等 3 秒 ...")
    print(f"   聊天室页面：{HOME_URL}     ← 前端文件由后端一起发出，直接打开就能聊天")
    print(f"   接口文档：{DOCS_URL}")
    print(f"   健康检查：{HEALTH_URL}")
    if HOST == "0.0.0.0":
        print("   局域网模式：别人用 http://<你的IPv4>:8000/ 访问（ipconfig 查 IPv4，要同一 WiFi）")
    print("   这个窗口不要关，关了服务就停了；按 Ctrl+C 停止。")
    print(line)

    # 端口已被占用（多半是刚才已经启动过一次），就不再重复启动
    if port_in_use("127.0.0.1", PORT):  # 固定查回环地址：0.0.0.0 不是一个能连的地址
        print("   注意：8000 端口已经有服务在跑，本次不再重复启动。")
        webbrowser.open(DOCS_URL)
        return

    threading.Thread(target=open_browser_later, args=(DOCS_URL,), daemon=True).start()

    try:
        # "模块路径:变量名" —— 到 app/main.py 里找那个叫 app 的 FastAPI 对象
        uvicorn.run("app.main:app", host=HOST, port=PORT)
    except KeyboardInterrupt:
        pass  # 用户按了 Ctrl+C，属于正常退出
    finally:
        print("   后端已停止。")


if __name__ == "__main__":
    main()
