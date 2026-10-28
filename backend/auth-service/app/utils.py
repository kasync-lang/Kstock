from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import KeyStore, settings


def verify_password_reset_token(token:str) -> str| None:
    try:
        decoded_token = jwt.decode(token, key= KeyStore.public_key, algorithms=[settings.ALGORITHM])
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None
def generate_password_reset_token(email:str) -> str:
    delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp":exp,"nbf":now,"sub":email},
        KeyStore.private_key,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt
