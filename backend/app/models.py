"""
models.py —— 4 张数据库表的定义（ORM 模型）。

    users                 用户
    conversations         会话（一次一对一聊天就是一个会话）
    conversation_members  会话成员（谁在哪个会话里）
    messages              消息

一对一聊天也建“会话 + 成员”两张表，是为了将来加群聊时不用改表结构：
新成员往中间表多插几行就行。
"""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    """当前 UTC 时间（不带时区标记）。

    统一存 UTC，显示时再转成本地时间，避免服务器换时区后数据错乱；
    SQLite 不真正支持时区，所以去掉 tzinfo。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """用户表：一个账号一行。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 登录名。唯一性交给数据库保证，比“先查一下再插入”可靠（两个人同时注册也不会重复）
    username: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )

    # 昵称：显示给别人看的名字，可以和登录名不同
    nickname: Mapped[str] = mapped_column(String(32), nullable=False)

    # 密码密文（salt + 密码 做 20 万轮哈希的结果），数据库里绝不存明文
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    # 每个用户独立的随机盐：让相同的密码也产生不同密文，彩虹表就失效了
    salt: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # 最后活跃时间，登录时刷新（预留：将来可用来显示在线状态）
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"User(id={self.id}, username={self.username})"


class Conversation(Base):
    """会话表：一次聊天就是一个会话。一对一里每个会话恰好有 2 个成员。"""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # 冗余字段：会话列表按它倒序排。
    # 存一个字段比每次去 messages 表算最大值便宜，列表查询退化成一次排序。
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False, index=True
    )

    # 有了这个关系就能直接写 conversation.members；
    # cascade 保证将来真删会话时，成员记录会一并清掉，不留垃圾数据
    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Conversation(id={self.id})"


class ConversationMember(Base):
    """会话成员表（中间表）：表达“用户”和“会话”之间的多对多关系。"""

    __tablename__ = "conversation_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 外键：这两个值必须能在 conversations.id / users.id 里找到
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="members")

    __table_args__ = (
        # 同一个用户不能在一个会话里出现两次（由数据库强制保证）
        UniqueConstraint("conversation_id", "user_id", name="uq_conversation_member"),
        # 服务“我参与了哪些会话”“我和某人是否已有会话”这两类查询
        Index("ix_member_user_conversation", "user_id", "conversation_id"),
    )

    def __repr__(self) -> str:
        return f"ConversationMember(conv={self.conversation_id}, user={self.user_id})"


class Message(Base):
    """消息表：一条消息一行，永久保存 —— 这是“消息持久化”的落脚点。"""

    __tablename__ = "messages"

    # id 身兼两职：唯一标识消息 + 充当轮询游标（前端问“给我比 123 更新的消息”）。
    # 用自增 id 而不是 created_at 当游标：时间戳可能重复或精度不足，会漏消息或重复拉。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # 用 Text（不限长度）；业务上的 1~2000 字符限制在 schemas.py 里校验
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 幂等字段：前端每次发消息前生成一个随机串。
    # 同一句话被提交两次时，第二次会撞上唯一约束，后端就把第一次那条返回，
    # 所以数据库里绝不会出现两条一模一样的消息。
    client_msg_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        # 复合索引，列顺序与轮询查询一致（先按会话过滤，再按 id > 游标筛选，最后按 id 排序）
        Index("ix_message_conv_id", "conversation_id", "id"),
    )

    def __repr__(self) -> str:
        return f"Message(id={self.id}, conv={self.conversation_id}, from={self.sender_id})"
