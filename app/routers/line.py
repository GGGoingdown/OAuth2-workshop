from loguru import logger
from typing import Union, List
from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Query,
    Depends,
    Cookie,
    Body,
)
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from dependency_injector.wiring import inject, Provide
from tortoise.transactions import atomic

###
from app import services, exceptions, utils, security
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


@router.get("/line-login/oauth2/callback", response_class=RedirectResponse)
@inject
@atomic()
async def line_authorization_callback(
    code: Union[str, None] = Query(
        default=None, description="Authorization code used to get an access token"
    ),
    state: Union[str, None] = Query(
        default=None,
        description="A unique alphanumeric string used to prevent cross-site request forgery",
    ),
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
    """Receiving the authorization code or error response
    Doc: https://developers.line.biz/en/docs/line-login/integrate-line-login/#receiving-the-authorization-code-or-error-response-with-a-web-app
    Raises:
        exceptions.LineAuthCallbackException: raise when receive error response
        exceptions.DBServiceUpdateException: raise when update db error
        exceptions.CacheServiceSaveException: raise when save cache error

    Returns:
        _type_: Redirect to '/notify'
    """
    if error:
        logger.warning(f"Error code: {error} - Description: {error_description}")
        raise exceptions.LineAuthCallbackException(error_description)

    if not code:
        logger.error("Without code error")
        raise exceptions.LineAuthCallbackException("Line server error [without code]")

    logger.debug(f"Code: {code} - State: {state}")
    access_token_schema = line_login_manager.create_access_token_schema(code=code)
    # Get access token
    access_token_rsp: LineSchema.LoginAccessTokenResponse = (
        await line_login_api.get_access_token(
            url=line_login_manager.access_token_url, payload=access_token_schema
        )
    )
    # Decoded JWT
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
    # Save current user in cache. it will raise exception when save user failure.
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


@router.get("/line-notify/oauth2/callback", response_class=RedirectResponse)
@inject
@atomic()
async def line_notify_authorization_callback(
    code: Union[str, None] = Query(
        default=None, description="A code for acquiring access tokens"
    ),
    state: Union[str, None] = Query(
        default=None,
        description="Directly sends the assigned state parameter. In this case we use to save 'session_id'",
    ),
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
    """Receiving the authorization code or error response
    Docs: https://notify-bot.line.me/doc/en/
    Raises:
        exceptions.LineAuthCallbackException: raise when receive error response
        exceptions.DBServiceUpdateException: raise when update db error
        exceptions.CacheServiceSaveException: raise when save cache error

    Returns:
        _type_: Redirect to '/notify'
    """
    if error:
        logger.warning(f"Error code: {error} - Description: {error_description}")
        raise exceptions.LineAuthCallbackException(error_description)

    if not code or not state:
        logger.error("Without code error")
        raise exceptions.LineAuthCallbackException("Line server error [without code]")

    # Get user using state (session_id)
    user_in_cache = await user_service.get_user_in_cache(session_id=state)
    if not user_in_cache:
        raise exceptions.LineAuthCallbackException(
            "Invalid state [session_id]. Please try again"
        )

    access_token_schema = line_notify_manager.create_access_token_schema(code=code)
    # Get access token
    access_token_rsp: LineSchema.NotifyAccessTokenResponse = (
        await line_notify_api.get_access_token(
            url=line_notify_manager.access_token_url, payload=access_token_schema
        )
    )

    notify_model = await line_service.filter_notify(user_id=user_in_cache.id)
    if notify_model:
        # Update old one
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
        # Crate new one
        notify_model = await line_service.save_notify(
            user_id=user_in_cache.id, access_token_pyd=access_token_rsp
        )

    # Save access token in cache
    cache_result = await line_service.save_notify_to_cache(
        user_id=user_in_cache.id, access_token=access_token_rsp.access_token
    )
    if not cache_result:
        raise exceptions.CacheServiceSaveException(
            "Cache notify failure. Please try again"
        )

    response = RedirectResponse(
        url="/notify", status_code=status.HTTP_301_MOVED_PERMANENTLY
    )
    return response


@router.get(
    "/line-notify/oauth2/authorize",
    response_model=GenericSchema.URLResponse,
    responses={
        401: {
            "model": GenericSchema.DetailResponse,
            "description": "Could not validate credentials",
        },
        404: {
            "model": GenericSchema.DetailResponse,
            "description": "Could not found credentials",
        },
    },
)
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
    """Line notify authorization URL
    Doc: https://notify-bot.line.me/doc/en/
    Args:
        session_id (Union[str, None], optional): save session_id to state. Defaults to Cookie(default=None).
    Raises:
        HTTPException[401]: Could not validate credentials [No session_id]
        HTTPException[404]: Could not found credentials [Not found in cache]

    Returns:
        _type_: authorization URL
    """
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


@router.get(
    "/line-notify/status",
    response_model=GenericSchema.StatusResponse,
)
@inject
async def line_notify_status(
    user_in_cache: UserSchema.UserInCache = Depends(security.get_cache_user),
    line_service: services.LineService = Depends(
        Provide[Application.service.line_service]
    ),
):
    """Check notify status
    Description: True: Enable. False: Disable
    Returns:
        _type_: status
    """
    # If get from cache.
    if await line_service.get_notify_from_cache(user_id=user_in_cache.id):
        return {"status": True}
    # If did not get from cache. check db exist or not
    notify_model = await line_service.filter_notify(user_id=user_in_cache.id)
    if notify_model and not notify_model.is_revoked:
        # cache it !!
        cache_result = await line_service.save_notify_to_cache(
            user_id=user_in_cache.id, access_token=notify_model.access_token
        )
        logger.debug(f"Cache notify: {cache_result}")
        return {"status": True}

    return {"status": False}


@router.delete(
    "/line-notify/revoked",
    response_model=GenericSchema.DetailResponse,
    responses={
        404: {
            "model": GenericSchema.DetailResponse,
            "description": "Not found access token",
        },
        401: {
            "model": GenericSchema.DetailResponse,
            "description": "Error message from LINE API",
        },
        500: {
            "model": GenericSchema.DetailResponse,
            "description": "Update db failure. Please try again",
        },
    },
)
@inject
@atomic()
async def line_notify_revoked(
    user_in_cache: UserSchema.UserInCache = Depends(security.get_cache_user),
    line_notify_api: services.LineNotifyAPIHandler = Depends(
        Provide[Application.service.line_notify_api_handler]
    ),
    line_service: services.LineService = Depends(
        Provide[Application.service.line_service]
    ),
):
    """Revoke  user access token
    Raises:
        HTTPException[404]: Not found access token
        HTTPException[401 or others]: From line revoke api
        HTTPException[500]: Update db error

    Returns:
        _type_: save success or not
    """
    notify_in_cache = await line_service.get_notify_from_cache(user_id=user_in_cache.id)
    if notify_in_cache:  # If cache exists.
        access_token = notify_in_cache.access_token
    else:  # If cache did not exists.
        notify_model = await line_service.filter_notify(user_id=user_in_cache.id)
        if not notify_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found access token"
            )
        access_token = notify_model.access_token

    # DB update
    update_db_result = await line_service.update_notify(
        user_id=user_in_cache.id, update_schema={"is_revoked": True}
    )
    if not update_db_result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Update db failure. Please try again",
        )
    # Call Line revoke api
    status_code, rsp_json = await line_notify_api.revoke(access_token=access_token)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=rsp_json)
    # Delet notify in cache

    delete_cache_result = await line_service.delete_notify_from_cache(
        user_id=user_in_cache.id
    )
    logger.debug(f"Delete notify in cache: {delete_cache_result}")

    return {"detail": "success"}


