from pydantic import BaseModel, HttpUrl, Field, EmailStr, validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

###
from app.schemas.auth import BaseOAuthQueryString


class GrantTypeEnum(str, Enum):
    authorization_code = "authorization_code"
    refresh_token = "refresh_token"


class OAuth2QueryString(BaseOAuthQueryString):
    ...


class BaseClientSchema(BaseModel):
    client_id: str
    client_secret: str


class BaseGrantTypeSchema(BaseModel):
    grant_type: GrantTypeEnum


class LoginAccessTokenSchema(BaseGrantTypeSchema, BaseClientSchema):
    grant_type: GrantTypeEnum = Field(default=GrantTypeEnum.authorization_code)
    code: str
    redirect_uri: HttpUrl
    code_verifier: Optional[str]


class NotifyAccessTokenSchema(BaseGrantTypeSchema, BaseClientSchema):
    grant_type: GrantTypeEnum = Field(default=GrantTypeEnum.authorization_code)
    code: str
    redirect_uri: HttpUrl


class NotifyAccessTokenResponse(BaseModel):
    access_token: str = Field(
        ...,
        description="An access token for authentication. Used for calling the notification API to be mentioned below. This access token has no expiration date",
    )


class BaseTokenResponse(BaseModel):
    access_token: str = Field(..., description="Access token. Valid for 30 days")
    expires_in: datetime = Field(
        ..., description="Number of seconds until the access token expires"
    )
    refresh_token: str = Field(
        ...,
        description="Token used to get a new access token (refresh token). Valid for 90 days after the access token is issued",
    )
    scope: str = Field(..., description="Permissions granted to the access token")
    token_type: str = Field(default="Bearer")

    @validator("expires_in", pre=True)
    def seconds_to_datetime(cls, v) -> datetime:
        # seconds to datetime
        return datetime.fromtimestamp(v)


class LoginAccessTokenResponse(BaseTokenResponse):
    id_token: str = Field(..., description="JWT with information about the user")


class IDTokenSchema(BaseModel):
    iss: str = Field(..., description="URL where the ID token is generated")
    sub: str = Field(..., description="User ID for which the ID token is generated")
    aud: str = Field(..., description="Channel ID [Client ID]")
    exp: int = Field(..., description="The expiry date of the ID token in UNIX time")
    iat: int = Field(
        ..., description="Time when the ID token was generated in UNIX time"
    )
    nonce: Optional[str] = Field(
        None,
        description="The nonce value specified in the authorization URL. Not included if the nonce value was not specified in the authorization request.",
    )
    amr: List[str] = Field(
        ..., description="List of authentication methods used by the user"
    )
    name: str = Field(..., description="User's display name")
    picture: str = Field(..., description="User's profile image URL")
    email: Optional[EmailStr] = Field(
        None,
        description="User's email address. Not included if the email scope was not specified in the authorization request.",
    )

    class Config:
        schema_extra = {
            "example": {
                "iss": "https://access.line.me",
                "sub": "U1234567890abcdef1234567890abcdef",
                "aud": "1234567890",
                "exp": 1504169092,
                "iat": 1504263657,
                "nonce": "0987654asdf",
                "amr": ["pwd"],
                "name": "Taro Line",
                "picture": "https://sample_line.me/aBcdefg123456",
            }
        }


class LoginVerifyTokenResponse(BaseModel):
    scope: str
    client_id: str
    expires_in: int


class LoginVerifyTokenErrerResponse(BaseModel):
    error: str
    error_description: str


class LoginRefreshTokenSchema(BaseGrantTypeSchema, BaseClientSchema):
    grant_type: GrantTypeEnum = Field(default=GrantTypeEnum.refresh_token)
    refresh_token: str = Field(
        ...,
        description="If the refresh token expires, you must prompt the user to log in again to generate a new access token",
    )


class LoginRefreshTokenResponse(BaseTokenResponse):
    ...


class NotifySchema(BaseModel):
    message: str
    imageThumbnail: Optional[HttpUrl] = Field(
        None, description="Maximum size of 240×240px JPEG", alias="image_thumb_nail"
    )
    image_full_size: Optional[HttpUrl] = Field(
        None, description="Maximum size of 2048×2048px JPEG", alias="image_full_size"
    )


class NotifyRecordInCache(BaseModel):
    create_at: datetime
    name: str
    message: str


class NotifyResponse(BaseModel):
    status: int = Field(
        ..., description="200: Success;400: Bad request;401: Invalid access token"
    )
    message: str


class NotifyVerifyTokenResponse(BaseModel):
    status: int = Field(
        ...,
        description="200: Success・Access token valid;401: Invalid access token;Other: Processed over time or stopped",
    )


class NotifyRevokeResponse(BaseModel):
    status: int = Field(
        ...,
        description="200: Success・Access token valid;401: Invalid access token;Other: Processed over time or stopped",
    )
