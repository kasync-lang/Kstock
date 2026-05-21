from fastapi import FastAPI
from starlette.responses import HTMLResponse
from fastapi import Request
from app.core.config import KeyStore
from dotenv import load_dotenv
from app.core.db import init_db
from fastapi.templating import Jinja2Templates
from app.api.main import api_router


# @asynccontextmanager
async def lifespan(app: FastAPI):
    KeyStore.load_key()
    load_dotenv(verbose=True)
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="app")


app.include_router(api_router)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html",{"request": request} )








