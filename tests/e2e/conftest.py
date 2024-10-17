import os
from collections.abc import AsyncIterator
from typing import Callable

import pytest

from apolo_base_client import HttpClient


@pytest.fixture
def srv_port(unused_tcp_port_factory: Callable[[], int]) -> int:
    return unused_tcp_port_factory()


@pytest.fixture
async def client(srv_port: int) -> AsyncIterator[HttpClient]:
    async with HttpClient(
        base_url=f"http://localhost:{srv_port}",
        auth0_url=os.environ["E2E_AUTH0_URL"],
        client_id=os.environ["E2E_CLIENT_ID"],
        audience=os.environ["E2E_AUDIENCE"],
        secret=os.environ["E2E_CLIENT_SECRET"],
    ) as cl:
        yield cl
