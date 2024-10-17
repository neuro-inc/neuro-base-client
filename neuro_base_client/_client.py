import asyncio
import contextlib
from collections.abc import AsyncIterator, Mapping
from types import TracebackType
from typing import Any, Optional, Type, Union

from aiohttp import ClientResponse, ClientResponseError, ClientSession, TraceConfig
from aiohttp.hdrs import AUTHORIZATION
from multidict import CIMultiDict
from typing_extensions import Self
from yarl import URL


class RefreshError(Exception):
    """Auth0 token refresh is impossible."""


class HttpClient:
    def __init__(
        self,
        *,
        base_url: Union[str, URL],
        auth0_url: Union[str, URL],
        client_id: str,
        audience: str,
        secret: str,
        expiration_ratio: float = 0.75,
        trace_configs: Optional[list[TraceConfig]] = None,
    ) -> None:
        self._auth0_url = URL(auth0_url)
        self._base_url = URL(base_url)
        self._client_id = client_id
        self._audience = audience
        self._secret = secret
        self._access_token = ""
        self._expiration_ratio = expiration_ratio
        self._expiration_time = 0.0  # request access token on startup
        self._client = ClientSession(trace_configs=trace_configs)

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_typ: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        await self.close()

    def is_expired(self, *, now: Optional[float] = None) -> bool:
        if now is None:
            loop = asyncio.get_running_loop()
            now = loop.time()
        return self._expiration_time <= now

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def expiration_time(self) -> str:
        return self._expiration_time

    def _generate_headers(self) -> CIMultiDict[str]:
        headers: CIMultiDict[str] = CIMultiDict()
        headers[AUTHORIZATION] = self._access_token
        return headers

    def _make_url(self, path: str) -> URL:
        if path.startswith("/"):
            path = path[1:]
        return self._base_url / path

    @contextlib.asynccontextmanager
    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[CIMultiDict[str]] = None,
        json: Any = None,
        params: Optional[Mapping[str, str]] = None,
        raise_for_status: bool = True,
    ) -> AsyncIterator[ClientResponse]:
        if self.is_expired():
            await self.refresh()

        url = self._make_url(path)
        real_headers = self._generate_headers()
        if headers is not None:
            real_headers.update(headers)

        resp = await self._client.request(
            method, url, headers=real_headers, params=params, json=json
        )
        if raise_for_status:
            await _raise_for_status(resp)
        try:
            yield resp
        finally:
            resp.release()

    async def refresh(self) -> None:
        payload = dict(
            grant_type="client_credentials",
            audience=self._audience,
            client_secret=self._secret,
            client_id=self._client_id,
        )
        async with self._client.post(
            self._auth0_url,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
            },
            json=payload,
        ) as resp:
            try:
                resp.raise_for_status()
            except ClientResponseError as exc:
                raise RefreshError("failed to get an access token.") from exc
            resp_payload = await resp.json()
            if resp_payload["token_type"] != "Bearer":
                raise RefreshError(
                    "unsupported token type " + resp_payload["token_type"]
                )
            self._update_token(resp_payload["access_token"], resp_payload["expires_in"])

    def _update_token(self, access_token: str, expires_in: float) -> None:
        self._access_token = "Bearer " + access_token
        loop = asyncio.get_running_loop()
        self._expiration_time = loop.time() + expires_in * self._expiration_ratio


async def _raise_for_status(resp: ClientResponse) -> None:
    if 400 <= resp.status:
        details: str
        try:
            obj = await resp.json()
        except asyncio.CancelledError:
            raise
        except Exception:
            # ignore any error with reading message body
            details = resp.reason  # type: ignore
        else:
            try:
                details = obj["error"]
            except KeyError:
                details = str(obj)
        raise ClientResponseError(
            resp.request_info,
            resp.history,
            status=resp.status,
            message=details,
            headers=resp.headers,
        )
