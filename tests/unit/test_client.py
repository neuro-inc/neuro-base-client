import asyncio
from collections.abc import AsyncIterator

import pytest

from apolo_base_client import HttpClient


@pytest.fixture
async def client() -> AsyncIterator[HttpClient]:
    async with HttpClient(
        base_url="https://base.url",
        auth0_url="https://auth0.url",
        client_id="client_id",
        audience="<audience>",
        secret="secret",
    ) as cl:
        yield cl


async def test_is_not_expired(client: HttpClient) -> None:
    client._expiration_time = 2075
    assert not client.is_expired(now=2000)


async def test_is_expired(client: HttpClient) -> None:
    client._expiration_time = 2075
    assert client.is_expired(now=2100)


async def test_update_token(client: HttpClient) -> None:
    loop = asyncio.get_running_loop()
    client._update_token("new-token", 100)
    assert client._access_token == "Bearer new-token"
    now = loop.time()
    assert client._expiration_time <= now + 75
