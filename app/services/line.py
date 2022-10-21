import urllib
import json
import aioredis
from loguru import logger
from typing import Union, Dict, Optional, Any
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder

###
from app import utils, exceptions, repositories, models
from app.schemas import LineSchema, GenericSchema
from app.services.httpx import AsyncRequestHandler

###
# API Handler
###


class BaseLineAPIHandler:
    base_headers = {"Content-Type": "application/x-www-form-urlencoded"}


class LineLoginAPIHandler(BaseLineAPIHandler):
    def __init__(self, request_handler: AsyncRequestHandler):
        self._request_handler = request_handler

    async def get_access_token(
        self,
        url: str,
        payload: LineSchema.LoginAccessTokenSchema,
    ) -> LineSchema.LoginAccessTokenResponse:
        """
        https://developers.line.biz/en/reference/line-login/#issue-access-token

        :param url: "https://api.line.me/oauth2/v2.1/token"
        :type url: str
        :param payload: request body
        :type payload: LineSchema.LoginAccessTokenSchema
        :return: access token
        :rtype: LineSchema.LoginAccessTokenResponse
        """

        status_code, rsp_json = await self._request_handler.post(
            url=url, data=jsonable_encoder(payload), headers=self.base_headers
        )
        if status_code != 200:
            raise exceptions.LineAPIUnexpectedStatusCodeException(message=rsp_json)
        try:
            return LineSchema.LoginAccessTokenResponse(**rsp_json)
        except ValidationError as e:
            raise exceptions.LineSchemaValidationException(message=e)


class LineNotifyAPIHandler(BaseLineAPIHandler):
    def __init__(self, request_handler: AsyncRequestHandler) -> None:
        self._request_handler = request_handler

    async def get_access_token(
        self, url: str, payload: LineSchema.NotifyAccessTokenSchema
    ) -> LineSchema.NotifyAccessTokenResponse:
        status_code, rsp_json = await self._request_handler.post(
            url=url, data=jsonable_encoder(payload), headers=self.base_headers
        )
        if status_code != 200:
            raise exceptions.LineAPIUnexpectedStatusCodeException(message=rsp_json)
        try:
            return LineSchema.NotifyAccessTokenResponse(**rsp_json)
        except ValidationError as e:
            raise exceptions.LineSchemaValidationException(message=e)


###
# Service
###
class LineCache:
    def __init__(self, redis_client: aioredis) -> None:
        self._redis_client = redis_client

    def _create_notify_key(self, user_id: int) -> str:
        return f"notify:user:{user_id}"

    def _create_notify_records(self, user_id: int) -> str:
        return f"notify-records:user:{user_id}"

    async def save_notify(self, user_id: int, payload: str) -> bool:
        key = self._create_notify_key(user_id=user_id)
        return await self._redis_client.set(key, payload)

    async def get_notify(self, user_id: int) -> Optional[str]:
        key = self._create_notify_key(user_id=user_id)
        return await self._redis_client.get(key)

    async def delete_notify(self, user_id: int) -> int:
        key = self._create_notify_key(user_id=user_id)
        return await self._redis_client.delete(key)


class LineService:
    def __init__(
        self,
        line_cache: LineCache,
        line_login_repo: repositories.LineLoginRepo,
        line_notify_repo: repositories.LineNotifyRepo,
        line_notify_record_repo: repositories.LineNotifyRecordRepo,
    ) -> None:
        self._line_cache = line_cache
        self._line_login_repo = line_login_repo
        self._line_notify_repo = line_notify_repo
        self._line_notify_record_repo = line_notify_record_repo

    async def save_login(
        self,
        user_id: int,
        *,
        access_token_pyd: LineSchema.LoginAccessTokenResponse,
        id_token_pyd: LineSchema.IDTokenSchema,
    ) -> models.LineLogin:
        db_schema: Dict[str, Any] = {
            "user_id": user_id,
            **access_token_pyd.dict(
                include={"access_token", "refresh_token", "expires_in"}
            ),
            **id_token_pyd.dict(include={"sub", "name", "picture"}),
        }
        if id_token_pyd.email:
            db_schema["email"] = id_token_pyd.email

        return await self._line_login_repo.create(**db_schema)

    async def save_notify(
        self, user_id: int, *, access_token_pyd: LineSchema.NotifyAccessTokenResponse
    ) -> models.LineNotify:
        now = utils.get_utc_now()
        return await self._line_notify_repo.create(
            create_at=now,
            access_token=access_token_pyd.access_token,
            is_revoked=False,
            user_id=user_id,
        )

    async def save_notify_record(
        self, user_id: int, *, payload: LineSchema.NotifySchema
    ) -> models.LineNotifyRecord:
        now = utils.get_utc_now()
        payload_without_none = payload.dict(exclude_none=True, exclude_unset=True)
        return await self._line_notify_record_repo.create(
            create_at=now, user_id=user_id, **payload_without_none
        )

    async def update_login(self, update_schema: Dict, **filter: Any) -> int:
        update_at = utils.get_utc_now()
        update = {"update_at": update_at, **update_schema}
        return await self._line_login_repo.update_with_select(
            update_schema=update, **filter
        )

    async def update_notify(self, update_schema: Dict, **filter: Any) -> int:
        update_at = utils.get_utc_now()
        update = {"update_at": update_at, **update_schema}
        return await self._line_notify_repo.update_with_select(
            update_schema=update, **filter
        )

    async def filter_login_with_prefetch(self, sub: str) -> Optional[models.LineLogin]:
        return await self._line_login_repo.filter_with_prefetch(sub=sub)

    async def filter_notify(self, user_id: int) -> Optional[models.LineNotify]:
        return await self._line_notify_repo.filter(user_id=user_id)

    async def get_notify_from_cache(
        self, user_id: int
    ) -> Optional[GenericSchema.AccessTokenResponse]:
        payload = await self._line_cache.get_notify(user_id=user_id)
        return GenericSchema.AccessTokenResponse.parse_raw(payload) if payload else None

    async def delete_notify_from_cache(self, user_id: int) -> int:
        return await self._line_cache.delete_notify(user_id=user_id)

    async def save_notify_to_cache(self, user_id: int, access_token: str) -> bool:
        payload = json.dumps(
            GenericSchema.AccessTokenResponse(access_token=access_token)
        )
        return await self._line_cache.save_notify(user_id=user_id, payload=payload)
