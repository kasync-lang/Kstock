import logging
from typing import Annotated
import jwt
from cryptography.hazmat.primitives import serialization
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from markdown_it.rules_inline.state_inline import Delimiter
from pydantic import ValidationError
from app.core import security
from app.core import db
import os
from app.model.User import User
from app.schema.token import Token, TokenPayload
from beanie import PydanticObjectId
from app.schema.user import UserPublic
from app.core.config import KeyStore
from app.schema.user import UserBase
from app.core.config import settings
import logging
reuseable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/login/access-token",
)
TokenDep = Annotated[str, Depends(reuseable_oauth2)]





async def get_current_user(token:TokenDep) -> User:
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
    user = await User.get(PydanticObjectId(token_data.sub))

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
    user_dict["is_superuser"] = True if user_dict['role'] == 'admin' else False
    return UserPublic(**user_dict)

CurrentUser = Annotated[UserPublic, Depends(parse_user_db_to_currentuser)]

def get_current_active_superuser(current_user: CurrentUser) -> CurrentUser:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,detail="Does not enough permission"
        )
    return current_user


    