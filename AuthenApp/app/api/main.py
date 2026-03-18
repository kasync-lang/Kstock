from fastapi import APIRouter

from app.api import login
from app.api import testutil
from app.api import user
from app.api import jwk

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(login.router)
api_router.include_router(testutil.router)
api_router.include_router(user.router)
api_router.include_router(jwk.router)