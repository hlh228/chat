"""
schemas.py —— 接口的输入、输出格式（Pydantic 模型）。

输入格式在这里声明类型和限制，请求进不来就直接被 FastAPI 拦下返回 422，
业务代码里不用再写一堆 if 判断。
输出格式也在这里：哪些字段能返回给前端一目了然 ——
比如 UserPublic 里没有 password_hash 和 salt，密码相关的东西永远传不出去。
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


# ==================== 账号相关 ====================


class RegisterRequest(BaseModel):
    """注册接口的请求体。"""

    username: str = Field(..., min_length=2, max_length=32, description="登录名，全站唯一")
    password: str = Field(..., min_length=6, max_length=64, description="密码，至少 6 位")
    nickname: str | None = Field(
        default=None, max_length=32, description="昵称，不填就默认用登录名"
    )


class LoginRequest(BaseModel):
    """登录接口的请求体。"""

    username: str = Field(..., description="登录名")
    password: str = Field(..., description="密码")


class UserPublic(BaseModel):
    """可以安全返回给前端的用户信息（故意不含 password_hash 和 salt）。"""

    # from_attributes=True 允许直接传 ORM 对象来构造，例如 UserPublic.model_validate(user)
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    created_at: datetime


class TokenResponse(BaseModel):
    """注册 / 登录成功后返回：token + 用户信息。"""

    token: str = Field(..., description="以后每次请求都要放在 Authorization 头里")
    user: UserPublic


# ==================== 聊天相关 ====================

# 消息正文的格式：去掉首尾空白、最少 1 个字符、最多 2000 个字符。
# 去掉空白是为了挡住“打一堆空格也能发出去”的情况。
MessageContent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class ConversationCreate(BaseModel):
    """开会话的请求体：只需告诉服务端“我想跟谁聊”。

    已聊过就返回原来那个会话，没聊过才新建，所以绝不会重复建。
    """

    peer_id: int = Field(..., description="对方的用户 id，从 GET /api/users 里拿")


class ConversationPublic(BaseModel):
    """返回给前端的会话信息。peer 和 last_message 不是表里的列，是接口临时拼出来的。"""

    id: int = Field(..., description="会话 id，发消息 / 收消息都要用它")
    peer: UserPublic = Field(..., description="聊天对象（我自己的信息不用再发一遍）")
    last_message_at: datetime = Field(..., description="最后一条消息的时间，列表按它倒序")
    last_message: str | None = Field(default=None, description="最后一条消息的正文，还没聊过就是 null")


class MessageCreate(BaseModel):
    """发消息的请求体。"""

    content: MessageContent = Field(..., description="消息正文，1~2000 个字符")
    client_msg_id: str = Field(
        ..., min_length=8, max_length=64, description="前端生成的随机串，用来防重复提交"
    )


class MessagePublic(BaseModel):
    """返回给前端的一条消息。

    多带了 sender_nickname：服务端顺手查出来，前端就不用再发一次请求问“3 号叫什么”。
    """

    id: int = Field(..., description="消息 id，同时也是轮询用的游标")
    conversation_id: int
    sender_id: int
    sender_nickname: str = Field(..., description="发送者昵称")
    content: str
    created_at: datetime
