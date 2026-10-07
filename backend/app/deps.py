"""
deps.py —— FastAPI 的依赖函数。

get_current_user 是“需要登录才能访问”的开关：
接口参数里写上 current_user: User = Depends(get_current_user)，
没带 token / token 过期 / token 伪造的请求都会被拦下返回 401，
接口函数体里因此不用写任何鉴权代码。

token 放在请求头而不是 Cookie：跨域下更省事，前端也方便存进 localStorage。
"""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import parse_token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """从请求头 Authorization: Bearer <token> 里解析出当前登录用户。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("缺少登录凭证，请先登录")

    # “Bearer ” 正好 7 个字符，从第 7 位往后切就是 token 本身
    user_id = parse_token(authorization[7:].strip())
    if user_id is None:
        raise _unauthorized("登录凭证无效或已过期，请重新登录")

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("用户不存在，请重新登录")

    return user


def _unauthorized(message: str) -> HTTPException:
    """统一构造 401 错误，前端收到 401 就该回到登录页。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )
