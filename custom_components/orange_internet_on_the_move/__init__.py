"""Orange Internet On the move: the in-car data plan of Renault vehicles (Orange Business portal).

A drop-in replacement for rexave/hass-orange-internet-on-the-move: same domain, same
device identifiers and same entity unique IDs, so existing entities, their history
and dashboards are kept; the version 1 config entries it created are migrated.
"""

from __future__ import annotations

import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OrangeIotmClient
from .const import DOMAIN, LEGACY_CONF_PASSWORD, LEGACY_CONF_USERNAME
from .coordinator import OrangeIotmConfigEntry, OrangeIotmCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OrangeIotmConfigEntry) -> bool:
    """Set up the account: first refresh (retried by HA on failure), then the sensors."""
    client = OrangeIotmClient(async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = OrangeIotmCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OrangeIotmConfigEntry) -> bool:
    """Unload the sensors."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: OrangeIotmConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow deleting a device that is no longer on the account (a car sold, a SIM removed)."""
    data = entry.runtime_data.data or {}
    return not any(domain == DOMAIN and identifier in data for domain, identifier in device_entry.identifiers)


async def async_migrate_entry(hass: HomeAssistant, entry: OrangeIotmConfigEntry) -> bool:
    """Migrate the version 1 entries of rexave/hass-orange-internet-on-the-move.

    They stored the credentials under custom keys and had no unique ID, so the same
    account could be added twice.
    """
    if entry.version > 2:
        # Downgrade from a future version: refuse rather than guess.
        return False
    if entry.version == 1:
        data = dict(entry.data)
        username = data.pop(LEGACY_CONF_USERNAME, data.get(CONF_USERNAME))
        password = data.pop(LEGACY_CONF_PASSWORD, data.get(CONF_PASSWORD))
        data[CONF_USERNAME] = username
        data[CONF_PASSWORD] = password
        unique_id = entry.unique_id
        if unique_id is None and isinstance(username, str):
            candidate = username.strip().lower()
            # Two legacy entries of the same account: only the first one gets the unique ID.
            taken = any(
                other.unique_id == candidate
                for other in hass.config_entries.async_entries(DOMAIN)
                if other.entry_id != entry.entry_id
            )
            unique_id = None if taken else candidate
        hass.config_entries.async_update_entry(entry, data=data, unique_id=unique_id, version=2, minor_version=1)
        _LOGGER.debug("Migrated config entry %s to version 2", entry.entry_id)
    return True
