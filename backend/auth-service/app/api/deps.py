import logging
from typing import Annotated
import jwt
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.model.User import Oauth2Account, User
from app.schema.token import TokenPayload
from beanie import PydanticObjectId
from app.schema.user import UserPublic
from app.core.config import KeyStore
from app.core.config import settings

TOKEN_ERROR_EXPIRED = {
    "code": "ACCESS_TOKEN_EXPIRED",
    "message": "Access token has expired",
}
TOKEN_ERROR_INVALID = {
    "code": "INVALID_TOKEN",
    "message": "Token is invalid",
}
TOKEN_ERROR_MISSING = {
    "code": "MISSING_TOKEN",
    "message": "Bearer token is required",
}


class CustomOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> str:
        authorization = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer" or not param:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=TOKEN_ERROR_MISSING,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return param


reuseable_oauth2 = CustomOAuth2PasswordBearer(
    tokenUrl=f"{settings.PREFIX_API}/login/access-token",
    auto_error=False,
)
TokenDep = Annotated[str, Depends(reuseable_oauth2)]


async def auth_http_exception_handler(request: Request, exc: StarletteHTTPException):
    headers = getattr(exc, "headers", None)
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
            headers=headers,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(HTTPException, auth_http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, auth_http_exception_handler)


def get_redis(request: Request):
    return request.app.state.redis


async def get_current_user(token: TokenDep) -> User | Oauth2Account:
    try:
        payload = jwt.decode(
            token,
            key=KeyStore.public_key,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": True},
        )
        logging.log(1, payload)
        token_data = TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=TOKEN_ERROR_EXPIRED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=TOKEN_ERROR_INVALID,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        account_id = PydanticObjectId(token_data.sub)
    except (TypeError, ValueError, InvalidId):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=TOKEN_ERROR_INVALID,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await User.get(account_id)
    if not user:
        user = await Oauth2Account.get(account_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if not user.is_actived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return user


def parse_user_db_to_currentuser(user=Depends(get_current_user)):
    user_dict = dict(user)
    user_dict["id"] = str(user_dict["id"])
    if isinstance(user, Oauth2Account):
        user_dict["full_name"] = user_dict.get("name")
        user_dict["provider"] = getattr(user, "provider", "google")
    else:
        user_dict["provider"] = None
    user_dict["is_superuser"] = user_dict.get("role") == "admin"
    return UserPublic(**user_dict)


CurrentUser = Annotated[UserPublic, Depends(parse_user_db_to_currentuser)]
CurrentAccount = Annotated[User | Oauth2Account, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> CurrentUser:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Does not enough permission"
        )
    return current_user
