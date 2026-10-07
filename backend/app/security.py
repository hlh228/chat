"""
security.py —— 密码加密，以及登录凭证（token）的签发与校验。

密码：不存明文。注册时随机生成“盐”，把 盐 + 密码 做 PBKDF2 哈希后存下来；
      登录时用同样的盐和轮数再算一遍，比对结果。哈希是单向的，偷走数据库也还原不出密码。

token：登录后签发，格式为  用户ID.过期时间.签名
      签名用服务端密钥算出，改了内容签名就对不上，所以不用查数据库就能判断真伪，
      也不需要单独建一张 token 表。
"""

import base64
import hashlib
import hmac
import secrets
import time

from .config import PBKDF2_ITERATIONS, SECRET_KEY, TOKEN_EXPIRE_MINUTES

_HASH_ALGORITHM = "sha256"
_SALT_BYTES = 16  # 16 字节盐，转成十六进制是 32 个字符
_TOKEN_SEPARATOR = "."


def generate_salt() -> str:
    """生成一个随机盐。每个用户一个，相同的密码也会算出不同密文。"""
    return secrets.token_hex(_SALT_BYTES)


def hash_password(password: str, salt: str) -> str:
    """把密码和盐一起做哈希，返回可以存进数据库的字符串。

    用 pbkdf2_hmac 而不是直接 sha256：它能指定“搅拌轮数”，故意让计算变慢。
    20 万轮约 0.1 秒，用户感觉不到，但暴力破解的成本提高了几万倍。
    """
    derived_key = hashlib.pbkdf2_hmac(
        _HASH_ALGORITHM,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return base64.b64encode(derived_key).decode("ascii")


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """校验密码是否正确。

    用 hmac.compare_digest 而不是 == ：后者遇到第一个不同字符就返回，
    比较耗时会有细微差别，能被用来一点点猜出密文（时序攻击）。
    """
    return hmac.compare_digest(hash_password(password, salt), expected_hash)


def create_token(user_id: int) -> str:
    """为用户签发 token，形如 12.1799999999.Xy7K9_A-8bQ2mZp。"""
    expires_at = int(time.time()) + TOKEN_EXPIRE_MINUTES * 60
    payload = f"{user_id}{_TOKEN_SEPARATOR}{expires_at}"
    return f"{payload}{_TOKEN_SEPARATOR}{_sign(payload)}"


def parse_token(token: str) -> int | None:
    """校验 token 并取出用户 ID；格式错、签名错、已过期都返回 None。"""
    parts = token.split(_TOKEN_SEPARATOR)
    if len(parts) != 3:  # 正常应该是 用户ID、过期时间、签名 三段
        return None

    user_id_text, expires_at_text, signature = parts
    payload = f"{user_id_text}{_TOKEN_SEPARATOR}{expires_at_text}"

    # 第一关：签名对不对（对不上说明是伪造的，或者内容被改过）
    if not hmac.compare_digest(_sign(payload), signature):
        return None

    # 第二关：里面的数字能正常转换吗（防止手工乱拼的字符串）
    try:
        user_id = int(user_id_text)
        expires_at = int(expires_at_text)
    except ValueError:
        return None

    # 第三关：过期了吗
    if expires_at < int(time.time()):
        return None

    return user_id


def _sign(payload: str) -> str:
    """用服务端密钥给一段文字生成签名（内部函数）。"""
    mac = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    # 转成 URL 安全的 Base64，再去掉结尾的等号让字符串短一点
    return base64.urlsafe_b64encode(mac.digest()).decode("ascii").rstrip("=")
