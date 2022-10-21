from loguru import logger
from typing import Union
from fastapi import APIRouter, Request, Cookie, Depends, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from dependency_injector.wiring import inject, Provide

###
from app import services
from app.containers import Application

router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory="app/templates")


@router.get("/logout")
@inject
async def logout(
    request: Request,
    session_id: Union[str, None] = Cookie(default=None),
    user_service: services.UserService = Depends(
        Provide[Application.service.user_service]
    ),
):
    if session_id:
        # Delete session id in cahce
        delete_result = await user_service.delete_user_in_cache(session_id=session_id)
        logger.debug(f"Delete session: {delete_result}")

    return RedirectResponse(url="/login", status_code=status.HTTP_301_MOVED_PERMANENTLY)


@router.get("/login")
@inject
async def login(
    request: Request,
    session_id: Union[str, None] = Cookie(default=None),
    user_service: services.UserService = Depends(
        Provide[Application.service.user_service]
    ),
):
    if session_id:
        cache_user = await user_service.get_user_in_cache(session_id=session_id)
        if cache_user:
            return RedirectResponse(
                url="/notify", status_code=status.HTTP_301_MOVED_PERMANENTLY
            )

    response = templates.TemplateResponse("login.html", {"request": request})
    return response


@router.get("/notify")
@inject
async def notify_page(
    request: Request,
    session_id: Union[str, None] = Cookie(default=None),
    user_service: services.UserService = Depends(
        Provide[Application.service.user_service]
    ),
):
    if session_id:
        cache_user = await user_service.get_user_in_cache(session_id=session_id)
        if cache_user:
            response = templates.TemplateResponse(
                "notify_index.html", {"request": request, "username": cache_user.name}
            )
            return response

    return RedirectResponse(url="/login", status_code=status.HTTP_301_MOVED_PERMANENTLY)
