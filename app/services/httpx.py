from typing import Callable, Tuple, Any, Dict
from loguru import logger
from aiohttp import ClientSession, ClientTimeout
from aiohttp_retry import RetryClient, ExponentialRetry
from dependency_injector import resources

RAISE_STATUS = {500, 501, 502, 503, 504, 505, 506, 507, 508}
CLIENT_TIMEOUT = 10
RETRY_ATTEMPTS = 3


class AsyncRequestClient(resources.AsyncResource):
    async def init(self) -> RetryClient:
        timeout = ClientTimeout(total=CLIENT_TIMEOUT)
        client_session = ClientSession(timeout=timeout)
        retry_options = ExponentialRetry(attempts=RETRY_ATTEMPTS, statuses=RAISE_STATUS)
        retry_client = RetryClient(
            raise_for_status=False,
            retry_options=retry_options,
            client_session=client_session,
        )
        logger.info("--- AsyncRequestClient init ---")
        return retry_client

    async def shutdown(self, client: RetryClient) -> None:
        await client.close()
        logger.info("--- AsyncRequestClient shutdown ---")


class AsyncRequestHandler:
    def __init__(self, request_client: RetryClient) -> None:
        self._request_client = request_client
        self._http_method: Dict = {
            "GET": self._request_client.get,
            "POST": self._request_client.post,
            "PATCH": self._request_client.patch,
        }

    async def _request(
        self, method: Callable, url: str, **kwargs: Any
    ) -> Tuple[int, Dict]:
        async with method(url, **kwargs) as response:
            status_code = response.status
            if status_code in RAISE_STATUS:
                return status_code, {"detail": "outside server crash"}
            rsp_json = await response.json()

        return status_code, rsp_json

    async def get(self, url: str, **kwargs: Any) -> Tuple[int, Dict]:
        return await self._request(self._http_method["GET"], url=url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Tuple[int, Dict]:
        return await self._request(self._http_method["POST"], url=url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Tuple[int, Dict]:
        return await self._request(self._http_method["PATCH"], url=url, **kwargs)
