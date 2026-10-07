"""
database.py —— 数据库的引擎、会话工厂、模型基类，以及两个对外使用的函数。

对外的 5 样东西：
    engine       引擎（全局一个）
    SessionLocal 会话工厂（每个请求生产一个会话）
    Base         所有表模型的基类
    get_db()     FastAPI 依赖：接口函数用它拿到数据库会话
    init_db()    建表（程序启动时调用一次）
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

# check_same_thread=False 必须加：SQLite 默认禁止一个连接被多个线程使用，
# 而 FastAPI 会把普通 def 接口丢进线程池执行，线程会变来变去。
# 关闭这个检查是安全的，因为我们保证“一个请求一个独立会话、用完即关”。
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # 改成 True 会把执行的 SQL 打印出来，调试时有用
)

# 会话工厂：SessionLocal() 才得到一个会话。
# autoflush=False / autocommit=False 是为了让“什么时候写库、什么时候提交”完全由代码显式控制。
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有表模型的基类；Base.metadata 里登记着项目里全部的表。"""


def get_db():
    """FastAPI 依赖：给每个请求分配一个数据库会话，请求结束（含出错）后一定关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """按 models.py 的定义建表。表已存在就跳过，不会删数据。"""
    # 这行 import 是“副作用导入”：只有导入它，模型类才会注册到 Base.metadata
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
