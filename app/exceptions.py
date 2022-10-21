from typing import Any


class InternalException(Exception):
    error_code: int


class BaseInternalServiceException(InternalException):
    tier: str
    entity: str

    def __init__(self, message: Any) -> None:
        self.error_message = (
            f"[{self.error_code}]::{self.tier}::{self.entity}::{message}"
        )
        super().__init__(self.error_message)


###
#   Cache
###
class CacheServiceException(BaseInternalServiceException):
    tier: str = "cache"


class CacheServiceSaveException(CacheServiceException):
    error_code: int = 5000
    entity: str = "save"


###
#   DB
###
class DBServiceException(BaseInternalServiceException):
    tier: str = "db"


class DBServiceUpdateException(DBServiceException):
    error_code: int = 5100
    entity: str = "update"


###
#   Line
###
class LineServiceException(BaseInternalServiceException):
    tier: str = "line"


class LineSchemaValidationException(LineServiceException):
    error_code: int = 3300
    entity: str = "schema_validation"


class LineAuthJWTException(LineServiceException):
    error_code: int = 3000
    entity: str = "auth_jwt"


class LineAuthCallbackException(LineServiceException):
    error_code: int = 3001
    entity: str = "auth_callback"


class LineAPIUnexpectedStatusCodeException(LineServiceException):
    error_code: int = 3100
    entity: str = "status_code"
