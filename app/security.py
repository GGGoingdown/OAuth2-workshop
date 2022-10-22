from typing import Union
from fastapi import Depends, Cookie, HTTPException, status
from dependency_injector.wiring import inject, Provide

###
from app import services
from app.containers import Application
from app.schemas import UserSchema


@inject
async def get_cache_user(
    session_id: Union[str, None] = Cookie(default=None),
    user_service: services.UserService = Depends(
        Provide[Application.service.user_service]
    ),
) -> UserSchema.UserInCache:
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    user = await user_service.get_user_in_cache(session_id=session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Could not found credentials"
        )

    return user
