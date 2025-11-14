import uuid
import datetime
import jwt
from passlib.context import CryptContext
from .config import SECRET
from ..db import redis_client

pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def create_access_token(user_id, tenant_id, ttl=3600):
    exp = datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl)
    return jwt.encode({"sub": user_id, "tenant_id": tenant_id, "exp": exp}, SECRET, algorithm="HS256")


def mint_refresh_token(user_id, tenant_id, ttl=60*60*24*7):
    jti = str(uuid.uuid4())
    key = f"rt:{jti}"
    redis_client.set(key, f"{user_id}:{tenant_id}", ex=ttl)
    return jti


def revoke_refresh_token(jti):
    redis_client.delete(f"rt:{jti}")


def is_refresh_valid(jti):
    return redis_client.exists(f"rt:{jti}") == 1


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])
