from pydantic import BaseModel, Field, HttpUrl
from typing import List
from enum import Enum

class JWTPayload(BaseModel):
    sub: str
    scopes: List[str]


class JWTTokenData(BaseModel):
    user_id: int
    scopes: List[str] = Field(..., description="User Policy")


class JWTUser(JWTTokenData):
    ...


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")


class LoginTypeEnum(str, Enum):
    normal = "normal"
    line = "line"  # See schemas/line.py
    github = "github"
    google = "google"
    instagram = "instagram"


class BaseOAuthQueryString(BaseModel):
    response_type: str
    client_id: str
    redirect_uri: HttpUrl
    state: str
    scope: List[str]


