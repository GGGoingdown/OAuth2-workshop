from pydantic import BaseModel, Field, HttpUrl
from typing import List


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


###
#   OAuth2
###


class BaseOAuthQueryString(BaseModel):
    response_type: str
    client_id: str
    redirect_uri: HttpUrl
    state: str
    scope: List[str]


class LineOAuthAccessTokenSchema(BaseModel):
    grant_type: str = Field(default="authorization_code")
    code: str
    client_id: str
    client_secret: str
    redirect_uri: HttpUrl

class LineOAuthAccessTokenResponse(BaseModel):
    access_token: str
    expires_in: str
    id_token: str
    refresh_token: str
    scope: str 
    token_type: str

class LineOAuthIDTokenSchema(BaseModel):
    iss: str
    user_id: str = Field(..., alias="sub")
    aud: str = Field(..., description="Channel ID [Client ID]")
    exp: int
    iat: int 
    name: str 
    picture: str
