"""
routers/auth.py —— 账号相关的 3 个接口：

    POST /api/auth/register   注册（注册成功直接发 token，不用再登录一次）
    POST /api/auth/login      登录
    GET  /api/auth/me         我是谁（前端刷新页面后用它确认 token 还有效）
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, utc_now
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from ..security import create_token, generate_salt, hash_password, verify_password

# prefix 让这个文件里所有接口都自动带上 /api/auth 前缀；tags 只影响 /docs 的分组显示
router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册新用户",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """注册新账号，成功后返回 token 和用户信息。"""
    # 先查一下登录名有没有被占用。（这一步只为给出友好提示，
    # 真正保证不重复的是数据库上 username 的唯一索引）
    existing_user = db.scalar(select(User).where(User.username == payload.username))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该用户名已被占用，换一个吧",
        )

    # 生成盐，再用盐把密码搅成密文；数据库里存的是 salt 和 password_hash，都不是原始密码
    salt = generate_salt()
    new_user = User(
        username=payload.username,
        nickname=payload.nickname or payload.username,  # 昵称留空就用登录名
        salt=salt,
        password_hash=hash_password(payload.password, salt),
    )
    db.add(new_user)
    db.commit()
    # refresh 把数据库生成的 id、created_at 读回来，否则 new_user.id 还是 None，没法签 token
    db.refresh(new_user)

    return TokenResponse(
        token=create_token(new_user.id),
        user=UserPublic.model_validate(new_user),
    )


@router.post("/login", response_model=TokenResponse, summary="登录")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """用登录名和密码换 token。

    “用户不存在”和“密码错误”返回同一句提示：分开提示的话，
    攻击者能靠反馈一个个试出系统里有哪些账号（用户名枚举攻击）。
    """
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.salt, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
        )

    user.last_seen_at = utc_now()  # 顺手记一下最后活跃时间
    db.commit()

    return TokenResponse(
        token=create_token(user.id),
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic, summary="获取当前登录用户")
def read_current_user(current_user: User = Depends(get_current_user)):
    """返回 token 对应的用户。返回 200 说明 token 还有效，返回 401 就该重新登录。

    参数里写了 Depends(get_current_user)，本接口就自动变成“必须登录才能访问”，
    没带 token 的请求进不到函数体，所以函数体里不用写任何鉴权代码。
    """
    return UserPublic.model_validate(current_user)
