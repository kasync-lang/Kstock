from typing import Any

from app.core.security import get_password_hash, verify_password
from app.schema.user import UserCreate, UserUpdate
from app.model.User import User, Oauth2Account


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
    user_data = user_in.model_dump(exclude_unset=True)
    password = user_data.pop("password", None)
    if password:
        db_user.hashed_password = get_password_hash(password)
    if "email" in user_data and user_data["email"] is not None:
        db_user.email = user_data["email"]
    if "full_name" in user_data:
        db_user.full_name = user_data["full_name"]
    if "is_actived" in user_data:
        db_user.is_actived = user_data["is_actived"]
    await db_user.save()
    return db_user




async def get_user_by_email(*, email:str) -> User | None:
    return await User.find_one(User.email==email)

async def get_oauth_account_by_email(*, email: str) -> Oauth2Account | None:

    return await Oauth2Account.find_one(Oauth2Account.email==email)


async def authenticate(*,email:str, password:str) -> User | None:
    db_user = await get_user_by_email(email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user

async def create_oauth2_account(*, oauth_account: Oauth2Account) -> Oauth2Account:
    user_data = oauth_account.model_dump()
    db_obj = Oauth2Account(**user_data)
    db_user = await get_oauth_account_by_email(email=user_data["email"])
    if db_user:
        return db_obj
    else:
        await db_obj.save()
    return db_obj





