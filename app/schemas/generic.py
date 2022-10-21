from enum import Enum
from pydantic import BaseModel


class LogLevel(str, Enum):
    TRACE = "TRACE"
    DEUBG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Environment Mode
class EnvironmentMode(str, Enum):
    DEV = "DEV"
    TEST = "TEST"
    STAG = "STAG"
    PROD = "PROD"


class DetailResponse(BaseModel):
    detail: str


class URLResponse(BaseModel):
    url: str


class AccessTokenResponse(BaseModel):
    access_token: str


class StatusResponse(BaseModel):
    status: bool
