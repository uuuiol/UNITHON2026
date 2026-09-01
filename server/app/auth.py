"""회원가입/로그인 — 1단계: 인증 자체.

세션을 서버에 저장하지 않는다. 로그인 성공 시 서명된 토큰(JWT)을 돌려주고,
프론트는 요청마다 `Authorization: Bearer <token>` 헤더로 담아 보낸다.

`get_current_user`가 다음 단계(소유권 — Project/Test를 사용자별로 나누기)에서
그대로 재사용될 자리다. 지금은 이 함수를 쓰는 라우트가 `/api/auth/me` 하나뿐이다.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .models import User

log = logging.getLogger(__name__)

# 운영 배포 시엔 반드시 고정값을 줘야 한다 — 안 주면 서버가 재시작될 때마다
# 새로 만들어져서 그전에 발급된 토큰이 전부 무효가 된다(=전원 로그아웃).
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    log.warning(
        "JWT_SECRET 환경변수가 없어 임의 값으로 대신합니다. "
        "서버를 재시작하면 기존 로그인이 전부 풀립니다 — 배포 시엔 반드시 고정값을 주세요."
    )

JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=7)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    """소문자로 맞추고 형식을 검사한다. 회원가입과 프로필 수정이 같이 쓴다."""
    value = value.strip().lower()
    if not EMAIL_RE.match(value):
        raise ValueError("이메일 형식이 올바르지 않습니다.")
    return value


class SignupIn(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=50)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return normalize_email(value)


class LoginIn(BaseModel):
    email: str
    password: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_user_id(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.") from exc


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """보호된 라우트가 쓰는 의존성. 헤더가 없거나 토큰이 무효하면 401."""
    header = request.headers.get("Authorization") or ""
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    user_id = _decode_user_id(header.removeprefix("Bearer ").strip())
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user


def user_out(user: User) -> dict:
    return {"id": str(user.id), "email": user.email, "name": user.name, "workspace": user.workspace}
