import logging
from typing import Annotated
import jwt
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from app.model.User import Oauth2Account, User
from app.schema.token import TokenPayload
from beanie import PydanticObjectId
from app.schema.user import UserPublic
from app.core.config import KeyStore
from app.core.config import settings
reuseable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.PREFIX_API}/login/access-token",
)
TokenDep = Annotated[str, Depends(reuseable_oauth2)]

from fastapi import Request


def get_redis(request: Request):
    return request.app.state.redis





async def get_current_user(token:TokenDep) -> User | Oauth2Account:
    try:
        payload  = jwt.decode(
            token,key = KeyStore.public_key,
            algorithms = [settings.ALGORITHM],
            options = {"verify_exp": True},
        )
        logging.log(1, payload)
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    try:
        account_id = PydanticObjectId(token_data.sub)
    except (TypeError, ValueError, InvalidId):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
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
            status_code = status.HTTP_400_BAD_REQUEST, detail="Inactive user"
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
            status_code=status.HTTP_403_FORBIDDEN,detail="Does not enough permission"
        )
    return current_user


    