from dependency_injector import containers, providers

# Application
from app import services, db, repositories
from app.config import Settings


class Gateway(containers.DeclarativeContainer):
    config = providers.Configuration()

    redis_client = providers.Resource(db.redis_init)

    db_resource = providers.Resource(db.DBResource, config=db.TORTOISE_ORM)


class Service(containers.DeclarativeContainer):
    config: Settings = providers.Configuration()
    gateway = providers.DependenciesContainer()
    # * Resource Initialize * #
    logger_init = providers.Resource(
        services.LoggerInitialize,
        application_name=config.app.application_name,
        log_level=config.app.log_level,
        env_mode=config.app.env_mode,
        log_path=config.app.log_path,
    )

    async_request_client = providers.Resource(services.AsyncRequestClient)

    async_request_handler = providers.Singleton(
        services.AsyncRequestHandler, request_client=async_request_client
    )

    # * Model Repositories *#
    user_repo = providers.Singleton(
        repositories.UserRepo,
    )

    line_login_repo = providers.Singleton(repositories.LineLoginRepo)

    line_notify_repo = providers.Singleton(repositories.LineNotifyRepo)

    line_notify_record_repo = providers.Singleton(repositories.LineNotifyRecordRepo)

    # * Auth Services *#
    jwt_handler = providers.Singleton(
        services.JWTHandler,
        secret_key=config.jwt.secret_key,
        algorithm=config.jwt.algorithm,
        expired_time_minute=config.jwt.expire_min,
    )

    authencation_seletor = providers.Singleton(
        services.AuthenticationSelector, jwt=jwt_handler
    )

    authentication_service = providers.Singleton(
        services.AuthenticationService,
        user_repo=user_repo,
        auth_selector=authencation_seletor,
    )

    authorization_service = providers.Singleton(
        services.AuthorizationService,
        auth_selector=authencation_seletor,
    )

    line_login_manager = providers.Singleton(
        services.LineLoginOAuth2Manager, config=config.line_login
    )
    line_notify_manager = providers.Singleton(
        services.LineNotifyOAuth2Manager, config=config.line_notify
    )

    # * User Service *#
    user_cache = providers.Singleton(
        services.UserCache, redis_client=gateway.redis_client
    )
    user_service = providers.Singleton(
        services.UserService, user_repo=user_repo, user_cache=user_cache
    )

    line_login_api_handler = providers.Singleton(
        services.LineLoginAPIHandler, request_handler=async_request_handler
    )

    line_notify_api_handler = providers.Singleton(
        services.LineNotifyAPIHandler, request_handler=async_request_handler
    )

    line_cache = providers.Singleton(
        services.LineCache, redis_client=gateway.redis_client
    )

    line_service = providers.Singleton(
        services.LineService,
        line_cache=line_cache,
        line_login_repo=line_login_repo,
        line_notify_repo=line_notify_repo,
        line_notify_record_repo=line_notify_record_repo,
    )


class Application(containers.DeclarativeContainer):
    config = providers.Configuration()
    gateway = providers.Container(Gateway, config=config)
    service: Service = providers.Container(Service, config=config, gateway=gateway)
