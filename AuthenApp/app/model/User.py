from beanie import Document, Indexed, Replace, Insert, before_event
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Literal
from datetime import datetime, timezone



class User(Document):
    email: EmailStr = Field(unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_actived: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    role : Literal["basic_user", "admin"] = Field(default="basic_user")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    @before_event([Replace, Insert])
    def update_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)
    class Settings:
        name = "user_infor"
        validate_on_save = True

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com",
                "hashed_password": "$2b$12$...",
                "full_name": "John Doe",
                "is_active": True,
                "is_verified": False,
                "role": "basic_user",
            }
        }
class Oauth2Account(Document,BaseModel):
    provider: str
    email: EmailStr = Field(unique=True)
    provider_account_id: str
    name: str
    scope: Optional[list[str]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    role: Literal["basic_user", "admin"] = Field(default="basic_user")
    is_actived: bool = Field(default=True)
    class Settings:
        name = "oauth2_account"
        validate_on_save = True

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "google",
                "email": "john@example.com",
                "provider_account_id": "1234567890",
                "name": "John Doe",
                "scope": "openid email profile",
                "created_at": "2023-01-01T00:00:00Z",
                "role": "basic_user",
                "is_actived": True,
            }
        }