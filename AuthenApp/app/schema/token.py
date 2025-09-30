from pydantic import BaseModel
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = 'Bearer'

class TokenPayload(BaseModel):
    sub: str
    exp: datetime