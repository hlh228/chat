"""
main.py —— FastAPI 应用的入口。

负责五件事：创建应用、配置 CORS 中间件、启动时建表、挂路由、托管前端静态文件。

启动方式（在 backend 目录下执行）：
    .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload

启动后可访问：
    http://127.0.0.1:8000/            直接打开聊天室页面（前端文件由后端一起发出）
    http://127.0.0.1:8000/docs        自动生成的接口文档
    http://127.0.0.1:8000/api/health  健康检查
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS
from .database import init_db
from .routers import auth, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时建表；关闭时没有需要清理的东西，所以 yield 后面是空的。"""
    init_db()
    yield


app = FastAPI(
    title="轻量聊天室 API",
    version="0.1.0",
    description="原生 HTML/CSS/JavaScript + FastAPI + SQLite 的轻量即时通讯项目",
    lifespan=lifespan,
)

# 前端跑在 5173、后端跑在 8000，端口不同浏览器视为跨域，这里用白名单放行。
# 没有用 "*"，避免把接口开放给任意网站。
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)  # 注册 / 登录 / 我是谁
app.include_router(chat.router)  # 找人 / 开会话 / 发消息 / 收消息


@app.get("/api/health", tags=["系统"], summary="健康检查")
def health_check():
    """最简单的接口：返回 ok 就说明服务是活的。"""
    return {"status": "ok"}


# ==================== 把前端页面也交给后端发 ====================
# 好处：只开 8000 一个端口就够了 —— 局域网给别人看、内网穿透到公网，都只要映射这一个口；
# 而且页面和接口是同一个来源，浏览器根本不会触发跨域检查。
# 注意 1：mount 必须写在所有 include_router 之后，否则挂在 "/" 上的静态服务会把 /api/... 也抢走。
# 注意 2：html=True 表示访问 "/" 时自动返回 index.html。
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"  # backend/app → 回到 chat/
if FRONTEND_DIR.is_dir():  # 前端目录万一不在，也只是少个页面，后端照样能跑
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
