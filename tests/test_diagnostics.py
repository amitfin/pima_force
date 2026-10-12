"""Tests for diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import CONF_NAME, CONF_PORT
from pysiaalarm.event import SIAEvent
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.pima_force.const import (
    ADM_CID_EVENT_QUALIFIER_OPEN,
    ADM_CID_PIMA_ZONE_STATUS_CODE,
    CONF_ZONES,
    DEFAULT_LISTENING_PORT,
    DOMAIN,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

# The diagnostics HTTP API warns when optional compression libraries are missing.
pytestmark = pytest.mark.allowed_logs(["zlib_ng"])

OPTIONS = {CONF_PORT: DEFAULT_LISTENING_PORT, CONF_ZONES: [{CONF_NAME: "Front Door"}]}


async def test_diagnostics_loaded(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    auto_mock_sia_client_tcp: MagicMock,
) -> None:
    """Test diagnostics of a loaded entry include the live state."""
    auto_mock_sia_client_tcp.server.is_serving.return_value = True
    config_entry = MockConfigEntry(domain=DOMAIN, options=OPTIONS)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data.coordinator
    await coordinator.process_event(
        SIAEvent(
            event_type=ADM_CID_PIMA_ZONE_STATUS_CODE,
            event_qualifier=ADM_CID_EVENT_QUALIFIER_OPEN,
            ri="001",
        )
    )

    assert coordinator.last_message is not None
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "state": "loaded",
        "options": OPTIONS,
        "listening": True,
        "last_message": coordinator.last_message.isoformat(),
        "zone_states": {"1": True},
    }


async def test_diagnostics_port_in_use(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    auto_mock_sia_client_tcp: MagicMock,
) -> None:
    """Test diagnostics of an entry waiting to retry show it isn't listening."""
    auto_mock_sia_client_tcp.async_start.side_effect = OSError
    auto_mock_sia_client_tcp.server = None
    config_entry = MockConfigEntry(domain=DOMAIN, options=OPTIONS)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "state": "setup_retry",
        "options": OPTIONS,
        "listening": False,
        "last_message": None,
        "zone_states": {},
    }


async def test_diagnostics_not_loaded(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test diagnostics of an entry that was never set up."""
    config_entry = MockConfigEntry(domain=DOMAIN, options=OPTIONS)
    config_entry.add_to_hass(hass)
    hass.config.components.add(DOMAIN)

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "state": "not_loaded",
        "options": OPTIONS,
    }
