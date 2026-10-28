import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from app.core import crud
from app.api.deps import CurrentAccount, get_current_active_superuser, CurrentUser
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.core import mail
from app.schema.user import UsersPublic, UserCreate, Message, UserPublic
from app.model.User import Oauth2Account, User
from app.api.deps import parse_user_db_to_currentuser
from app.schema.user import UserUpdateMe, UpdatePassword, UserUpdate
from beanie import PydanticObjectId


router = APIRouter(prefix="/user", tags=["user"])
@router.get("/", dependencies=[Depends(get_current_active_superuser)],response_model=UsersPublic)

async def read_users(skip:int = 1, limit:int = 100) -> Any:
    skip_count = (skip - 1) * limit
    users_from_db = await User.find({}).skip(skip_count).limit(limit).to_list(length=limit)
    data_user = []
    for user in users_from_db:
        data_user.append(parse_user_db_to_currentuser(user))
    return UsersPublic(data=data_user)
@router.post("/", dependencies=[Depends(get_current_active_superuser)],response_model=UserPublic)
async def create_user(user_in: UserCreate) -> Any:
    user_db  = await crud.get_user_by_email(email=user_in.email)
    if user_db:
        raise HTTPException(status_code=409, detail="User already exists")
    user_db = await crud.create_user(user_create=user_in)
    if user_db.email:
        await mail.send_email(
            template="new_account",
            to=user_in.email,
            data={
                "username": user_in.email,
                "password": user_in.password,
                "link": settings.FRONTEND_HOST,
            },
        )

    logging.warning(f"New user created: {user_db.email}")
    return parse_user_db_to_currentuser(user_db)
@router.patch("/me", response_model=UserPublic)
async def update_user_me(*, user_in: UserUpdateMe, current_user: CurrentUser, current_account: CurrentAccount) -> Any:
    if isinstance(current_account, Oauth2Account):
        raise HTTPException(status_code=400, detail="OAuth account profile is managed by its provider")
    if user_in.email:
        exiting_user = await crud.get_user_by_email(email=user_in.email)
        if exiting_user and exiting_user.id != current_user.id:
            raise HTTPException(status_code=409, detail="User with this email already exists")
    user_data = user_in.model_dump(exclude_unset=True)
    userdb = await User.find_one(User.id == current_user.id)
    await userdb.update({"$set": user_data})

    updated_user = await User.find_one(User.id == current_user.id)
    return parse_user_db_to_currentuser(updated_user)

@router.patch("/me/password", response_model=Message)
async def update_user_password_me(body: UpdatePassword, current_account: CurrentAccount) -> Any:
    if isinstance(current_account, Oauth2Account):
        raise HTTPException(status_code=400, detail="OAuth accounts do not have a local password")
    if not verify_password(body.current_password, current_account.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="New password can not be the same current password")
    hashed_password = get_password_hash(body.new_password)
    await User.find_one(User.id == current_account.id).update({"$set": {"hashed_password": hashed_password}})
    return Message(message="Password updated successfully")
@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    return current_user
@router.delete("/me", response_model=Message)
async def delete_user_me(current_user: CurrentUser, current_account: CurrentAccount) -> Any:
    if current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser can not be deleted yourself")
    try:
        current_account.is_actived = False
        await current_account.save()
    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=400, detail="Something went wrong")

    return Message(message="User deleted successfully")

@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(user_id: str, current_user: CurrentUser) -> Any:
    try:
        account_id = PydanticObjectId(user_id)
    except (TypeError, ValueError, InvalidId):
        raise HTTPException(status_code=404, detail="User not found in system")

    user = await User.get(account_id)
    if not user:
        user = await Oauth2Account.get(account_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found in system")
    if str(user.id) == current_user.id:
        return parse_user_db_to_currentuser(user)
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Forbidden")
    return parse_user_db_to_currentuser(user)

@router.patch("/{user_id}", response_model=UserPublic, dependencies=[Depends(get_current_active_superuser)])
async def update_user(user_id: str, user_in: UserUpdate) -> Any:
    try:
        object_id = ObjectId(user_id)
    except (TypeError, ValueError, InvalidId):
        raise HTTPException(status_code=404, detail="User not found in system")
    db_user = await User.find_one(User.id == object_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found in system")
    if user_in.email:
        exiting_user = await crud.get_user_by_email(email=user_in.email)
        if exiting_user and exiting_user.id != user_id:
            raise HTTPException(status_code=409, detail="User with this email already exists")
    user_db = await User.find_one(User.id == user_id).update({"$set": user_in.model_dump(exclude_unset=True)})
    return parse_user_db_to_currentuser(user_db)

@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_user(user_id: str, current_user: CurrentUser) -> Message:
    try:
        object_id = ObjectId(user_id)
    except (TypeError, ValueError, InvalidId):
        raise HTTPException(status_code=404, detail="User not found in system")
    user = await User.find_one(User.id == object_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found in system")
    if user.id == ObjectId(current_user.id):
        raise HTTPException(status_code=403, detail="Can not delete superuser yourself")
    if user:
        user.is_actived = False
    else:
        raise HTTPException(status_code=404, detail="User not found in system")
    return Message(message="User deleted successfully")






