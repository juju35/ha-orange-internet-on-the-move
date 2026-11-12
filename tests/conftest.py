"""Fixtures: a mocked Orange Internet On the move portal."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.orange_internet_on_the_move.const import (
    BASE_URL,
    CONSUMPTION_PATH,
    DEVICES_PATH,
    DOMAIN,
    LOGIN_PATH,
)

USERNAME = "driver@example.com"
PASSWORD = "s3cret"
TOKEN = "token-1"
DEVICE_ID = "5f2a9c"
SERIAL = "89330123456789012345"

DEVICES = [
    {
        "id": DEVICE_ID,
        "country": "FR",
        "status": "ACTIVE",
        "tag": "Espace",
        "user": {"id": "u1", "name": "Driver Name"},
        "creation_date": "2024-03-01T10:00:00Z",
        "serial_number": SERIAL,
    }
]

# A past plan listed first (as the portal may do), then the running one.
PLANS = [
    {
        "type": "onetime",
        "initial_data": 1048576,
        "left_data": 0,
        "start_date": "2020-01-01T00:00:00+00:00",
        "expiry_date": "2021-01-01T00:00:00+00:00",
    },
    {
        "type": "onetime",
        "initial_data": 3145728,  # KiB: 3 GiB
        "left_data": 2411724,
        "start_date": "2026-01-01T00:00:00+00:00",
        "expiry_date": "2099-01-01T00:00:00",  # no offset: read as UTC
    },
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


def mock_portal(
    aioclient_mock: AiohttpClientMocker,
    *,
    devices: list[dict[str, Any]] | None = None,
    plans: dict[str, list[dict[str, Any]]] | None = None,
    login_status: int = 200,
) -> None:
    """Register the portal endpoints (replacing any earlier ones)."""
    aioclient_mock.clear_requests()
    devices = DEVICES if devices is None else devices
    plans = {DEVICE_ID: PLANS} if plans is None else plans
    aioclient_mock.post(
        f"{BASE_URL}{LOGIN_PATH}",
        status=login_status,
        headers={"x-auth-token": TOKEN} if login_status == 200 else None,
    )
    aioclient_mock.get(f"{BASE_URL}{DEVICES_PATH}", json=devices)
    for device_id, device_plans in plans.items():
        aioclient_mock.get(f"{BASE_URL}{CONSUMPTION_PATH.format(device_id=device_id)}", json=device_plans)


@pytest.fixture
def portal(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """The portal with one car and its plans."""
    mock_portal(aioclient_mock)
    return aioclient_mock


def make_entry(**kwargs: Any) -> MockConfigEntry:
    """A version 2 entry of the test account."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=USERNAME,
        title=USERNAME,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        **kwargs,
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry | None = None) -> MockConfigEntry:
    """Add and set up an entry."""
    entry = entry or make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
