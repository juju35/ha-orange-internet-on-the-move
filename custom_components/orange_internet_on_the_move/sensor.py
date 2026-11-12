"""Sensors of the data plan of each car."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Plan
from .coordinator import OrangeIotmConfigEntry, OrangeIotmCoordinator
from .entity import OrangeIotmEntity

# The coordinator does the polling: entity updates never hit the portal.
PARALLEL_UPDATES = 0

_KIB_PER_MIB = 1024


def _mib(kib: float | None) -> float | None:
    return None if kib is None else round(kib / _KIB_PER_MIB, 3)


@dataclass(frozen=True, kw_only=True)
class OrangeIotmSensorDescription(SensorEntityDescription):
    """Sensor reading one value of the current plan."""

    value_fn: Callable[[Plan], float | int | str | datetime | None]


# The keys are the unique ID suffixes of rexave's integration (plus used_data, new).
# Data sizes are published in MiB, the value rexave's integration already stored (labelled
# Mbit there by mistake), so existing entities keep their numbers; new ones display GiB.
SENSORS: tuple[OrangeIotmSensorDescription, ...] = (
    OrangeIotmSensorDescription(
        key="left_data",
        translation_key="left_data",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        value_fn=lambda plan: _mib(plan.left_data),
    ),
    OrangeIotmSensorDescription(
        key="used_data",
        translation_key="used_data",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        value_fn=lambda plan: _mib(plan.used_data),
    ),
    OrangeIotmSensorDescription(
        key="initial_data",
        translation_key="initial_data",
        device_class=SensorDeviceClass.DATA_SIZE,
        # Kept from rexave's integration: without it, Home Assistant flags its existing statistics.
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        value_fn=lambda plan: _mib(plan.initial_data),
    ),
    OrangeIotmSensorDescription(
        key="left_data_percentage",
        translation_key="left_data_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda plan: plan.left_percentage,
    ),
    OrangeIotmSensorDescription(
        key="start_date",
        translation_key="start_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda plan: plan.start_date,
    ),
    OrangeIotmSensorDescription(
        key="expiry_date",
        translation_key="expiry_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda plan: plan.expiry_date,
    ),
    OrangeIotmSensorDescription(
        key="plan_type",
        translation_key="plan_type",
        value_fn=lambda plan: plan.plan_type,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OrangeIotmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors of every device, and of the devices added to the account later."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new = [device_id for device_id in coordinator.data or {} if device_id not in known]
        if not new:
            return
        known.update(new)
        async_add_entities(
            OrangeIotmSensor(coordinator, device_id, description) for device_id in new for description in SENSORS
        )

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class OrangeIotmSensor(OrangeIotmEntity, SensorEntity):
    """One value of the current plan of a device."""

    entity_description: OrangeIotmSensorDescription

    def __init__(
        self, coordinator: OrangeIotmCoordinator, device_id: str, description: OrangeIotmSensorDescription
    ) -> None:
        """Remember what to read."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | datetime | None:
        """Read from the latest data: unknown while the device has no plan."""
        data = self.device_data
        if data is None or data.plan is None:
            return None
        return self.entity_description.value_fn(data.plan)
