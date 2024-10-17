import asyncio

from aiohttp import web
from aiohttp.pytest_plugin import AiohttpServer

from apolo_base_client import HttpClient


async def test_refresh(client: HttpClient) -> None:
    await client.refresh()
    loop = asyncio.get_running_loop()
    assert client._access_token != ""
    assert client._expiration_time > loop.time()


async def test_request_autoinitialize(
    client: HttpClient, srv_port: int, aiohttp_server: AiohttpServer
) -> None:
    async def hello(request: web.Request) -> web.Response:
        return web.Response(text="hello")

    app = web.Application()
    app.router.add_get("/hello", hello)

    await aiohttp_server(app, port=srv_port)

    async with client.request("GET", "/hello") as resp:
        assert await resp.text() == "hello"

    assert client.access_token != ""
    loop = asyncio.get_running_loop()
    assert client.expiration_time > loop.time()


async def test_request_check_token(
    client: HttpClient, srv_port: int, aiohttp_server: AiohttpServer
) -> None:
    async def hello(request: web.Request) -> web.Response:
        assert request.headers["Authorization"] == token
        return web.Response(text="hello")

    app = web.Application()
    app.router.add_get("/hello", hello)

    await aiohttp_server(app, port=srv_port)

    await client.refresh()

    token = client.access_token

    async with client.request("GET", "/hello") as resp:
        assert await resp.text() == "hello"
