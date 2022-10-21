from loguru import logger
from typing import Union
from pydantic import ValidationError
from fastapi import Request, APIRouter, HTTPException, status, Query, Depends, Cookie
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from dependency_injector.wiring import inject, Provide
from tortoise.transactions import atomic

###
from app import services, exceptions, utils
from app.containers import Application
from app.schemas import UserSchema, AuthSchema, LineSchema, GenericSchema


router = APIRouter(tags=["Line"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/line-login/oauth2/authorize", response_class=RedirectResponse)
@inject
async def line_login_authorization_url(
    line_login_manager: services.LineLoginOAuth2Manager = Depends(
        Provide[Application.service.line_login_manager]
    ),
):
    """Line login authorization URL
    Reference:
        https://developers.line.biz/en/docs/line-login/integrate-line-login/#receiving-the-authorization-code-or-error-response-with-a-web-app

    Args:
        line_login_manager (services.LineLoginOAuth2Manager, optional): _description_. Defaults to Depends( Provide[Application.service.line_login_manager] ).

    Returns:
        _type_: str (URL)

    """
    url = line_login_manager.auth_url()
    response = RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    return response


@router.get("/line-login/oauth2/callback")
@inject
@atomic()
async def line_authorization_callback(
    request: Request,
    code: Union[str, None] = Query(default=None),
    state: Union[str, None] = Query(default=None),
    error: Union[str, None] = Query(default=None, description="Error code"),
    error_description: Union[str, None] = Query(
        default=None, description="A description of the error."
    ),
    line_login_manager: services.LineLoginOAuth2Manager = Depends(
        Provide[Application.service.line_login_manager]
    ),
    line_login_api: services.LineLoginAPIHandler = Depends(
        Provide[Application.service.line_login_api_handler]
    ),
    line_service: services.LineService = Depends(
        Provide[Application.service.line_service]
    ),
    user_service: services.UserService = Depends(
        Provide[Application.service.user_service]
    ),
):
    if error:
        logger.warning(f"Error code: {error} - Description: {error_description}")
        raise exceptions.LineAuthCallbackException(error_description)

    if not code:
        logger.error("Without code error")
        raise exceptions.LineAuthCallbackException("Line server error [without code]")

    logger.debug(f"Code: {code} - State: {state}")
    access_token_schema = line_login_manager.create_access_token_schema(code=code)

    access_token_rsp: LineSchema.LoginAccessTokenResponse = (
        await line_login_api.get_access_token(
            url=line_login_manager.access_token_url, payload=access_token_schema
        )
    )
    id_token_decoded: LineSchema.IDTokenSchema = line_login_manager.jwt_decode(
        access_token_rsp.id_token
    )

    login_model = await line_service.filter_login_with_prefetch(
        sub=id_token_decoded.sub
    )
    if login_model is None:
        # Create new user
        user_model = await user_service.create_user(name=id_token_decoded.name)
        login_model = await line_service.save_login(
            user_id=user_model.id,
            access_token_pyd=access_token_rsp,
            id_token_pyd=id_token_decoded,
        )
        user_id = user_model.id
    else:
        # Updat user
        user_id = login_model.user_id
        now = utils.get_utc_now()
        update_user_result = await user_service.update_user(
            id=user_id, update_schema={"last_login_at": now}
        )
        if not update_user_result:
            raise exceptions.DBServiceUpdateException(
                "Update user failure [DB]. Please try again"
            )

        update_login_result = await line_service.update_login(
            sub=login_model.sub,
            update_schema={
                **access_token_rsp.dict(
                    include={"access_token", "refresh_token", "expires_in"}
                ),
                **id_token_decoded.dict(include={"sub", "name", "picture"}),
            },
        )
        if not update_login_result:
            raise exceptions.DBServiceUpdateException(
                "Update line login failure [DB]. Please try again"
            )

    session_id = await user_service.save_user_in_cache(
        payload=UserSchema.UserInCache(
            id=user_id,
            name=id_token_decoded.name,
            login_token=access_token_rsp.access_token,
            login_type=AuthSchema.LoginTypeEnum.line,
        )
    )

    response = RedirectResponse(
        url="/notify", status_code=status.HTTP_301_MOVED_PERMANENTLY
    )
    response.set_cookie(key="session_id", value=session_id)
    return response


@router.get("/line-notify/oauth2/authorize", response_model=GenericSchema.URLResponse)
@inject
async def line_notify_authorization_url(
    session_id: Union[str, None] = Cookie(default=None),
    user_service: services.UserService = Depends(
        Provide[Application.service.user_service]
    ),
    line_notify_manager: services.LineNotifyOAuth2Manager = Depends(
        Provide[Application.service.line_notify_manager]
    ),
):
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    if not await user_service.get_user_in_cache(session_id=session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Could not found credentials"
        )

    url = line_notify_manager.auth_url(state=session_id)
    return {"url": url}


@router.get("/line-notify/state", response_model=GenericSchema.StatusResponse)
@inject
async def line_notify_state(
    session_id: Union[str, None] = Cookie(default=None),
    line_service: services.LineService = Depends(
        Provide[Application.service.line_service]
    ),
    user_service: services.UserService = Depends(
        Provide[Application.service.user_service]
    ),
):
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
    logger.info(f"User: {user}")

    if await line_service.get_notify_from_cache(user_id=user.id):
        return {"status": True}

    notify_model = await line_service.filter_notify(user_id=user.id)
    if notify_model and not notify_model.is_revoked:
        cache_result = await line_service.save_notify_to_cache(
            user_id=user.id, access_token=notify_model.access_token
        )
        if not cache_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache notify token failure. Please try again",
            )
        return {"status": True}

    return {"status": False}


@router.get("/line-notify/oauth2/callback")
@inject
@atomic()
async def line_notify_authorization_callback(
    code: Union[str, None] = Query(default=None),
    state: Union[str, None] = Query(default=None),
    error: Union[str, None] = Query(default=None, description="Error code"),
    error_description: Union[str, None] = Query(
        default=None, description="A description of the error."
    ),
    line_notify_manager: services.LineNotifyOAuth2Manager = Depends(
        Provide[Application.service.line_notify_manager]
    ),
    line_notify_api: services.LineNotifyAPIHandler = Depends(
        Provide[Application.service.line_notify_api_handler]
    ),
    line_service: services.LineService = Depends(
        Provide[Application.service.line_service]
    ),
    user_service: services.UserService = Depends(
        Provide[Application.service.user_service]
    ),
):
    if error:
        logger.warning(f"Error code: {error} - Description: {error_description}")
        raise exceptions.LineAuthCallbackException(error_description)

    if not code or not state:
        logger.error("Without code error")
        raise exceptions.LineAuthCallbackException("Line server error [without code]")

    user_in_cache = await user_service.get_user_in_cache(session_id=state)
    if not user_in_cache:
        raise exceptions.LineAuthCallbackException(
            "Invalid state [session_id]. Please try again"
        )

    access_token_schema = line_notify_manager.create_access_token_schema(code=code)

    access_token_rsp: LineSchema.NotifyAccessTokenResponse = (
        await line_notify_api.get_access_token(
            url=line_notify_manager.access_token_url, payload=access_token_schema
        )
    )

    notify_model = await line_service.filter_notify(user_id=user_in_cache.id)
    if notify_model:
        update_result = await line_service.update_notify(
            update_schema={
                "access_token": access_token_rsp.access_token,
                "is_revoked": False,
            },
            user_id=user_in_cache.id,
        )
        if not update_result:
            raise exceptions.DBServiceUpdateException(
                "Update notify failure [DB]. Please try again"
            )

    else:
        notify_model = await line_service.save_notify(
            user_id=user_in_cache.id, access_token_pyd=access_token_rsp
        )

    cache_result = await line_service.save_notify_to_cache(
        user_id=user_in_cache.id, access_token=notify_model.access_token
    )
    if not cache_result:
        raise exceptions.CacheServiceSaveException(
            "Cache notify failure. Please try again"
        )

    response = RedirectResponse(
        url="/notify", status_code=status.HTTP_301_MOVED_PERMANENTLY
    )
    return response


@router.delete("/line-notify/revoked", response_model=GenericSchema.DetailResponse)
@inject
@atomic()
async def line_notify_revoked():
    return {"detail": "success"}
