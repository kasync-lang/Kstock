from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from starlette.responses import HTMLResponse
from fastapi import Request
from app.core.config import KeyStore
from dotenv import load_dotenv
from app.core.db import init_db
from app.core import mail
from fastapi.templating import Jinja2Templates
from app.api.main import api_router
from app.api.deps import register_exception_handlers
import redis.asyncio as redis


from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    KeyStore.load_key()
    load_dotenv(verbose=True)
    await init_db()

    app.state.redis = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
    )
    await mail.start()
    yield
    await mail.stop()
    await app.state.redis.aclose()

app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://192.168.2.100:5173",
        "https://kasyntech.com/"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory="app")


app.include_router(api_router)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})
