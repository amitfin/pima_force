"""Support for representing pima force zones as binary sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

import homeassistant.helpers.config_validation as cv
import probatio
from homeassistant.components import binary_sensor
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.const import CONF_NAME, CONF_PORT, STATE_ON
from homeassistant.helpers import entity_platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_LAST_CLOSE,
    ATTR_LAST_OPEN,
    ATTR_LAST_SET,
    ATTR_ZONE,
    CONF_ZONES,
    DOMAIN,
    SERVICE_SET_CLOSED,
    SERVICE_SET_OPEN,
)
from .entity import PimaForceEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.pima_force import PimaForceConfigEntry

PARALLEL_UPDATES = 0

SERVICE_SCHEMA = cv.make_entity_service_schema(None, extra=probatio.ALLOW_EXTRA)


def _unique_id(config_entry: PimaForceConfigEntry, zone: int) -> str:
    """Return the unique ID of a zone's entity."""
    return f"{config_entry.entry_id}_{zone}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PimaForceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    zones = {
        index + 1: zone[CONF_NAME]
        for index, zone in enumerate(config_entry.options.get(CONF_ZONES, []))
        if zone.get(CONF_NAME)
    }
    unique_ids = {_unique_id(config_entry, zone) for zone in zones}
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if entity.unique_id not in unique_ids:
            entity_registry.async_remove(entity.entity_id)

    now = dt_util.now().isoformat()
    async_add_entities(
        PimaForceZoneBinarySensor(config_entry, zone, name, now)
        for zone, name in zones.items()
    )
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_OPEN, SERVICE_SCHEMA, "async_set_open"
    )
    platform.async_register_entity_service(
        SERVICE_SET_CLOSED, SERVICE_SCHEMA, "async_set_closed"
    )


class PimaForceZoneBinarySensor(
    PimaForceEntity, binary_sensor.BinarySensorEntity, RestoreEntity
):
    """Representation of the alert sensor base."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    _unrecorded_attributes = frozenset(
        {ATTR_ZONE, ATTR_LAST_SET, ATTR_LAST_OPEN, ATTR_LAST_CLOSE}
    )

    def __init__(
        self, config_entry: PimaForceConfigEntry, zone: int, name: str, now: str
    ) -> None:
        """Initialize object with defaults."""
        super().__init__(config_entry)
        self._attr_unique_id = _unique_id(config_entry, zone)
        self.entity_id = (
            f"binary_sensor.{DOMAIN}_{config_entry.options[CONF_PORT]}_zone{zone}"
        )
        self._attr_name = name
        self._attr_is_on = False
        self._attr_extra_state_attributes = {
            ATTR_ZONE: zone,
            ATTR_LAST_SET: now,
            ATTR_LAST_OPEN: None,
            ATTR_LAST_CLOSE: now,
        }
        self._zone = zone

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._attr_is_on = last_state.state == STATE_ON
            for key in self._attr_extra_state_attributes:
                if key in last_state.attributes:
                    self._attr_extra_state_attributes[key] = last_state.attributes[key]
        self._apply_zone_state()

    def _apply_zone_state(self) -> bool:
        """Apply the coordinator's zone state and return whether it changed."""
        if (
            new_state := self.coordinator.zones.get(self._zone)
        ) is None or new_state == self._attr_is_on:
            return False
        now = dt_util.now().isoformat()
        self._attr_extra_state_attributes[ATTR_LAST_SET] = now
        if new_state:
            self._attr_extra_state_attributes[ATTR_LAST_OPEN] = now
        else:
            self._attr_extra_state_attributes[ATTR_LAST_CLOSE] = now
        self._attr_is_on = new_state
        return True

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._apply_zone_state():
            super()._handle_coordinator_update()

    async def async_set_open(self) -> None:
        """Set the zone state to open."""
        self.coordinator.zones[self._zone] = True
        self._handle_coordinator_update()

    async def async_set_closed(self) -> None:
        """Set the zone state to closed."""
        self.coordinator.zones[self._zone] = False
        self._handle_coordinator_update()
