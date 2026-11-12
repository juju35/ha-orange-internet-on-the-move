"""Diagnostics: the devices and their current plan, without credentials or identifiers."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import OrangeIotmConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "serial_number", "device_id"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: OrangeIotmConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    devices = [
        {
            "device": asdict(data.device),
            "plan": None if data.plan is None else {**asdict(data.plan), "left_percentage": data.plan.left_percentage},
        }
        for data in (coordinator.data or {}).values()
    ]
    return async_redact_data(
        {
            "entry": {"version": entry.version, "minor_version": entry.minor_version, "data": dict(entry.data)},
            "last_update_success": coordinator.last_update_success,
            "devices": devices,
        },
        TO_REDACT,
    )
