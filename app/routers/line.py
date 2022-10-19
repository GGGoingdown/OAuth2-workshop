from loguru import logger
from typing import Union
from pydantic import ValidationError
from fastapi import APIRouter, HTTPException, status, Query, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from dependency_injector.wiring import inject, Provide

###
from app import services
from app.containers import Application
from app.schemas import AuthSchema


router = APIRouter(tags=["Line"])


@router.get("/line-login/oauth2/authorize", response_class=RedirectResponse)
@inject
async def line_authorization_url(
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
    return line_login_manager.auth_url


@router.get("/line-login/oauth2/callback")
@inject
async def line_authorization_callback(
    code: Union[str, None] = Query(default=None),
    state: Union[str, None] = Query(default=None),
    error: Union[str, None] = Query(default=None, description="Error code"),
    error_description: Union[str, None] = Query(
        default=None, description="A description of the error."
    ),
    line_login_manager: services.LineLoginOAuth2Manager = Depends(
        Provide[Application.service.line_login_manager]
    ),
    async_request_handler: services.AsyncRequestHandler = Depends(
        Provide[Application.service.async_request_handler]
    ),
):
    if error:
        logger.debug(f"Error code: {error} - Description: {error_description}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_description
        )

    if not code:
        logger.error("Without code error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Line server error",
        )

    logger.debug(f"Code: {code} - State: {state}")
    payload = jsonable_encoder(
        line_login_manager.create_access_token_payload(code=code)
    )
    # Get access token
    status_code, rsp_json = await async_request_handler.post(
        url=line_login_manager.access_token_url,
        data=payload,
        headers=line_login_manager.access_token_headers,
    )
    if status_code != 200:
        logger.error(
            f"Get access token failure. Status code: {status_code} - Response: {rsp_json}"
        )
        raise HTTPException(status_code=status_code, detail=rsp_json)

    try:
        rsp_payload = AuthSchema.LineOAuthAccessTokenResponse(**rsp_json)

        user_info: AuthSchema.LineOAuthIDTokenSchema = line_login_manager.jwt_decode(
            rsp_payload.id_token
        )

        response = RedirectResponse(url="/notify")
        return response

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


@router.get("/line-notify/oauth2/callback")
@inject
async def line_notify_authorization_callback():
    ...
