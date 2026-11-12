"""Tests for setup, sensors, migration and stability."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.orange_internet_on_the_move.const import BASE_URL, DEVICES_PATH, DOMAIN, LOGIN_PATH

from .conftest import DEVICE_ID, DEVICES, PASSWORD, PLANS, SERIAL, USERNAME, mock_portal, setup_entry

# Unique ID suffixes of rexave/hass-orange-internet-on-the-move: kept so its entities carry on.
LEGACY_KEYS = ("left_data_percentage", "left_data", "initial_data", "start_date", "expiry_date", "plan_type")


def _entity_id(hass: HomeAssistant, key: str, device_id: str = DEVICE_ID) -> str | None:
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{device_id}_{key}")


def _device(hass: HomeAssistant) -> dr.DeviceEntry:
    """The car's device; async_get_device is deprecated in recent Home Assistant, this works on all versions."""
    [entry] = hass.config_entries.async_entries(DOMAIN)
    [device] = [
        device
        for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        if (DOMAIN, DEVICE_ID) in device.identifiers
    ]
    return device


async def _update(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_sensors(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    left = hass.states.get(_entity_id(hass, "left_data"))
    assert float(left.state) == pytest.approx(2.30, abs=0.01)  # 2411724 KiB shown in GiB
    assert left.attributes["unit_of_measurement"] == "GiB"
    assert left.attributes["friendly_name"] == "Espace Data left"
    assert float(hass.states.get(_entity_id(hass, "initial_data")).state) == pytest.approx(3.0)
    assert float(hass.states.get(_entity_id(hass, "used_data")).state) == pytest.approx(0.70, abs=0.01)
    assert hass.states.get(_entity_id(hass, "left_data_percentage")).state == "76"
    # The running plan, not the first one listed.
    assert hass.states.get(_entity_id(hass, "start_date")).state == "2026-01-01T00:00:00+00:00"
    assert hass.states.get(_entity_id(hass, "expiry_date")).state == "2099-01-01T00:00:00+00:00"
    assert hass.states.get(_entity_id(hass, "plan_type")).state == "onetime"

    device = _device(hass)
    assert device.name == "Espace"
    assert device.manufacturer == "Orange"
    assert device.serial_number == SERIAL


async def test_every_entity_has_unique_id_and_legacy_ids(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    """rexave's integration also added its base class as an entity without unique ID (deprecated in 2027.8)."""
    entry = await setup_entry(hass)
    registered = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert {e.entity_id for e in registered} == set(hass.states.async_entity_ids("sensor"))
    assert len(registered) == 7
    for key in LEGACY_KEYS:
        assert _entity_id(hass, key) is not None, key


async def test_no_deprecation_warnings(
    hass: HomeAssistant, portal: AiohttpClientMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """No CONN_CLASS_CLOUD_POLL (removed in 2027.5) or other frame-helper report."""
    caplog.set_level(logging.WARNING, logger="homeassistant.helpers.frame")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()
    assert not [r for r in caplog.records if r.name == "homeassistant.helpers.frame"]


async def test_cannot_connect_retries_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(f"{BASE_URL}{LOGIN_PATH}", exc=TimeoutError())
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_bad_credentials_start_reauth(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_portal(aioclient_mock, login_status=401)
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_failed_update_marks_unavailable_then_recovers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_portal(aioclient_mock)
    await setup_entry(hass)
    entity_id = _entity_id(hass, "left_data")
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE_URL}{DEVICES_PATH}", status=500)
    await _update(hass)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    mock_portal(aioclient_mock)
    await _update(hass)
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_device_without_plan(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_portal(aioclient_mock, plans={DEVICE_ID: []})
    await setup_entry(hass)
    assert hass.states.get(_entity_id(hass, "left_data")).state == STATE_UNKNOWN


async def test_several_cars_and_new_car_added(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Every car of the account (rexave's integration read the first one only), and cars added later."""
    mock_portal(aioclient_mock)
    await setup_entry(hass)
    assert _entity_id(hass, "left_data", "other") is None
    second = {**DEVICES[0], "id": "other", "tag": "Captur", "serial_number": "8933999"}
    mock_portal(aioclient_mock, devices=[*DEVICES, second], plans={DEVICE_ID: PLANS, "other": PLANS})
    await _update(hass)
    entity_id = _entity_id(hass, "left_data", "other")
    assert entity_id is not None
    assert hass.states.get(entity_id).attributes["friendly_name"] == "Captur Data left"


async def test_removed_car_unavailable_and_deletable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, hass_ws_client
) -> None:
    mock_portal(aioclient_mock)
    entry = await setup_entry(hass)
    assert await async_setup_component(hass, "config", {})
    device = _device(hass)
    client = await hass_ws_client(hass)

    async def remove() -> bool:
        await client.send_json_auto_id(
            {
                "type": "config/device_registry/remove_config_entry",
                "config_entry_id": entry.entry_id,
                "device_id": device.id,
            }
        )
        return (await client.receive_json())["success"]

    assert not await remove()  # still on the account
    mock_portal(aioclient_mock, devices=[], plans={})
    await _update(hass)
    assert hass.states.get(_entity_id(hass, "left_data")).state == STATE_UNAVAILABLE
    assert await remove()


async def test_migrate_rexave_entry(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    """A version 1 entry of rexave's integration keeps its entities, now with standard keys and a unique ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Orange Internet on the move Data",
        data={"config_username": f" {USERNAME.upper()}", "config_password": PASSWORD},
    )
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    old = ent_reg.async_get_or_create("sensor", DOMAIN, f"{DEVICE_ID}_left_data", config_entry=entry)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.data == {CONF_USERNAME: f" {USERNAME.upper()}", CONF_PASSWORD: PASSWORD}
    assert entry.unique_id == USERNAME
    assert _entity_id(hass, "left_data") == old.entity_id
    assert hass.states.get(old.entity_id).state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


async def test_migrate_duplicate_rexave_entries(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    """Two legacy entries of one account: the second migrates without a clashing unique ID."""
    entries = [
        MockConfigEntry(domain=DOMAIN, version=1, data={"config_username": USERNAME, "config_password": PASSWORD})
        for _ in range(2)
    ]
    for entry in entries:
        entry.add_to_hass(hass)
    # Setting up the integration sets up every entry of the domain.
    await hass.config_entries.async_setup(entries[0].entry_id)
    await hass.async_block_till_done()
    assert [entry.version for entry in entries] == [2, 2]
    assert sorted(str(entry.unique_id) for entry in entries) == ["None", USERNAME]


async def test_refuse_downgrade(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=3, data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_unload(hass: HomeAssistant, portal: AiohttpClientMocker) -> None:
    entry = await setup_entry(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