@router.post(
    "/line-notify/message",
    response_model=LineSchema.NotifyRecordInCache,
    responses={
        404: {
            "model": GenericSchema.DetailResponse,
            "description": "Not found access token",
        },
        401: {
            "model": GenericSchema.DetailResponse,
            "description": "Error message from LINE API",
        },
        500: {
            "model": GenericSchema.DetailResponse,
            "description": "Update db failure. Please try again",
        },
    },
)
@inject
async def sned_line_notify_message(
    user_in_cache: UserSchema.UserInCache = Depends(security.get_cache_user),
    payload: LineSchema.NotifySchema = Body(...),
    line_notify_api: services.LineNotifyAPIHandler = Depends(
        Provide[Application.service.line_notify_api_handler]
    ),
    line_service: services.LineService = Depends(
        Provide[Application.service.line_service]
    ),
):
    """Send LINE notify message
    Raises:
        HTTPException[404]: Not found access token
        HTTPException[Any]: Error message from LINE API.

    Returns:
        _type_: send success or not
    """
    notify_in_cache = await line_service.get_notify_from_cache(user_id=user_in_cache.id)
    if notify_in_cache:
        access_token = notify_in_cache.access_token
    else:
        notify_model = await line_service.filter_notify(user_id=user_in_cache.id)
        if not notify_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found access token"
            )
        access_token = notify_model.access_token
        await line_service.save_notify_to_cache(
            user_id=user_in_cache.id, access_token=access_token
        )

    status_code, rsp_json = await line_notify_api.notify(
        access_token=access_token, payload=payload
    )
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=rsp_json)

    notify_record_model = await line_service.save_notify_record(
        user_id=user_in_cache.id, payload=payload
    )

    cache_payload = LineSchema.NotifyRecordInCache(
        name=user_in_cache.name,
        create_at=notify_record_model.create_at,
        message=payload.message,
    )
    await line_service.save_notify_record_to_cache(cache_payload)

    return cache_payload


@router.get(
    "/line-notify/message",
    response_model=List[LineSchema.NotifyRecordInCache],
    responses={
        401: {
            "model": GenericSchema.DetailResponse,
            "description": "Could not validate credentials",
        },
    },
    dependencies=[Depends(security.get_cache_user)],
)
@inject
async def get_line_notify_records(
    line_service: services.LineService = Depends(
        Provide[Application.service.line_service]
    ),
):
    """Get notify records
    Returns:
        _type_: records. include create_at, name, and message
    """
    # Get from cache
    records = await line_service.get_notify_record_from_cache()
    if not len(records):
        # Get from db
        record_models = await line_service.get_notify_records()
        cache_payload = [
            LineSchema.NotifyRecordInCache(
                name=record_model.user.name,
                create_at=record_model.create_at,
                message=record_model.message,
            )
            for record_model in record_models
        ]
        if cache_payload:
            # cache it !!
            await line_service.save_notify_record_to_cache(*cache_payload)
            return cache_payload

    return [LineSchema.NotifyRecordInCache.parse_raw(record) for record in records]
