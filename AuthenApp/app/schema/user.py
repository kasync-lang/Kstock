from pydantic import BaseModel,EmailStr, Field
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr = Field(max_length=155)
    is_actived: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    full_name: Optional[str] | None = Field(default=None, max_length=155)
    model_config = {
        "extra": "ignore"
    }

class UserCreate(UserBase):
    password: str = Field(min_length=4, max_length=128)

class UserRegister(BaseModel):
    email: EmailStr = Field(max_length=155)
    password: str = Field(min_length=4, max_length=128)
    full_name: str = Field(max_length=155)

class UserUpdateMe(BaseModel):
    email: EmailStr = Field(max_length=155)
    full_name: str = Field(max_length=155)

#update user for admin
class UserUpdate(UserBase):
    email: EmailStr = Field(max_length=155, default=None)
    password: str = Field(min_length=4, max_length=128, default=None)
class UpdatePassword(BaseModel):
    current_password: str = Field(min_length=4, max_length=128)
    new_password: str = Field(min_length=4, max_length=128)

class UserPublic(UserBase):
    id: Optional[str] = Field(default=None)


class UsersPublic(BaseModel):
    data: list[UserPublic]
class NewPassword(BaseModel):
    token: str
    new_password: str = Field(min_length=4, max_length=128)

class Message(BaseModel):
    message: str

