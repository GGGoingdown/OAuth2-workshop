from typing import Tuple, Any, Dict
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

    async def get(self, url: str, **kwargs: Any) -> Tuple[int, Dict]:
        async with self._request_client.get(url, **kwargs) as response:
            status_code = response.status
            if status_code in RAISE_STATUS:
                return status_code, {"detail": "outside server crash"}
            rsp_text = await response.json()

        return status_code, rsp_text

    async def post(self, url: str, **kwargs: Any) -> Tuple[int, Dict]:
        async with self._request_client.post(url, **kwargs) as response:
            status_code = response.status
            if status_code in RAISE_STATUS:
                return status_code, {"detail": "outside server crash"}
            rsp_text = await response.json()

        return status_code, rsp_text

    async def patch(self, url: str, **kwargs: Any) -> Tuple[int, Dict]:
        async with self._request_client.patch(url, **kwargs) as response:
            status_code = response.status
            if status_code in RAISE_STATUS:
                return status_code, {"detail": "outside server crash"}
            rsp_text = await response.json()

        return status_code, rsp_text
