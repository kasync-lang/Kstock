
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorClient
from beanie import init_beanie
from contextlib import asynccontextmanager

import os
from app.model.User import User, Oauth2Account
from app.core.config import settings


async def init_db():
        uri_db = settings.MONGO_URI
        if not uri_db:
                raise ValueError("MongoDB URI not found")
        client = AsyncIOMotorClient(uri_db)
        db = client["user_infor"]
        list_index = await db["user_infor"].index_information()
        if "email_1" in list_index:
                await db["user_infor"].drop_index("email_1")
        await db["user_infor"].create_index("email", unique=True)
        await init_beanie(database=db, document_models=[User, Oauth2Account])

