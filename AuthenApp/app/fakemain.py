from fastapi import FastAPI, Request, HTTPException,status
import logging
import os
import secrets

from app.core import crud

path = "client_secret.json"
from fastapi.responses import RedirectResponse
app = FastAPI()
from google_auth_oauthlib.flow import Flow
import requests
SCOPES = ['https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'openid']
app = FastAPI()
if os.path.exists(path):
    print("File exists")
else:
    print("File does not exist")
@app.get("/auth/google")
async def auth_google():
    flow = Flow.from_client_secrets_file(
        path,
        scopes=SCOPES,
        redirect_uri='http://localhost:8080/auth/google/callback',

    )
    flow.redirect_uri = 'http://localhost:8080/auth/google/callback'
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
@app.get("/auth/google/callback")
async def callback(request: Request):
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
        path,
        scopes=SCOPES,
        state=state,
        redirect_uri='http://localhost:8080/auth/google/callback',
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
    print("="*50)
    response = requests.get(url_get_userinfo, headers={"Authorization": f"Bearer {credentials.token}"})
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch user info")
    user_info = response.json()
    return user_info.get("email"), user_info.get("name")