"""Base entity: one device per car of the account."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import DeviceData
from .const import DOMAIN
from .coordinator import OrangeIotmCoordinator


class OrangeIotmEntity(CoordinatorEntity[OrangeIotmCoordinator]):
    """An entity of one device, fed by the account coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OrangeIotmCoordinator, device_id: str, key: str) -> None:
        """Attach to the device; the unique ID keeps the format of rexave's integration."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        device = coordinator.data[device_id].device
        serial = device.serial_number
        self._attr_device_info = DeviceInfo(
            # Same identifier as rexave's integration, so its device is reused.
            identifiers={(DOMAIN, device_id)},
            name=device.tag or f"Internet On the move {(serial or device_id)[-4:]}",
            manufacturer="Orange",
            model="Internet On the move",
            serial_number=serial,
            configuration_url="https://internetonthemove.orange-business.com/",
        )

    @property
    def device_data(self) -> DeviceData | None:
        """The latest data of this device, None once it left the account."""
        return (self.coordinator.data or {}).get(self._device_id)

    @property
    def available(self) -> bool:
        """Unavailable when the last update failed or the device is no longer on the account."""
        return super().available and self.device_data is not None
