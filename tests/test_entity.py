"""Tests for the entity base class."""

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pima_force import PimaForceRuntimeData
from custom_components.pima_force.const import (
    DEFAULT_LISTENING_PORT,
    DOMAIN,
)
from custom_components.pima_force.coordinator import PimaForceDataUpdateCoordinator
from custom_components.pima_force.entity import PimaForceEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_entity_device_info(hass: HomeAssistant) -> None:
    """Test device info on the base entity."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    config_entry.runtime_data = PimaForceRuntimeData(
        PimaForceDataUpdateCoordinator(hass, config_entry)
    )

    entity = PimaForceEntity(config_entry)
    device_info = entity.device_info

    assert device_info is not None
    assert device_info.get("name") == "Pima Force"
    assert device_info.get("manufacturer") == "Pima"
    assert device_info.get("model") == "Force"
    assert device_info.get("identifiers") == {(DOMAIN, config_entry.entry_id)}
