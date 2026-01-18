"""Tests for the coordinator."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from homeassistant.const import CONF_PORT
from pysiaalarm.event import SIAEvent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pima_force.const import (
    ADM_CID_EVENT_QUALIFIER_CLOSE,
    ADM_CID_EVENT_QUALIFIER_OPEN,
    ADM_CID_PIMA_ZONE_STATUS_CODE,
    DEFAULT_LISTENING_PORT,
    DOMAIN,
)
from custom_components.pima_force.coordinator import PimaForceDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_process_event_updates_zone(hass: HomeAssistant) -> None:
    """Test that qualifying events update zones."""
    coordinator = PimaForceDataUpdateCoordinator(
        hass,
        MockConfigEntry(
            domain=DOMAIN,
            options={CONF_PORT: DEFAULT_LISTENING_PORT},
        ),
    )
    mock_update_listeners = MagicMock()
    coordinator.async_update_listeners = mock_update_listeners

    await coordinator.process_event(
        SIAEvent(
            event_type=ADM_CID_PIMA_ZONE_STATUS_CODE,
            event_qualifier=ADM_CID_EVENT_QUALIFIER_OPEN,
            ri="2",
        )
    )
    assert coordinator.zones == {2: True}
    mock_update_listeners.assert_called_once()

    mock_update_listeners.reset_mock()
    await coordinator.process_event(
        SIAEvent(
            event_type=ADM_CID_PIMA_ZONE_STATUS_CODE,
            event_qualifier=ADM_CID_EVENT_QUALIFIER_CLOSE,
            ri="2",
        )
    )
    assert coordinator.zones == {2: False}
    mock_update_listeners.assert_called_once()


async def test_process_event_ignores_non_zone_event(hass: HomeAssistant) -> None:
    """Test that non-matching events are ignored."""
    coordinator = PimaForceDataUpdateCoordinator(
        hass,
        MockConfigEntry(
            domain=DOMAIN,
            options={CONF_PORT: DEFAULT_LISTENING_PORT},
        ),
    )
    coordinator.async_update_listeners = MagicMock()

    await coordinator.process_event(
        SIAEvent(
            event_type="999",
            event_qualifier=ADM_CID_EVENT_QUALIFIER_OPEN,
            ri="2",
        )
    )
    await coordinator.process_event(
        SIAEvent(
            event_type=ADM_CID_PIMA_ZONE_STATUS_CODE,
            event_qualifier="9",
            ri="2",
        )
    )
    await coordinator.process_event(
        SIAEvent(
            event_type=ADM_CID_PIMA_ZONE_STATUS_CODE,
            event_qualifier=ADM_CID_EVENT_QUALIFIER_OPEN,
            ri=None,
        )
    )

    assert coordinator.zones == {}
    coordinator.async_update_listeners.assert_not_called()


async def test_coordinator_start_stop_calls_client(
    hass: HomeAssistant, auto_mock_sia_client_tcp: MagicMock
) -> None:
    """Test that async_start/async_stop proxy to the SIA client."""
    coordinator = PimaForceDataUpdateCoordinator(
        hass,
        MockConfigEntry(
            domain=DOMAIN,
            options={CONF_PORT: DEFAULT_LISTENING_PORT},
        ),
    )
    await coordinator.async_start()
    await coordinator.async_stop()

    auto_mock_sia_client_tcp.async_start.assert_awaited_once()
    auto_mock_sia_client_tcp.async_stop.assert_awaited_once()
