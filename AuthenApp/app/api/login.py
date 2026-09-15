import logging
from datetime import timedelta
from typing import Annotated, Any
import requests
from google_auth_oauthlib.flow import Flow
import secrets
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.schema.token import Token
from app.core import crud
from app.core import security
from app.schema.user import UserPublic, NewPassword, Message, UserCreate, UserRegister, Oauth2AccountBase
from app.utils import verify_password_reset_token
from app.utils import ( generate_password_reset_token,
                        generate_reset_password_email,
                        generate_signup_verify_email,
send_email,
                        )
from app.core.security import is_strong_password
from app.api.deps import CurrentUser, parse_user_db_to_currentuser, get_redis
from app.core.config import settings
from fastapi import BackgroundTasks, Request
from app.model.User import User, Oauth2Account
from fastapi.responses import RedirectResponse
SCOPES = ['https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'openid']
router = APIRouter(tags=["login"])
@router.post("/login/access-token")
async def login_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    user = await crud.authenticate(email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_actived:
        raise HTTPException(status_code=403, detail="Inactive user")
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
            return
        user_create = UserCreate.model_validate(user_in.model_dump(exclude_unset=True))
        email_data = generate_signup_verify_email(email=user_in.email, token=generate_password_reset_token(user_in.email))
        background_tasks.add_task(send_email,email_to = user_in.email, subject=email_data.subject, html_content=email_data.html_content )
        if not user:
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
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="User already verified")

    try:
        user.is_verified=True
        user.is_actived=True
        await user.save(ignore_revision=False)
        return Message(message="User verified successfully")
    except Exception as e:
        logging.log(logging.WARN, f"Error verifying user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/login/test-token", response_model= UserPublic)
async def login_test_token(current_user: CurrentUser) ->Any:
    return current_user

@router.post("/reset-password") # User for user reset own password when forgot throw mail, not for admin reset user password
async def reset_password(body: NewPassword) -> Message:
    email = verify_password_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await crud.get_user_by_email(email= email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    elif not user.is_actived:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = security.get_password_hash(password= body.new_password)
    user.hashed_password = hashed_password
    new_user = await user.save()
    if not new_user:
        raise HTTPException(status_code=400, detail="Something went wrong")
    return Message(message="Password update successfuly")

@router.post("/password-recovery/{email}") # trigger send mail to reset password
async def recover_password(email: str) -> Message:
    user = await crud.get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=404, detail="This user is not registered")
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(email_to= user.email, email=email, token=password_reset_token)
    send_email(email_to=user.email, subject= email_data.subject, html_content=email_data.html_content)
    return Message(message="Password recovery email sent")

@router.get("/auth/google")
async def auth_google():
    path_secrets = settings.GOOGLE_CLIENT_SECRET_PATH
    flow = Flow.from_client_secrets_file(
        path_secrets,
        scopes=SCOPES,
        redirect_uri=settings.CALLBACK_URL,

    )
    flow.redirect_uri = settings.CALLBACK_URL
    authorization_url, state = flow.authorization_url(
        state=secrets.token_urlsafe(32),
        code_challenge_method='S256'
    )
    response = RedirectResponse(authorization_url)

    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=False,  # localhost HTTP thì tạm False
        samesite="lax",
        max_age=300,
    )
    response.set_cookie(
    key="oauth_code_verifier",
    value=flow.code_verifier,
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=300,
)
    return response

@router.get("/auth/google/callback")
async def callback(request: Request, redis = Depends(get_redis)):
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    url_get_userinfo = "https://www.googleapis.com/oauth2/v2/userinfo"

    cookie_state = request.cookies.get("oauth_state")
    code_verifier = request.cookies.get("oauth_code_verifier")
    if not state or state != cookie_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")

    if not code_verifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code verifier")

    flow = Flow.from_client_secrets_file(
        settings.GOOGLE_CLIENT_SECRET_PATH,
        scopes=SCOPES,
        state=state,
        redirect_uri=settings.CALLBACK_URL,
    )
    flow.redirect_uri = 'http://localhost:8080/auth/google/callback'
    flow.code_verifier=code_verifier
    try:
        flow.fetch_token(code=code, code_verifier=code_verifier)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Authentication failed: {str(e)}")
    credentials = flow.credentials
    #check granted scopes
    if SCOPES[0] not in credentials.scopes or SCOPES[1] not in credentials.scopes or SCOPES[2] not in credentials.scopes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required scopes")

    response = requests.get(url_get_userinfo, headers={"Authorization": f"Bearer {credentials.token}"})
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch user info")
    user_info = response.json()
    email, name = user_info.get("email"), user_info.get("name")

    oauth_account = await crud.get_oauth_account_by_email(email=email)
    if not oauth_account:
        oauth_account_create = Oauth2Account(
            provider="google",
            email=email,
            provider_account_id=user_info.get("id"),
            scope=credentials.scopes,
            name=name,
            is_actived=True,

        )
        oauth_account = await crud.create_oauth2_account(oauth_account=oauth_account_create)

    codeexchange = secrets.token_urlsafe(32)
    await redis.set(f"oauth_code:{codeexchange}", str(oauth_account.id), ex=120)
    return RedirectResponse(f"{settings.FRONTEND_URL}/oauth/exchange?code={codeexchange}")
@router.post("/oauth/exchange")
async def echange(code: str, redis = Depends(get_redis)):
    user_id = await redis.getdel(f"oauth_code:{code}")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            subject=user_id.decode("utf-8"), expires_delta=access_token_expires
        )
    )