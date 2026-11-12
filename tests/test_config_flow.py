"""Tests for the config flow."""

from __future__ import annotations

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.orange_internet_on_the_move.const import BASE_URL, DOMAIN, LOGIN_PATH

from .conftest import PASSWORD, USERNAME, make_entry, mock_portal, setup_entry

INPUT = {CONF_USERNAME: f"  {USERNAME}  ", CONF_PASSWORD: PASSWORD}


async def _start(hass: HomeAssistant) -> dict:
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def test_user_flow(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"] == {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    assert result["result"].unique_id == USERNAME


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"status": 401}, "invalid_auth"),
        ({"status": 503}, "cannot_connect"),
        ({"exc": TimeoutError()}, "cannot_connect"),
    ],
)
async def test_user_flow_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, kwargs, error) -> None:
    aioclient_mock.post(f"{BASE_URL}{LOGIN_PATH}", **kwargs)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    # Then it works.
    mock_portal(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, monkeypatch) -> None:
    async def boom(self):
        raise RuntimeError

    monkeypatch.setattr("custom_components.orange_internet_on_the_move.api.OrangeIotmClient.async_login", boom)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["errors"] == {"base": "unknown"}


async def test_same_account_twice(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    make_entry().add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME.upper(), CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_portal(aioclient_mock)
    entry = await setup_entry(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    mock_portal(aioclient_mock, login_status=401)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}
    mock_portal(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {CONF_USERNAME: USERNAME, CONF_PASSWORD: "new"}


async def test_reconfigure(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    entry = await setup_entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: "new"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PASSWORD] == "new"


async def test_reconfigure_other_account(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    entry = await setup_entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "other@example.com", CONF_PASSWORD: PASSWORD}
    )
    assert result["reason"] == "wrong_account"
