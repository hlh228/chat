"""
routers/chat.py —— 聊天相关的 5 个接口（全部要求请求头带 token）：

    GET  /api/users                         用户列表（找聊天对象，不含自己）
    POST /api/conversations                 和某人开会话（已有就复用）
    GET  /api/conversations                 我的会话列表
    POST /api/conversations/{id}/messages   发消息
    GET  /api/conversations/{id}/messages   收消息（首屏拉最近 50 条 / 轮询拉新的）

三处关键逻辑：会话去重、成员权限校验、消息幂等。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from ..database import get_db
from ..deps import get_current_user
from ..models import Conversation, ConversationMember, Message, User, utc_now
from ..schemas import (
    ConversationCreate,
    ConversationPublic,
    MessageCreate,
    MessagePublic,
    UserPublic,
)

router = APIRouter(prefix="/api", tags=["聊天"])


# ==================== 内部辅助函数（只在本文件里用） ====================


def _get_my_conversation(conversation_id: int, me: User, db: Session) -> Conversation:
    """取出会话，同时确认“我”是它的成员；否则返回 403。

    没有这一步，任何人把 URL 里的数字一改就能读到别人的聊天记录。
    这里故意不区分“会话不存在”和“我不是成员”，免得泄露会话号是否存在。
    """
    conversation = db.scalar(
        select(Conversation)
        .join(
            ConversationMember,
            ConversationMember.conversation_id == Conversation.id,
        )
        .where(
            Conversation.id == conversation_id,
            ConversationMember.user_id == me.id,  # 关键就是这一行
        )
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="会话不存在，或者你不是这个会话的成员",
        )
    return conversation


def _find_existing_conversation(me: User, peer: User, db: Session) -> Conversation | None:
    """找出“同时包含我和他”的会话；没有就返回 None。

    会话表本身看不出谁跟谁在聊，所以要问成员表：
    “我参与的会话中，哪一个的成员里也有他？”
    """
    return db.scalar(
        select(Conversation)
        .join(
            ConversationMember,
            ConversationMember.conversation_id == Conversation.id,
        )
        .where(ConversationMember.user_id == me.id)
        .where(
            Conversation.id.in_(
                select(ConversationMember.conversation_id).where(
                    ConversationMember.user_id == peer.id
                )
            )
        )
        .order_by(Conversation.id)
        .limit(1)
    )


def _peer_of(conversation: Conversation, me: User, db: Session) -> User | None:
    """会话里除我之外的那个人（一对一只有一个，所以取一条就够）。"""
    return db.scalar(
        select(User)
        .join(ConversationMember, ConversationMember.user_id == User.id)
        .where(
            ConversationMember.conversation_id == conversation.id,
            User.id != me.id,
        )
        .limit(1)
    )


def _nickname_of(user_id: int, db: Session) -> str:
    """按 id 查昵称，只在拼“别人发的消息”时用到。"""
    return db.scalar(select(User.nickname).where(User.id == user_id)) or "未知用户"


def _message_public(message: Message, nickname: str) -> MessagePublic:
    """把消息对象 + 发送者昵称拼成返回格式。

    不能直接用 model_validate：sender_nickname 不在 messages 表里，只能手动组装。
    """
    return MessagePublic(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_nickname=nickname,
        content=message.content,
        created_at=message.created_at,
    )


def _conversation_public(conversation: Conversation, me: User, db: Session) -> ConversationPublic:
    """把会话对象拼成返回格式：对方信息 + 最后一条消息预览。"""
    peer = _peer_of(conversation, me, db)
    if peer is None:
        # 理论上不会发生（开会话时一定写了两条成员记录），真发生就是数据被人手动改过
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="会话数据异常：找不到聊天对象",
        )

    # 最后一条消息：按 id 倒序取第一条（用 id 而不是 created_at，理由和轮询游标一样）
    last_message = db.scalar(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc())
        .limit(1)
    )

    return ConversationPublic(
        id=conversation.id,
        peer=UserPublic.model_validate(peer),
        last_message_at=conversation.last_message_at,
        last_message=last_message.content if last_message is not None else None,
    )


# ==================== 接口 1：用户列表（找人） ====================


@router.get("/users", response_model=list[UserPublic], summary="用户列表（找聊天对象）")
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出所有用户供前端选择聊天对象。

    排除自己（没必要跟自己聊），并按 id 排序，保证每次返回顺序一致。
    参数里写了 Depends(get_current_user)，所以没登录的请求会被提前拦下返回 401。
    """
    users = db.scalars(select(User).where(User.id != current_user.id).order_by(User.id)).all()
    return [UserPublic.model_validate(user) for user in users]


# ==================== 接口 2：开会话（已有的复用） ====================


