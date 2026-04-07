import uuid
from typing import Any, Optional

from app.core.security import get_password_hash, verify_password
from app.schema.token import Token, TokenPayload
from app.schema.user import UserCreate, UserUpdate
from app.model.User import User




async def create_user(*, user_create: UserCreate) -> User:
    # Remove password from user_create data before validation
    user_data = user_create.model_dump(exclude={"password","is_superuser"})
    user_data["hashed_password"] = get_password_hash(user_create.password)
    user_data["role"] = "basic_user" #default role
    db_obj = User(**user_data)
    db_user = await get_user_by_email(email=user_data["email"])
    if db_user:
        return db_obj
    else:
        await db_obj.save()
    return db_obj


async def update_user(*, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude={"password"})
    if "password" in user_data:
        user_data["hashed_password"] = get_password_hash(user_data["password"])
    db_user.hashed_password = user_data["hashed_password"]
    db_user.email = user_data["email"]
    db_user.save()
    return db_user




async def get_user_by_email(*, email:str) -> User | None:
    return await User.find_one(User.email==email)


async def authenticate(*,email:str, password:str) -> User | None:
    db_user = await get_user_by_email(email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user





