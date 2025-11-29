from datetime import  datetime, timedelta, timezone
from typing import Any
import jwt
from fastapi import FastAPI

from app.core.config import KeyStore
from app.core.config import settings

from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
import re
ALGORITHM = settings.ALGORITHM


def create_access_token(subject: str| Any, expires_delta: timedelta):
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        payload= to_encode,
        key=KeyStore.private_key,
        algorithm=ALGORITHM,
    )
    return encoded_jwt
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
def is_strong_password(plain_password:str) -> bool:
    pattern = r'^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*\W)(?!.* ).{8,}$'
    return bool(re.match(pattern, plain_password))

