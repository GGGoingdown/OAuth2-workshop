import urllib
from loguru import logger
from typing import Union

###
from app import utils
from app.config import LineLoginConfiguration, LineNotifyConfiguration
from app.schemas import LineSchema

class BaseLineOAuth2Manager:
    def __init__(
        self, config: Union[LineLoginConfiguration, LineNotifyConfiguration]
    ) -> None:
        self._config = config
        logger.info(config)
        self.auth_url = self._create_auth_url()
        self.access_token_url = self._config.access_token_url
        self.base_requests_headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def _create_auth_url(self) -> str:
        schema = LineSchema.BaseOAuthQueryString(
            response_type="code",
            client_id=self._config.client_id,
            redirect_uri=self._config.redirect_url,
            state=utils.get_shortuuid(),
            scope=self._config.scopes,
        ).dict(exclude={"scope"})
        query = urllib.parse.urlencode(schema)
        scope_query = urllib.parse.quote(" ".join(self._config.scopes))
        return f"{self._config.auth_url}?{query}&scope={scope_query}"

    def create_access_token_payload(
        self, code: str
    ) -> LineSchema.LineOAuthAccessTokenSchema:
        return AuthSchema.LineOAuthAccessTokenSchema(
            code=code,
            client_id=self._config.client_id,
            client_secret=self._config.client_secret,
            redirect_uri=self._config.redirect_url,
        )

