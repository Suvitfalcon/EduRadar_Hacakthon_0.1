"""EduRadar teacher authentication using server-side SQLite sessions.

Do not commit real teacher passwords. Configure bootstrap credentials via env.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from time import monotonic

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, delete

from .db import Teacher, TeacherSession, get_session

router = APIRouter(prefix="/api/auth", tags=["teacher authentication"])
COOKIE = "eduradar_session"
SESSION_HOURS = 12
FAILED = defaultdict(list)


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digest(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return f"pbkdf2_sha256$310000${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        method, count, salt, saved = stored.split("$")
        if method != "pbkdf2_sha256":
            return False
        result = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(count))
        return hmac.compare_digest(result, bytes.fromhex(saved))
    except (ValueError, TypeError):
        return False


def bootstrap_teacher():
    username = os.environ.get("EDURADAR_TEACHER_USERNAME", "").strip().lower()
    password = os.environ.get("EDURADAR_TEACHER_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("Set EDURADAR_TEACHER_USERNAME and EDURADAR_TEACHER_PASSWORD before starting")
    if len(password) < 12:
        raise RuntimeError("EDURADAR_TEACHER_PASSWORD must have at least 12 characters")
    with get_session() as s:
        teacher = s.execute(select(Teacher).where(Teacher.username == username)).scalar_one_or_none()
        if teacher is None:
            s.add(Teacher(username=username, display_name=os.environ.get("EDURADAR_TEACHER_NAME", username),
                          password_hash=hash_password(password)))
            s.commit()
        # Credentials don't rotate on each restart. Use change_teacher_password.py to rotate them.


def lookup_teacher(request: Request):
    token = request.cookies.get(COOKIE, "")
    if not token:
        return None
    with get_session() as s:
        record = s.execute(select(TeacherSession).where(TeacherSession.token_hash == digest(token))).scalar_one_or_none()
        if not record or record.expires_at <= now():
            return None
        teacher = s.get(Teacher, record.teacher_id)
        if not teacher or not teacher.active:
            return None
        return {"id": teacher.id, "username": teacher.username, "display_name": teacher.display_name,
                "csrf_hash": record.csrf_hash}


def cookie_secure(request: Request):
    override = os.environ.get("EDURADAR_COOKIE_SECURE")
    if override is not None:
        return override == "1"
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1)


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response):
    ip = request.client.host if request.client else "unknown"
    current = monotonic()
    FAILED[ip] = [x for x in FAILED[ip] if current - x < 900]
    if len(FAILED[ip]) >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes")
    with get_session() as s:
        teacher = s.execute(select(Teacher).where(Teacher.username == body.username.strip().lower())).scalar_one_or_none()
        # Constant-work comparison even for nonexistent usernames
        valid = verify_password(body.password, teacher.password_hash if teacher else hash_password("dummy-login-placeholder"))
        if not teacher or not teacher.active or not valid:
            FAILED[ip].append(current)
            raise HTTPException(401, "Invalid username or password")
        FAILED.pop(ip, None)
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        s.add(TeacherSession(teacher_id=teacher.id, token_hash=digest(token), csrf_hash=digest(csrf),
                             expires_at=now() + timedelta(hours=SESSION_HOURS)))
        s.commit()
        response.set_cookie("eduradar_csrf", csrf, httponly=False, secure=cookie_secure(request), samesite="strict",
                            max_age=SESSION_HOURS * 3600, path="/")
        response.set_cookie(COOKIE, token, httponly=True, secure=cookie_secure(request), samesite="lax",
                            max_age=SESSION_HOURS * 3600, path="/")
        return {"username": teacher.username, "display_name": teacher.display_name, "csrf_token": csrf}


@router.get("/me")
def me(request: Request):
    teacher = lookup_teacher(request)
    if not teacher:
        raise HTTPException(401, "Please log in")
    return {"username": teacher["username"], "display_name": teacher["display_name"]}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        with get_session() as s:
            s.execute(delete(TeacherSession).where(TeacherSession.token_hash == digest(token)))
            s.commit()
    response.delete_cookie(COOKIE, path="/")
    response.delete_cookie("eduradar_csrf", path="/")
    return {"ok": True}
