import urllib
import abc
from loguru import logger
from functools import lru_cache, cached_property
from typing import Dict, Iterable, TypeVar, Generic, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from fastapi.security import SecurityScopes
from pydantic import ValidationError

###
from app import utils, repositories, exceptions
from app.config import (
    BaseOAuth2Configuration,
    LineLoginConfiguration,
    LineNotifyConfiguration,
)
from app.schemas import AuthSchema, UserSchema, LineSchema


T = TypeVar("T")


class JWTHandler:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    __slots__ = (
        "_secret_key",
        "_algorithm",
        "_expired_time_minute",
    )

    def __init__(
        self,
        secret_key: str,
        algorithm: str,
        expired_time_minute: int = 120,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expired_time_minute = expired_time_minute

    def decode(self, token: str) -> Dict:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"verify_aud": False},
            )

            return payload

        except JWTError:
            raise self.credentials_exception

    def encode(self, payload: Dict) -> str:
        encoded_jwt = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return encoded_jwt

    def create_expired_time(self) -> datetime:
        expried_dt = utils.get_utc_now() + timedelta(minutes=self._expired_time_minute)
        return expried_dt


class AuthenticationSelector:
    def __init__(self, jwt: JWTHandler) -> None:
        self.jwt = jwt


##############################################################################
#           Authorization and Authentication
##############################################################################
class BaseAuthService:
    invalid_username_or_password_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    @classmethod
    def _verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        return cls.pwd_context.verify(plain_password, hashed_password)

    @classmethod
    def get_password_hash(cls, password: str) -> str:
        return cls.pwd_context.hash(password)


class AuthenticationService(BaseAuthService):
    __slots__ = ("_user_repo", "_token_selector", "_auth_cache")

    def __init__(
        self,
        user_repo: repositories.UserRepo,
        auth_selector: AuthenticationSelector,
    ) -> None:
        self._user_repo = user_repo
        self._auth_selector = auth_selector

    async def authenticate_user(self, email: str, password: str) -> UserSchema.UserInDB:
        if (user := await self._user_repo.filter_by_mail(email)) is None:
            logger.info("Invalid e-mail")
            raise self.invalid_username_or_password_exception

        if not self._verify_password(password, user.password_hash):
            logger.info("Invalid password")
            raise self.invalid_username_or_password_exception

        return UserSchema.UserInDB.from_orm(user)

    def authenticate_jwt(
        self, security_scopes: SecurityScopes, token: str
    ) -> AuthSchema.JWTUser:
        # Decode JWT
        payload = self._auth_selector.jwt.decode(token)
        # Get User ID
        if (user_id := payload.get("sub")) is None:
            raise self._auth_selector.jwt.credentials_exception

        # Get Roles
        user_scopes = payload.get("scopes", [])

        try:
            jwt_schema = AuthSchema.JWTTokenData(
                user_id=user_id, scopes=user_scopes
            ).dict()

        except ValueError as e:
            logger.debug(e)
            raise self._auth_selector.jwt.credentials_exception

        if security_scopes.scopes:
            authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
        else:
            authenticate_value = "Bearer"

        for scope in security_scopes.scopes:
            if scope not in user_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions",
                    headers={"WWW-Authenticate": authenticate_value},
                )

        return AuthSchema.JWTUser.construct(**jwt_schema)


class AuthorizationService(BaseAuthService):
    __slots__ = ("_auth_selector",)

    def __init__(
        self,
        auth_selector: AuthenticationSelector,
    ) -> None:
        self._auth_selector = auth_selector

    def create_jwt_token(self, *, user_id: int, scopes: Iterable[str] = []) -> str:
        payload = AuthSchema.JWTPayload(sub=user_id, scopes=scopes).dict()
        expried_dt = self._auth_selector.jwt.create_expired_time()
        payload.update({"exp": expried_dt})
        return self._auth_selector.jwt.encode(payload)


###
# OAuth2
###
class BaseOAuth2Manager(Generic[T], abc.ABC):
    def __init__(self, config: BaseOAuth2Configuration) -> None:
        self._config = config

    def _create_auth_url(self, state: Optional[str] = None) -> str:
        schema = AuthSchema.BaseOAuthQueryString(
            response_type="code",
            client_id=self._config.client_id,
            redirect_uri=self._config.redirect_url,
            state=state if state else utils.get_shortuuid(),
            scope=self._config.scopes,
        ).dict(exclude={"scope"})
        query = urllib.parse.urlencode(schema)
        scope_query = urllib.parse.quote(" ".join(self._config.scopes))
        return f"{self._config.auth_url}?{query}&scope={scope_query}"

    @abc.abstractmethod
    def auth_url(self, state: Optional[str] = None) -> str:
        ...

    @property
    @abc.abstractmethod
    def access_token_url(self) -> str:
        ...

    @abc.abstractmethod
    def create_access_token_schema(self, code: str) -> T:
        ...


class LineLoginOAuth2Manager(BaseOAuth2Manager):
    def __init__(self, config: Dict):
        super().__init__(config=LineLoginConfiguration(**config))

    @lru_cache(maxsize=64)
    def auth_url(self, state: Optional[str] = None) -> str:
        return super()._create_auth_url(state=state)

    @cached_property
    def access_token_url(self) -> str:
        return self._config.access_token_url

    def create_access_token_schema(
        self,
        code: str,
    ) -> LineSchema.LoginAccessTokenSchema:
        return LineSchema.LoginAccessTokenSchema(
            grant_type=LineSchema.GrantTypeEnum.authorization_code,
            code=code,
            client_id=self._config.client_id,
            client_secret=self._config.client_secret,
            redirect_uri=self._config.redirect_url,
        )

    def jwt_decode(self, token: str) -> LineSchema.IDTokenSchema:
        try:
            decoded = jwt.decode(
                token,
                key=self._config.client_secret,
                options={"verify_signature": False},
                audience=self._config.client_id,
            )
            return LineSchema.IDTokenSchema(**decoded)
        except JWTError as e:
            raise exceptions.LineAuthJWTException(message=e)

        except ValidationError as e:
            raise exceptions.LineSchemaValidationException(message=e)


class LineNotifyOAuth2Manager(BaseOAuth2Manager):
    def __init__(self, config: Dict):
        super().__init__(config=LineNotifyConfiguration(**config))

    @lru_cache(maxsize=64)
    def auth_url(self, state: str) -> str:
        return super()._create_auth_url(state=state)

    @cached_property
    def access_token_url(self) -> str:
        return self._config.access_token_url

    def create_access_token_schema(
        self, code: str
    ) -> LineSchema.NotifyAccessTokenSchema:
        return LineSchema.NotifyAccessTokenSchema(
            grant_type=LineSchema.GrantTypeEnum.authorization_code,
            client_id=self._config.client_id,
            client_secret=self._config.client_secret,
            code=code,
            redirect_uri=self._config.redirect_url,
        )
