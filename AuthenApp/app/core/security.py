from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
import bcrypt
from app.core.config import KeyStore
from app.core.config import settings
import re

ALGORITHM = settings.ALGORITHM


def create_access_token(subject: str | Any, expires_delta: timedelta):
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        payload=to_encode,
        key=KeyStore.private_key,
        algorithm=ALGORITHM,
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    print(password, type(password), len(password.encode()))
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def is_strong_password(plain_password: str) -> bool:
    pattern = r'^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*\W)(?!.* ).{8,}$'
    return bool(re.match(pattern, plain_password))
