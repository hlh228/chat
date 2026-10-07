"""config.py —— 全项目的可调参数集中在这里，改配置只改这一个文件。"""

import os
from pathlib import Path

# ============================== 路径 ==============================

# __file__ 是 config.py 的路径：退一级到 app/，再退一级到 backend/
BASE_DIR = Path(__file__).resolve().parent.parent

# 默认用 backend/chat.db；如果设了环境变量 CHAT_DB_FILE 就用它指定的文件
# （跑测试时用它指向临时数据库，免得测试数据污染 chat.db）
DB_FILE = Path(os.getenv("CHAT_DB_FILE") or (BASE_DIR / "chat.db"))

# SQLAlchemy 要求的 SQLite 连接地址；as_posix() 把 Windows 的反斜杠转成正斜杠
DATABASE_URL = f"sqlite:///{DB_FILE.as_posix()}"

# ============================== 认证 ==============================

# token 有效期（分钟）：60 * 24 * 7 = 7 天
TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

# 密码哈希的迭代轮数：越大越难被暴力破解，但每次校验也越慢
PBKDF2_ITERATIONS = 200_000

# token 的签名密钥。一旦泄露，别人就能伪造任意用户的 token。
# 演示项目写死在代码里，真实项目必须从环境变量读取。
SECRET_KEY = "chat-room-demo-secret-key-change-me-in-production"

# ============================== 分页 ==============================

# 拉历史消息时，前端不传 limit 就用这个默认值
DEFAULT_PAGE_SIZE = 50

# limit 的上限，防止有人一次请求把整张表拖走
MAX_PAGE_SIZE = 200

# ============================== 跨域 ==============================

# 前端静态服务器（Python 自带的 http.server）跑在 5173，后端跑在 8000，
# 端口不同浏览器就认为是“跨域”并拦下请求，所以把前端地址加进白名单。
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