@router.post(
    "/conversations",
    response_model=ConversationPublic,
    status_code=status.HTTP_201_CREATED,
    summary="和某人开会话（已有则复用）",
)
def open_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """会话去重：找得到“我和他”的会话就返回它，找不到才新建。

    必须去重：不去重的话，前端每点一次就会多出一个会话，
    """
    if payload.peer_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能和自己聊天，请选另一个人",
        )

    peer = db.get(User, payload.peer_id)
    if peer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这个用户不存在")

    conversation = _find_existing_conversation(current_user, peer, db)

    if conversation is None:
        # flush 把 INSERT 发给数据库，好让我们拿到自增 id（此时还没提交事务）
        conversation = Conversation()
        db.add(conversation)
        db.flush()

        # 登记两条成员记录：一条是我，一条是他，这个会话才算“属于我们俩”
        db.add(ConversationMember(conversation_id=conversation.id, user_id=current_user.id))
        db.add(ConversationMember(conversation_id=conversation.id, user_id=peer.id))

        db.commit()
        db.refresh(conversation)

    return _conversation_public(conversation, current_user, db)


# ==================== 接口 3：我的会话列表 ====================


@router.get("/conversations", response_model=list[ConversationPublic], summary="我的会话列表")
def list_my_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出我参与的所有会话，最近聊过的排最前面。

    过滤条件 ConversationMember.user_id == current_user.id 天然是一层权限边界：
    我永远只能看到自己参与的会话。

    已知不足：下面每个会话都要各查两次（对方是谁、最后一条消息），
    这叫 N+1 查询；本项目会话很少，为了代码好读没有做批量优化。
    """
    conversations = db.scalars(
        select(Conversation)
        .join(
            ConversationMember,
            ConversationMember.conversation_id == Conversation.id,
        )
        .where(ConversationMember.user_id == current_user.id)
        .order_by(Conversation.last_message_at.desc())
    ).all()

    return [_conversation_public(c, current_user, db) for c in conversations]


# ==================== 接口 4：发消息 ====================


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessagePublic,
    status_code=status.HTTP_201_CREATED,
    summary="发消息",
)
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """消息幂等：同一个 client_msg_id 提交两次，数据库里只会存下一条。

    网络不好时用户会重复点“发送”，不处理的话对方会收到两条一模一样的话。
    实现分两层：先查这个串存过没有，
    真遇到并发时再靠数据库的唯一约束兜底。
    """
    conversation = _get_my_conversation(conversation_id, current_user, db)

    # ---- 第一层：先查这个 client_msg_id 是不是已经存过 ----
    existing = db.scalar(select(Message).where(Message.client_msg_id == payload.client_msg_id))
    if existing is not None:
        # 存过，但属于别的会话：说明前端复用了旧串，直接报错让前端换一个
        if existing.conversation_id != conversation.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="这个 client_msg_id 已经被用过了，请换一个新的",
            )
        return _message_public(existing, _nickname_of(existing.sender_id, db))

    # ---- 正常插入一条新消息 ----
    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=payload.content,
        client_msg_id=payload.client_msg_id,
    )
    db.add(message)

    # 顺手更新会话的“最后消息时间”，会话列表就靠它排序
    conversation.last_message_at = utc_now()

    try:
        db.commit()
    except IntegrityError:
        # ---- 第二层：并发兜底 ----
        # 两个请求同时进来时第一层会双双查不到，最终靠 client_msg_id 的唯一约束分胜负
        db.rollback()
        existing = db.scalar(
            select(Message).where(Message.client_msg_id == payload.client_msg_id)
        )
        if existing is None:
            raise  # 不是重复提交引起的错误，照常抛出去，别吞掉
        return _message_public(existing, _nickname_of(existing.sender_id, db))

    db.refresh(message)
    return _message_public(message, current_user.nickname)


# ==================== 接口 5：收消息（首屏和轮询共用） ====================


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessagePublic],
    summary="收消息（首屏 / 轮询共用）",
)
def list_messages(
    conversation_id: int,
    after_id: int = Query(
        default=0,
        ge=0,
        description="只要比这个 id 更新的消息；传 0 表示“第一次进来，给我最近的一批”",
    ),
    limit: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="一次最多返回多少条",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """一个接口服务两种场景，靠 after_id 区分：

        after_id = 0  ->  刚点进会话，返回最近 limit 条
        after_id > 0  ->  正在轮询，返回比它新的消息

    两种情况的返回都按 id 正序（从旧到新）。
    收消息用轮询而不是服务端推送：实现最直白、最不容易出错，代价是固定 2 秒延迟。
    """
    conversation = _get_my_conversation(conversation_id, current_user, db)

    # 两次查询都 JOIN 了 User 把昵称一起取出来，一条 SQL 搞定，避免再逐条查昵称
    if after_id == 0:
        # 首屏：要“最近”的 limit 条，所以先倒序取，再翻回正序
        rows = db.execute(
            select(Message, User.nickname)
            .join(User, User.id == Message.sender_id)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id.desc())
            .limit(limit)
        ).all()
        rows = list(reversed(rows))
    else:
        # 轮询：只要比游标新的，正好命中 ix_message_conv_id(conversation_id, id) 索引
        rows = db.execute(
            select(Message, User.nickname)
            .join(User, User.id == Message.sender_id)
            .where(
                Message.conversation_id == conversation.id,
                Message.id > after_id,
            )
            .order_by(Message.id)
            .limit(limit)
        ).all()

    return [_message_public(message, nickname) for message, nickname in rows]
