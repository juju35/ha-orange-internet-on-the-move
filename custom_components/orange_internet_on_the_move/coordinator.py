"""Coordinator polling the portal once for every entity of the account."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DeviceData, OrangeIotmAuthError, OrangeIotmClient, OrangeIotmError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type OrangeIotmConfigEntry = ConfigEntry[OrangeIotmCoordinator]


class OrangeIotmCoordinator(DataUpdateCoordinator[dict[str, DeviceData]]):
    """Fetches the devices of the account and their current plan."""

    config_entry: OrangeIotmConfigEntry

    def __init__(self, hass: HomeAssistant, entry: OrangeIotmConfigEntry, client: OrangeIotmClient) -> None:
        """Poll hourly; the first refresh happens in async_setup_entry."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> dict[str, DeviceData]:
        try:
            data = await self.client.async_get_data(dt_util.utcnow())
        except OrangeIotmAuthError as err:
            # Stops polling and asks the user to sign in again (reauth flow).
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="invalid_auth") from err
        except OrangeIotmError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed", translation_placeholders={"error": str(err)}
            ) from err
        _LOGGER.debug("Fetched %d device(s)", len(data))
        return data
