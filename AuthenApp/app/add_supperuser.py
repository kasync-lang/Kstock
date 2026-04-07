import asyncio
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorClient
from beanie import init_beanie
import os
from bson import ObjectId
from dotenv import load_dotenv
from app.core.security import get_password_hash
from app.model.User import User
from app.core.db import init_db
from app.core.config import settings

async def seed():
    load_dotenv(verbose=True)
    await init_db()
    if not await User.find_one(User.email == settings.FIRST_SUPERUSER_EMAIL):
        await User(
            email=settings.FIRST_SUPERUSER_EMAIL,
            hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
            is_actived=True,
            is_verified=True,
            role = "admin",
        ).insert()

async def seed2():
    load_dotenv(verbose=True)
    await init_db()
    user_test = await User.find_one(User.id == ObjectId("68c174d38f980502a4016963"))
    print(user_test)
if __name__ == "__main__":
    asyncio.run(seed())