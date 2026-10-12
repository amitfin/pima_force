"""Tests for the coordinator."""

import asyncio
import socket
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from homeassistant.const import CONF_PORT
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pysiaalarm.aio.client import SIAClient
from pysiaalarm.event import SIAEvent
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.pima_force.const import (
    ADM_CID_EVENT_QUALIFIER_CLOSE,
    ADM_CID_EVENT_QUALIFIER_OPEN,
    ADM_CID_PIMA_ZONE_STATUS_CODE,
    DEFAULT_LISTENING_PORT,
    DOMAIN,
)
from custom_components.pima_force.coordinator import PimaForceDataUpdateCoordinator

# A keep-alive (SIA NULL message) as received from a Pima Force panel.
KEEP_ALIVE_LINE = 'B46F002B"NULL"1632R1L0#AAAAAA[]_17:40:34,10-11-2026'

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
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
    for ri in (None, "", "abc"):
        await coordinator.process_event(
            SIAEvent(
                event_type=ADM_CID_PIMA_ZONE_STATUS_CODE,
                event_qualifier=ADM_CID_EVENT_QUALIFIER_OPEN,
                ri=ri,
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
    auto_mock_sia_client_tcp.server.close_clients.assert_called_once()
    auto_mock_sia_client_tcp.async_stop.assert_awaited_once()


@pytest.mark.usefixtures("socket_enabled")
async def test_coordinator_stop_with_open_connection(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a real SIA server stops while the panel's connection is open."""
    monkeypatch.setattr("custom_components.pima_force.coordinator.SIAClient", SIAClient)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    coordinator = PimaForceDataUpdateCoordinator(
        hass, MockConfigEntry(domain=DOMAIN, options={CONF_PORT: port})
    )
    coordinator.async_update_listeners = MagicMock()
    assert not coordinator.listening
    await coordinator.async_start()
    assert coordinator.listening

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        b'\n9A940041"ADM-CID"0141R1L0#AAAAAA[#AAAAAA|1760 01 032]_17:04:37,02-12-2026\r'
    )
    await writer.drain()
    assert b'"ACK"' in await asyncio.wait_for(reader.readuntil(b"\r"), 5)
    assert coordinator.zones == {32: True}

    await asyncio.wait_for(coordinator.async_stop(), 5)
    assert not coordinator.listening
    assert await asyncio.wait_for(reader.read(), 5) == b""
    # Stopping again (e.g. unload after Home Assistant stopped) is a no-op.
    await asyncio.wait_for(coordinator.async_stop(), 5)
    writer.close()


async def test_coordinator_config_entry(hass: HomeAssistant) -> None:
    """Test the coordinator is bound to its config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    coordinator = PimaForceDataUpdateCoordinator(hass, config_entry)

    assert coordinator.config_entry is config_entry


async def test_no_messages_issue(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a repair issue is raised after 30 minutes without any message."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_PORT: DEFAULT_LISTENING_PORT}
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data.coordinator
    issue_registry = ir.async_get(hass)
    issue_id = f"no_messages_{config_entry.entry_id}"

    async def advance(minutes: int) -> None:
        freezer.tick(timedelta(minutes=minutes))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    await advance(29)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    await advance(1)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "no_messages"
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {
        "port": str(DEFAULT_LISTENING_PORT),
        "minutes": "30",
    }

    await coordinator.process_event(SIAEvent.from_line(KEEP_ALIVE_LINE))
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert coordinator.last_message == dt_util.utcnow()
    assert coordinator.zones == {}

    await advance(20)
    await coordinator.process_event(SIAEvent.from_line(KEEP_ALIVE_LINE))
    await advance(20)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    await advance(10)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders == {
        "port": str(DEFAULT_LISTENING_PORT),
        "minutes": "30",
    }

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
    # A message processed after the server stopped doesn't start a new timer.
    await coordinator.process_event(SIAEvent.from_line(KEEP_ALIVE_LINE))
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    await advance(60)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
