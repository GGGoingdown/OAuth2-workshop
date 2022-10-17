from loguru import logger
from fastapi import APIRouter, HTTPException, status, Query, Depends
from dependency_injector.wiring import inject, Provide

router = APIRouter(prefix="/line", tags=["Line"])

@router.get("/oauth2/callback")
@inject
async def line_authorization_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    logger.info(f'code: {code} - state: {state}')
