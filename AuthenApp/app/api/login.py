import json
import logging
from datetime import timedelta
from typing import Annotated, Any
import requests
from google_auth_oauthlib.flow import Flow
import secrets
from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from app.schema.token import Token
from app.core import crud
from app.core import security
from app.core import session as session_manager
from app.schema.user import UserPublic, NewPassword, Message, UserCreate, UserRegister, Oauth2AccountBase
from app.utils import verify_password_reset_token
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    generate_signup_verify_email,
    send_email,
)
from app.core.security import is_strong_password
from app.api.deps import CurrentUser, parse_user_db_to_currentuser, get_redis
from app.core.config import settings
from app.model.User import User, Oauth2Account

SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
]
router = APIRouter(tags=["login"])


@router.post("/login/access-token")
async def login_access_token(
    response: Response,
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    redis=Depends(get_redis),
) -> Token:
    user = await crud.authenticate(email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_actived:
        raise HTTPException(status_code=403, detail="Inactive user")
    elif not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not verified")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    if redis:
        session_id, refresh_token = await session_manager.create_refresh_session(
            redis=redis,
            user_id=str(user.id),
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
        session_manager.set_refresh_token_cookie(response, refresh_token)

    return Token(access_token=access_token)


@router.post("/auth/refresh", response_model=Token)
async def refresh_access_token(
    request: Request,
    response: Response,
    redis=Depends(get_redis),
) -> Token:
    raw_refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
            headers=session_manager.get_cleared_cookie_headers(),
        )

    user_id, session_id, new_refresh_token = await session_manager.rotate_refresh_token(
        redis=redis,
        raw_refresh_token=raw_refresh_token,
    )

    # Verify that user exists and is active
    try:
        account_id = PydanticObjectId(user_id)
    except (TypeError, ValueError, InvalidId):
        session_manager.clear_refresh_token_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers=session_manager.get_cleared_cookie_headers(),
        )

    user = await User.get(account_id)
    if not user:
        user = await Oauth2Account.get(account_id)

    if not user:
        await session_manager.revoke_session(redis, session_id)
        session_manager.clear_refresh_token_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            headers=session_manager.get_cleared_cookie_headers(),
        )

    if not user.is_actived:
        await session_manager.revoke_session(redis, session_id)
        session_manager.clear_refresh_token_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
            headers=session_manager.get_cleared_cookie_headers(),
        )

    # Issue new short-lived access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = security.create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    session_manager.set_refresh_token_cookie(response, new_refresh_token)

    return Token(access_token=new_access_token)


@router.post("/auth/logout", response_model=Message)
async def logout(
    request: Request,
    response: Response,
    redis=Depends(get_redis),
) -> Message:
    raw_refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if raw_refresh_token and redis:
        token_hash = session_manager.hash_refresh_token(raw_refresh_token)
        token_entry_raw = await redis.get(f"refresh_token:{token_hash}")
        if token_entry_raw:
            try:
                token_data = json.loads(token_entry_raw)
                session_id = token_data.get("session_id")
                if session_id:
                    await session_manager.revoke_session(redis, session_id)
            except Exception:
                pass
            await redis.delete(f"refresh_token:{token_hash}")
    session_manager.clear_refresh_token_cookie(response)
    return Message(message="Successfully logged out")


@router.post("/signup", response_model=UserPublic)
async def register_user(user_in: UserRegister, background_tasks: BackgroundTasks):
    user = await crud.get_user_by_email(email=user_in.email)
    if not user or not user.is_verified:
        if not is_strong_password(user_in.password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too weak")
            return
        user_create = UserCreate.model_validate(user_in.model_dump(exclude_unset=True))
        email_data = generate_signup_verify_email(
            email=user_in.email, token=generate_password_reset_token(user_in.email)
        )
        background_tasks.add_task(
            send_email,
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        if not user:
            user = await crud.create_user(user_create=user_create)
    else:
        raise HTTPException(status_code=409, detail="User already exists")
    return parse_user_db_to_currentuser(user)


@router.get("/signup-verify", response_model=Message)
async def signup_verify(token: str):
    email = verify_password_reset_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await crud.get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="User already verified")

    try:
        user.is_verified = True
        user.is_actived = True
        await user.save(ignore_revision=False)
        return Message(message="User verified successfully")
    except Exception as e:
        logging.log(logging.WARN, f"Error verifying user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/login/test-token", response_model=UserPublic)
async def login_test_token(current_user: CurrentUser) -> Any:
    return current_user


@router.post("/reset-password")
async def reset_password(body: NewPassword) -> Message:
    email = verify_password_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await crud.get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    elif not user.is_actived:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = security.get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    new_user = await user.save()
    if not new_user:
        raise HTTPException(status_code=400, detail="Something went wrong")
    return Message(message="Password update successfuly")


@router.post("/password-recovery/{email}")
async def recover_password(email: str) -> Message:
    user = await crud.get_user_by_email(email=email)
    if not user:
        raise HTTPException(status_code=404, detail="This user is not registered")
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    send_email(
        email_to=user.email, subject=email_data.subject, html_content=email_data.html_content
    )
    return Message(message="Password recovery email sent")


@router.get("/auth/google")
async def auth_google():
    path_secrets = settings.GOOGLE_CLIENT_SECRET_PATH
    flow = Flow.from_client_secrets_file(
        path_secrets,
        scopes=SCOPES,
        redirect_uri=settings.google_oauth.redirect_uris[0],
    )
    flow.redirect_uri = settings.google_oauth.redirect_uris[0]
    authorization_url, state = flow.authorization_url(
        state=secrets.token_urlsafe(32), code_challenge_method='S256'
    )
    response = RedirectResponse(authorization_url)
    print("authorization_url: ", flow.redirect_uri)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=False,
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
async def callback(request: Request, redis=Depends(get_redis)):
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
        redirect_uri=settings.google_oauth.redirect_uris[0],
    )
    flow.redirect_uri = settings.google_oauth.redirect_uris[0]
    flow.code_verifier = code_verifier
    try:
        flow.fetch_token(code=code, code_verifier=code_verifier)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}",
        )
    credentials = flow.credentials
    if (
        SCOPES[0] not in credentials.scopes
        or SCOPES[1] not in credentials.scopes
        or SCOPES[2] not in credentials.scopes
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required scopes"
        )

    response = requests.get(
        url_get_userinfo, headers={"Authorization": f"Bearer {credentials.token}"}
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user info",
        )
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
    print("call back url is: ", flow.redirect_uri)
    codeexchange = secrets.token_urlsafe(32)
    await redis.set(f"oauth_code:{codeexchange}", str(oauth_account.id), ex=120)
    return RedirectResponse(f"{settings.FRONTEND_URL}/oauth/exchange?code={codeexchange}")


@router.post("/oauth/exchange")
async def echange(
    code: str,
    response: Response,
    request: Request,
    redis=Depends(get_redis),
):
    user_id = await redis.getdel(f"oauth_code:{code}")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user_id, expires_delta=access_token_expires
    )
    if redis:
        session_id, refresh_token = await session_manager.create_refresh_session(
            redis=redis,
            user_id=str(user_id),
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
        session_manager.set_refresh_token_cookie(response, refresh_token)

    return Token(access_token=access_token)
