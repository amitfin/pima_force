"""The tests for the pima_force integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.exceptions import ServiceValidationError
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
    SERVICE_SET_ZONES,
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
    assert config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.config_entries.async_get_entry(config_entry.entry_id) is None


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


@pytest.mark.parametrize(
    ("service", "data", "return_response"),
    [
        (SERVICE_GET_ZONES, {}, True),
        (SERVICE_SET_ZONES, {CONF_ZONES: ["Front Door"]}, False),
    ],
)
@pytest.mark.parametrize("foreign_domain", [None, "sun"])
async def test_async_setup_zones_actions_reject_invalid_entry(
    hass: HomeAssistant,
    service: str,
    data: dict[str, Any],
    foreign_domain: str | None,
    *,
    return_response: bool,
) -> None:
    """Test zone actions reject missing and other integrations' config entries."""
    entry_id = "missing_entry"
    foreign_entry = None
    if foreign_domain:
        foreign_entry = MockConfigEntry(domain=foreign_domain, options={"key": 1})
        foreign_entry.add_to_hass(hass)
        entry_id = foreign_entry.entry_id

    assert await async_setup(hass, {})

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: entry_id, **data},
            blocking=True,
            return_response=return_response,
        )

    assert err.value.translation_key == "invalid_config_entry"
    assert err.value.translation_placeholders == {"entry_id": entry_id}
    if foreign_entry:
        assert foreign_entry.options == {"key": 1}


async def test_async_setup_set_zones_action(hass: HomeAssistant) -> None:
    """Test set_zones service updates configured zone names."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT, CONF_ZONES: []},
    )
    config_entry.add_to_hass(hass)

    assert await async_setup(hass, {})

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ZONES,
        {
            ATTR_CONFIG_ENTRY_ID: config_entry.entry_id,
            CONF_ZONES: ["Front Door", "Back Door"],
        },
        blocking=True,
    )

    assert config_entry.options[CONF_ZONES] == [
        {CONF_NAME: "Front Door"},
        {CONF_NAME: "Back Door"},
    ]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ZONES,
        {ATTR_CONFIG_ENTRY_ID: config_entry.entry_id, CONF_ZONES: ["", "Hall"]},
        blocking=True,
    )

    assert config_entry.options[CONF_ZONES] == [{CONF_NAME: ""}, {CONF_NAME: "Hall"}]


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry assigns runtime data and starts the coordinator."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    coordinator = MagicMock()
    coordinator.async_start = AsyncMock()
    coordinator.async_stop = AsyncMock()
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


async def test_async_setup_entry_port_in_use(
    hass: HomeAssistant, auto_mock_sia_client_tcp: MagicMock
) -> None:
    """Test setup is retried when the listening port can't be bound."""
    auto_mock_sia_client_tcp.async_start.side_effect = OSError(
        98, "Address already in use"
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_PORT: DEFAULT_LISTENING_PORT}
    )
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.reason == (
        f"Unable to listen on port {DEFAULT_LISTENING_PORT}: "
        "[Errno 98] Address already in use"
    )


async def test_async_setup_entry_forward_failure_stops_server(
    hass: HomeAssistant,
) -> None:
    """Test the SIA server is stopped when platform setup fails."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=RuntimeError)

    coordinator = MagicMock()
    coordinator.async_start = AsyncMock()
    coordinator.async_stop = AsyncMock()
    with (
        patch(
            "custom_components.pima_force.PimaForceDataUpdateCoordinator",
            return_value=coordinator,
        ),
        pytest.raises(RuntimeError),
    ):
        await async_setup_entry(hass, config_entry)

    coordinator.async_stop.assert_awaited_once()


async def test_sia_server_stopped_when_home_assistant_stops(
    hass: HomeAssistant, auto_mock_sia_client_tcp: MagicMock
) -> None:
    """Test the SIA server is stopped on stop, and the listener removed on unload."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_PORT: DEFAULT_LISTENING_PORT}
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    auto_mock_sia_client_tcp.async_stop.assert_awaited_once()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    auto_mock_sia_client_tcp.async_stop.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    auto_mock_sia_client_tcp.async_stop.assert_not_awaited()


async def test_config_entry_update_listener(hass: HomeAssistant) -> None:
    """Test config entry update listener triggers a reload."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    hass.config_entries.async_schedule_reload = MagicMock()

    await config_entry_update_listener(hass, config_entry)

    hass.config_entries.async_schedule_reload.assert_called_once_with(
        config_entry.entry_id
    )


@pytest.mark.parametrize("unloaded", [True, False])
async def test_async_unload_entry(hass: HomeAssistant, *, unloaded: bool) -> None:
    """Test async_unload_entry stops the coordinator only if platforms unload."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    coordinator = MagicMock()
    coordinator.async_stop = AsyncMock()
    config_entry.runtime_data = PimaForceRuntimeData(coordinator=coordinator)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=unloaded)

    assert await async_unload_entry(hass, config_entry) is unloaded
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        config_entry, (Platform.BINARY_SENSOR,)
    )
    assert coordinator.async_stop.await_count == int(unloaded)
