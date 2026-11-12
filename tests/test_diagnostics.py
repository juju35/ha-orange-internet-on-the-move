"""Tests for the diagnostics."""

from __future__ import annotations

import json

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import DEVICE_ID, PASSWORD, SERIAL, TOKEN, USERNAME, setup_entry


async def test_diagnostics_redacted(hass: HomeAssistant, hass_client, portal: AiohttpClientMocker) -> None:
    assert await async_setup_component(hass, "diagnostics", {})
    entry = await setup_entry(hass)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    dumped = json.dumps(diag)
    for secret in (USERNAME, PASSWORD, SERIAL, DEVICE_ID, TOKEN, "Driver Name"):
        assert secret not in dumped
    assert diag["entry"]["data"] == {"username": REDACTED, "password": REDACTED}
    [device] = diag["devices"]
    assert device["device"]["tag"] == "Espace"
    assert device["plan"]["left_percentage"] == 76
