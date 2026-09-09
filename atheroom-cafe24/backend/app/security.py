import base64, hashlib, hmac, os, secrets
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from app.config import settings
from app.db import get_db
from app.models import User, LoginSession

def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def utc(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def password_hash(password):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + key).decode()
def verify_password(password, encoded):
    try:
        raw = base64.b64decode(encoded)
        return hmac.compare_digest(raw[16:], hashlib.scrypt(password.encode(), salt=raw[:16], n=16384, r=8, p=1))
    except (ValueError, TypeError): return False

def cipher():
    if not settings.token_encryption_key: raise HTTPException(503, '연결 준비가 필요합니다. 운영 담당자에게 문의해주세요.')
    return Fernet(settings.token_encryption_key.encode())
def encrypt(value): return cipher().encrypt(value.encode()).decode()
def decrypt(value): return cipher().decrypt(value.encode()).decode()

def current_user(request: Request, db=Depends(get_db)):
    token = request.cookies.get('studio_session', '')
    session = db.get(LoginSession, digest(token)) if token else None
    if not session or utc(session.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(401, '로그인 후 이용해주세요.')
    user = db.get(User, session.user_id)
    if not user: raise HTTPException(401, '다시 로그인해주세요.')
    return user

def admin(user=Depends(current_user)):
    if user.role != 'ADMIN': raise HTTPException(403, '관리자만 이용할 수 있습니다.')
    return user
