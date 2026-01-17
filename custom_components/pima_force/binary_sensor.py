"""Support for representing pima force zones as binary sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import binary_sensor
from homeassistant.const import CONF_NAME, CONF_PORT, STATE_ON
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_LAST_CLOSE,
    ATTR_LAST_OPEN,
    ATTR_LAST_TOGGLE,
    ATTR_ZONE,
    CONF_ZONES,
    DOMAIN,
)
from .entity import PimaForceEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from custom_components.pima_force import PimaForceConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: PimaForceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    async_add_entities(
        PimaForceZoneBinarySensor(
            config_entry,
            index + 1,
            zone[CONF_NAME],
        )
        for index, zone in enumerate(config_entry.options.get(CONF_ZONES, []))
        if zone.get(CONF_NAME)
    )


class PimaForceZoneBinarySensor(
    PimaForceEntity, binary_sensor.BinarySensorEntity, RestoreEntity
):
    """Representation of the alert sensor base."""

    _attr_device_class = binary_sensor.BinarySensorDeviceClass.DOOR
    _unrecorded_attributes = frozenset(
        {ATTR_LAST_OPEN, ATTR_LAST_CLOSE, ATTR_LAST_TOGGLE}
    )

    def __init__(
        self, config_entry: PimaForceConfigEntry, zone: int, name: str
    ) -> None:
        """Initialize object with defaults."""
        super().__init__(config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{zone}"
        self.entity_id = (
            f"binary_sensor.{DOMAIN}_{config_entry.options[CONF_PORT]}_zone{zone}"
        )
        self._attr_name = name
        self._attr_is_on = False
        self._attr_extra_state_attributes = {
            ATTR_LAST_OPEN: None,
            ATTR_LAST_CLOSE: None,
            ATTR_LAST_TOGGLE: None,
            ATTR_ZONE: zone,
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

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            new_state := self.coordinator.zones.get(self._zone)
        ) is not None and new_state != self._attr_is_on:
            now = dt_util.now().isoformat()
            self._attr_extra_state_attributes[ATTR_LAST_TOGGLE] = now
            if new_state:
                self._attr_extra_state_attributes[ATTR_LAST_OPEN] = now
            else:
                self._attr_extra_state_attributes[ATTR_LAST_CLOSE] = now
            self._attr_is_on = new_state
            super()._handle_coordinator_update()
