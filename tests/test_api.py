"""Tests for the portal client."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

from custom_components.orange_internet_on_the_move.api import (
    OrangeIotmAuthError,
    OrangeIotmClient,
    OrangeIotmError,
    Plan,
    select_plan,
)
from custom_components.orange_internet_on_the_move.const import BASE_URL, DEVICES_PATH, LOGIN_PATH

from .conftest import DEVICE_ID, PASSWORD, TOKEN, USERNAME, mock_portal

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _plan(start: str | None, expiry: str | None, left: float = 1) -> Plan:
    return Plan(
        plan_type="onetime",
        initial_data=4,
        left_data=left,
        start_date=None if start is None else datetime.fromisoformat(start),
        expiry_date=None if expiry is None else datetime.fromisoformat(expiry),
    )


def _client(hass: HomeAssistant) -> OrangeIotmClient:
    return OrangeIotmClient(async_get_clientsession(hass), USERNAME, PASSWORD)


def _logins(aioclient_mock: AiohttpClientMocker) -> int:
    return sum(1 for method, url, *_ in aioclient_mock.mock_calls if method == "POST" and url.path == LOGIN_PATH)


def test_select_plan_prefers_running_plan() -> None:
    past = _plan("2025-01-01T00:00:00+00:00", "2025-06-01T00:00:00+00:00")
    running = _plan("2026-05-01T00:00:00+00:00", "2026-07-01T00:00:00+00:00")
    upcoming = _plan("2026-07-01T00:00:00+00:00", "2026-09-01T00:00:00+00:00")
    assert select_plan([past, upcoming, running], NOW) is running
    assert select_plan([], NOW) is None
    # Nothing running: the one that started last.
    assert select_plan([past, upcoming], NOW) is upcoming


def test_plan_figures() -> None:
    plan = _plan(None, None, left=3.99)
    assert plan.left_percentage == 99  # never rounded up to 100 once data was used
    assert plan.used_data == pytest.approx(0.01)
    assert Plan("x", 0, 0, None, None).left_percentage is None  # no division by zero
    assert Plan("x", 4, 5, None, None).left_percentage == 100
    assert Plan("x", None, 1, None, None).used_data is None


async def test_get_data(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    data = await _client(hass).async_get_data(NOW)
    plan = data[DEVICE_ID].plan
    assert data[DEVICE_ID].device.tag == "Espace"
    assert plan.left_data == 2411724
    assert plan.expiry_date == datetime(2099, 1, 1, tzinfo=UTC)  # offset-less date read as UTC


async def test_token_reused_across_updates(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    """One login, then the token is sent on every call (rexave's integration logged in on each update)."""
    client = _client(hass)
    await client.async_get_data(NOW)
    await client.async_get_data(NOW)
    assert _logins(portal) == 1
    for method, _url, _data, headers in portal.mock_calls:
        if method == "GET":
            assert headers["x-auth-token"] == TOKEN


async def test_relogin_when_token_rejected(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_portal(aioclient_mock)
    client = _client(hass)
    await client.async_get_devices()
    calls = 0

    async def expired_once(method, url, data):
        nonlocal calls
        calls += 1
        return AiohttpClientMockResponse(method, url, status=401 if calls == 1 else 200, json=[])

    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{BASE_URL}{LOGIN_PATH}", headers={"x-auth-token": "token-2"})
    aioclient_mock.get(f"{BASE_URL}{DEVICES_PATH}", side_effect=expired_once)
    assert await client.async_get_devices() == []
    assert _logins(aioclient_mock) == 1
    assert aioclient_mock.mock_calls[-1][3]["x-auth-token"] == "token-2"


async def test_auth_error_when_still_rejected(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_portal(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{BASE_URL}{LOGIN_PATH}", headers={"x-auth-token": TOKEN})
    aioclient_mock.get(f"{BASE_URL}{DEVICES_PATH}", status=403)
    with pytest.raises(OrangeIotmAuthError):
        await _client(hass).async_get_devices()
    assert _logins(aioclient_mock) == 2  # one retry, not a loop


@pytest.mark.parametrize(("status", "error"), [(401, OrangeIotmAuthError), (500, OrangeIotmError)])
async def test_login_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status, error) -> None:
    mock_portal(aioclient_mock, login_status=status)
    with pytest.raises(error):
        await _client(hass).async_login()


async def test_login_without_token(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(f"{BASE_URL}{LOGIN_PATH}")
    with pytest.raises(OrangeIotmError):
        await _client(hass).async_login()


@pytest.mark.parametrize("exc", [aiohttp.ClientError(), TimeoutError()])
async def test_network_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, exc) -> None:
    aioclient_mock.post(f"{BASE_URL}{LOGIN_PATH}", exc=exc)
    with pytest.raises(OrangeIotmError) as err:
        await _client(hass).async_get_devices()
    assert not isinstance(err.value, OrangeIotmAuthError)


async def test_unexpected_payload(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_portal(aioclient_mock, devices={"error": "x"})  # type: ignore[arg-type]
    with pytest.raises(OrangeIotmError):
        await _client(hass).async_get_devices()


async def test_parallel_requests_log_in_once(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    client = _client(hass)
    await asyncio.gather(*(client.async_get_devices() for _ in range(5)))
    assert _logins(portal) == 1


async def test_credentials_never_logged(
    hass: HomeAssistant, portal: AiohttpClientMocker, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("DEBUG")
    await _client(hass).async_get_data(NOW)
    assert PASSWORD not in caplog.text
    assert TOKEN not in caplog.text
