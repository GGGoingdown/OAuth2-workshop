#######
#   Application Metadata
#######
__VERSION__ = "0.0.1"
__TITLE__ = "OAuth2-Workshop"
__DESCRIPTION__ = "OAuth2.0 course homework"
__DOCS_URL__ = None
__ROOT_PATH__ = ""
################################################
import sys
import sentry_sdk
from loguru import logger
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Settings
from app import exceptions
from app.config import settings

# Sentry
def add_sentry_middleware(app: FastAPI, *, release_name: str) -> None:
    from app.middleware import CustomSentryAsgiMiddleware

    # Initial sentry and add middleware
    logger.info("--- Initial Sentry ---")
    sentry_sdk.init(
        settings.sentry.dns,
        traces_sample_rate=settings.sentry.trace_sample_rates,
        release=f"{release_name}@{__VERSION__}",
        environment=settings.app.env_mode.value,
    )
    app.add_middleware(CustomSentryAsgiMiddleware)


# Log request
def add_log_middleware(app: FastAPI) -> None:
    from app.middleware import LogRequestsMiddleware, IgnoredRoute

    app.add_middleware(
        LogRequestsMiddleware,
        ignored_routes=[
            IgnoredRoute(path="/health"),  # Health check endpoint
            IgnoredRoute(path="/openapi.json"),  # OpenAPI
        ],
    )


# Exceptions
def add_exceptions(app: FastAPI) -> None:
    from tortoise.exceptions import DoesNotExist, IntegrityError
    from aiohttp.client_exceptions import ClientError
    from asyncio.exceptions import TimeoutError


    @app.exception_handler(TimeoutError)
    async def asyncio_timeouterror_handler(request: Request, exc: TimeoutError):
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "timeout error"},
        )

    @app.exception_handler(ClientError)
    async def aiohttp_client_exception_handler(request: Request, exc: ClientError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
            headers={"X-Error": str(exc)},
        )

    @app.exception_handler(DoesNotExist)
    async def doesnotexist_exception_handler(request: Request, exc: DoesNotExist):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
        )

    @app.exception_handler(IntegrityError)
    async def integrityerror_exception_handler(request: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
            headers={"X-Error": "IntegrityError"},
        )

    @app.exception_handler(exceptions.BaseInternalServiceException)
    async def internalerror_exception_handler(
        request: Request, exc: exceptions.BaseInternalServiceException
    ):
        _error_message = str(exc.error_message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
            headers={"X-Error": _error_message},
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title=__TITLE__,
        description=__DESCRIPTION__,
        version=__VERSION__,
        docs_url=__DOCS_URL__,
        root_path=__ROOT_PATH__,
    )

    # Routers
    from app import routers

    app.include_router(routers.health_router)
    app.include_router(routers.authentication_router)
    app.include_router(routers.user_router)
    app.include_router(routers.view_router)
    app.include_router(routers.line_router)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Dependency injection
    from app import security
    from app.containers import Application

    container = Application()
    container.config.from_pydantic(settings)
    container.wire(
        modules=[sys.modules[__name__], security, routers.auth, routers.line]
    )

    app.container = container

    @app.on_event("startup")
    async def startup_event():
        logger.info("--- Startup Event ---")
        #! If resource with async function, change init_resources to await
        await app.container.service.init_resources()

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("--- Shutdown Event ---")
        #! If resource with async function, change init_resources to await
        await app.container.service.shutdown_resources()

    # Sentry middleware
    if settings.sentry.dns:
        add_sentry_middleware(app, release_name=settings.app.application_name)

    # Log request middleware
    # add_log_middleware(app)

    # Customize Exceptions
    add_exceptions(app)

    return app
