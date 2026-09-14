from fastapi import FastAPI
from starlette.responses import HTMLResponse
from fastapi import Request
from app.core.config import KeyStore
from dotenv import load_dotenv
from app.core.db import init_db
from fastapi.templating import Jinja2Templates
from app.api.main import api_router


from fastapi.middleware.cors import CORSMiddleware



# @asynccontextmanager
async def lifespan(app: FastAPI):
    KeyStore.load_key()
    load_dotenv(verbose=True)
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://192.168.2.100:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory="app")


app.include_router(api_router)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html",{"request": request} )








