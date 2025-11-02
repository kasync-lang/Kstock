from datetime import timedelta
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.schema.token import Token
from app.core import crud
from app.core import security
from app.api.deps import get_current_active_superuser
from app.schema.user import UserPublic, NewPassword, Message, UserCreate, UserRegister
from app.utils import verify_password_reset_token
from fastapi.responses import HTMLResponse
from app.utils import ( generate_password_reset_token,
                        generate_reset_password_email,
                        generate_signup_verify_email,
send_email,
                        )
from app.core.security import is_strong_password
from app.api.deps import CurrentUser, parse_user_db_to_currentuser
from app.core.config import settings
from fastapi import BackgroundTasks
from app.model.User import User


router = APIRouter(tags=["login"])
@router.post("/login/access-token")
async def login_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    user = await crud.authenticate(email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_actived:
        raise HTTPException(status_code=400, detail="Inactive user")
    elif not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not verified")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    return Token(
        access_token=security.create_access_token(
            subject=user.id, expires_delta=access_token_expires
        )
    )


@router.post("/signup", response_model=UserPublic)
async def register_user(user_in: UserRegister, background_tasks: BackgroundTasks):
    user = await crud.get_user_by_email(email=user_in.email)
    if not user or not user.is_verified:
        if not is_strong_password(user_in.password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too weak")
        if user.is_verified:
            await User.find_one(User.id == ObjectId(user_in.user_id)).delete()
        user_create = UserCreate.model_validate(user_in.model_dump(exclude_unset=True))
        email_data = generate_signup_verify_email(email=user_in.email, token=generate_password_reset_token(user_in.email))
        background_tasks.add_task(send_email,email_to = user_in.email, subject=email_data.subject, html_content=email_data.html_content )
        user = await crud.create_user(user_create=user_create)
    else:
        raise HTTPException(status_code=409, detail="User already exists")
    return parse_user_db_to_currentuser(user)

@router.get("/signup-verify", response_model=Message)
async def signup_verify(token:str):
    email = verify_password_reset_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await crud.get_user_by_email(email=email)
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Token expired")
    User.find_one(email=email).update({"is_verified": True})
    await user.save(ignore_revision=True)
    return Message(message="User verified successfully")


@router.post("/login/test-token", response_model= UserPublic)
async def login_test_token(current_user: CurrentUser) ->Any:
    return current_user

@router.post("/reset-password")
async def reset_password(body: NewPassword) -> Message:
    email = verify_password_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await crud.get_user_by_email(email= email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = security.get_password_hash(password= body.new_password)
    user.hashed_password = hashed_password
    return Message(message="Password update successfuly")

@router.post("/password-recovery/{email}")
async def recover_password(email: str) -> Message:
    user = await crud.get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=404, detail="This user is not registered")
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(email_to= user.email, email=email, token=password_reset_token)
    send_email(email_to=user.email, subject= email_data.subject, html_content=email_data.html_content)
    return Message(message="Password recovery email sent")
@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
async def recover_password_html_content(email: str, ) -> Any:
    user = await crud.get_user_by_email(email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )

