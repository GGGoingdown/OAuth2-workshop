import aioredis
import json
from typing import Optional, Any, Dict
from datetime import datetime
from fastapi.encoders import jsonable_encoder

###
from app import utils, exceptions
from app.models import User
from app.repositories import UserRepo
from app.schemas import UserSchema


class UserCache:
    def __init__(self, redis_client: aioredis) -> None:
        self._redis_client = redis_client

    def _create_user_key(self, session_id: str) -> str:
        return f"user:{session_id}"

    async def save_user(
        self, session_id: str, payload: str, expired_sec: int = 86400
    ) -> bool:
        key = self._create_user_key(session_id=session_id)
        return await self._redis_client.setex(key, expired_sec, payload)

    async def get_user(self, session_id: str) -> Optional[str]:
        key = self._create_user_key(session_id=session_id)
        return await self._redis_client.get(key)

    async def delete_user(self, session_id: str) -> int:
        key = self._create_user_key(session_id=session_id)
        return await self._redis_client.delete(key)


class UserService:
    def __init__(self, user_repo: UserRepo, user_cache: UserCache) -> None:
        self._user_repo = user_repo
        self._user_cache = user_cache

    async def create_user(
        self,
        *,
        name: str,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        last_login_at: Optional[datetime] = None,
    ) -> User:
        return await self._user_repo.create(
            name=name,
            email=email,
            password_hash=password_hash,
            create_at=utils.get_utc_now(),
            last_login_at=last_login_at,
        )

    async def get_user_by_email(self, email: str) -> User:
        return await self._user_repo.get(email=email)

    async def update_user(self, update_schema: Dict, **filter: Any) -> int:
        return await self._user_repo.update_with_select(
            update_schema=update_schema, **filter
        )

    async def save_user_in_cache(self, payload: UserSchema.UserInCache) -> str:
        session_id = utils.get_shortuuid()
        save_result = await self._user_cache.save_user(
            session_id=session_id,
            payload=json.dumps(jsonable_encoder(payload, exclude_none=True)),
        )
        if not save_result:
            raise exceptions.CacheServiceSaveException(
                message="Save user failure. Please try again"
            )
        return session_id

    async def get_user_in_cache(
        self, session_id: str
    ) -> Optional[UserSchema.UserInCache]:
        user = await self._user_cache.get_user(session_id=session_id)
        if user is None:
            return None
        return UserSchema.UserInCache.parse_raw(user)

    async def delete_user_in_cache(self, session_id: str) -> int:
        return await self._user_cache.delete_user(session_id=session_id)
