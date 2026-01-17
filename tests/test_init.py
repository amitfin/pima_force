"""The tests for the pima_force integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_NAME, CONF_PORT, Platform
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.pima_force import (
    PimaForceRuntimeData,
    async_setup,
    async_setup_entry,
    async_unload_entry,
    config_entry_update_listener,
)
from custom_components.pima_force.const import (
    CONF_ZONES,
    DEFAULT_LISTENING_PORT,
    DOMAIN,
    SERVICE_GET_ZONES,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_setup(hass: HomeAssistant) -> None:
    """Test basic setup flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_setup_get_zones_action(hass: HomeAssistant) -> None:
    """Test get_zones service returns configured zone names."""
    zones = [{CONF_NAME: "Front Door"}, {CONF_NAME: ""}]
    config_entry = MockConfigEntry(domain=DOMAIN, options={CONF_ZONES: zones})
    config_entry.add_to_hass(hass)

    assert await async_setup(hass, {})

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ZONES,
        {ATTR_CONFIG_ENTRY_ID: config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == {CONF_ZONES: ["Front Door", ""]}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_ZONES,
            {ATTR_CONFIG_ENTRY_ID: "missing_entry"},
            blocking=True,
            return_response=True,
        )


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry assigns runtime data and starts the coordinator."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    coordinator = MagicMock()
    coordinator.async_start = AsyncMock()
    with patch(
        "custom_components.pima_force.PimaForceDataUpdateCoordinator",
        return_value=coordinator,
    ):
        assert await async_setup_entry(hass, config_entry)

    assert isinstance(config_entry.runtime_data, PimaForceRuntimeData)
    assert config_entry.runtime_data.coordinator is coordinator
    coordinator.async_start.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        config_entry, (Platform.BINARY_SENSOR,)
    )


async def test_config_entry_update_listener(hass: HomeAssistant) -> None:
    """Test config entry update listener triggers a reload."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    hass.config_entries.async_schedule_reload = MagicMock()

    await config_entry_update_listener(hass, config_entry)

    hass.config_entries.async_schedule_reload.assert_called_once_with(
        config_entry.entry_id
    )


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test async_unload_entry stops the coordinator."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    coordinator = MagicMock()
    coordinator.async_stop = AsyncMock()
    config_entry.runtime_data = PimaForceRuntimeData(coordinator=coordinator)

    assert await async_unload_entry(hass, config_entry)
    coordinator.async_stop.assert_awaited_once()
