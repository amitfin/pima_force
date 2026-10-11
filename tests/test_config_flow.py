"""Tests for the config flow."""

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pima_force.config_flow import (
    OptionsFlowHandler,
    PimaForceConfigFlow,
)
from custom_components.pima_force.const import (
    CONF_ZONES,
    DEFAULT_LISTENING_PORT,
    DOMAIN,
    TITLE,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant


def _zones() -> list[dict[str, str]]:
    return [{CONF_NAME: "Front Door"}]


def _schema_default(schema: Any, key: str) -> Any:
    for marker in schema.schema:
        if getattr(marker, "schema", marker) == key:
            default = marker.default
            return default() if callable(default) else default
    raise AssertionError


async def test_flow_user_form(hass: HomeAssistant) -> None:
    """Test the user form flow and creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result.get("type") == FlowResultType.FORM


async def test_flow_user_creates_entry(hass: HomeAssistant) -> None:
    """Test user flow creates an entry with options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: DEFAULT_LISTENING_PORT, CONF_ZONES: _zones()},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == f"{TITLE} {DEFAULT_LISTENING_PORT}"
    assert result.get("data") == {}
    assert result.get("options") == {
        CONF_PORT: DEFAULT_LISTENING_PORT,
        CONF_ZONES: _zones(),
    }


async def test_async_get_options_flow() -> None:
    """Test config flow exposes an options flow handler."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    handler = PimaForceConfigFlow.async_get_options_flow(config_entry)

    assert isinstance(handler, OptionsFlowHandler)


async def test_options_flow_updates_port(hass: HomeAssistant) -> None:
    """Test the options flow updates the listening port."""
    zones = _zones()
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: 5000, CONF_ZONES: zones},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert _schema_default(result.get("data_schema"), CONF_PORT) == 5000
    assert _schema_default(result.get("data_schema"), CONF_ZONES) == zones

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: 6000},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_PORT: 6000, CONF_ZONES: zones}
    assert config_entry.title == f"{TITLE} 6000"


async def test_flow_user_aborts_on_duplicate_port(hass: HomeAssistant) -> None:
    """Test the user flow aborts when the port is already used by an entry."""
    MockConfigEntry(
        domain=DOMAIN, options={CONF_PORT: DEFAULT_LISTENING_PORT}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: DEFAULT_LISTENING_PORT, CONF_ZONES: _zones()},
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_options_flow_rejects_port_of_other_entry(hass: HomeAssistant) -> None:
    """Test the options flow rejects a port used by another entry."""
    MockConfigEntry(domain=DOMAIN, options={CONF_PORT: 5000}).add_to_hass(hass)
    zones = _zones()
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{TITLE} 6000",
        options={CONF_PORT: 6000, CONF_ZONES: zones},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    new_zones = [{CONF_NAME: "Back Door"}]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: 5000, CONF_ZONES: new_zones},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {CONF_PORT: "already_configured"}
    assert _schema_default(result.get("data_schema"), CONF_PORT) == 5000
    assert _schema_default(result.get("data_schema"), CONF_ZONES) == new_zones
    assert config_entry.options == {CONF_PORT: 6000, CONF_ZONES: zones}
    assert config_entry.title == f"{TITLE} 6000"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: 6000, CONF_ZONES: new_zones},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_PORT: 6000, CONF_ZONES: new_zones}


@pytest.mark.parametrize("port", [0, 65536])
async def test_flows_reject_invalid_port(hass: HomeAssistant, port: int) -> None:
    """Test the user and options flows reject ports outside 1-65535."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with pytest.raises(InvalidData) as err:
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PORT: port}
        )
    assert err.value.schema_errors == {
        CONF_PORT: "expected a port number between 1 and 65535"
    }

    config_entry = MockConfigEntry(domain=DOMAIN, options={CONF_PORT: 5000})
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_PORT: port}
        )
    assert config_entry.options == {CONF_PORT: 5000}


async def _setup_entry_with_zones(
    hass: HomeAssistant, zones: list[dict[str, str]]
) -> MockConfigEntry:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{TITLE} 10001",
        options={CONF_PORT: 10001, CONF_ZONES: zones},
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def test_options_flow_port_change_renames_entities(
    hass: HomeAssistant, auto_mock_sia_client_tcp: MagicMock
) -> None:
    """Test a confirmed port change renames default entity IDs only."""
    config_entry = await _setup_entry_with_zones(
        hass,
        [{CONF_NAME: "Front Door"}, {CONF_NAME: "Back Door"}, {CONF_NAME: "Garage"}],
    )
    registry = er.async_get(hass)
    registry.async_update_entity(
        "binary_sensor.pima_force_10001_zone2",
        new_entity_id="binary_sensor.back_door",
    )
    await hass.async_block_till_done()
    new_zones = [{CONF_NAME: ""}, {CONF_NAME: "Back Door"}, {CONF_NAME: "Garage"}]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_PORT: 10002, CONF_ZONES: new_zones}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "confirm_port_change"
    assert result.get("description_placeholders") == {
        "old_port": "10001",
        "new_port": "10002",
        "name": "Garage",
        "old_entity_id": "binary_sensor.pima_force_10001_zone3",
        "new_entity_id": "binary_sensor.pima_force_10002_zone3",
    }
    assert config_entry.options[CONF_PORT] == 10001

    auto_mock_sia_client_tcp.async_start.reset_mock()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    auto_mock_sia_client_tcp.async_start.assert_awaited_once()
    assert config_entry.options == {CONF_PORT: 10002, CONF_ZONES: new_zones}
    assert config_entry.title == f"{TITLE} 10002"
    assert sorted(
        entity.entity_id
        for entity in er.async_entries_for_config_entry(registry, config_entry.entry_id)
    ) == ["binary_sensor.back_door", "binary_sensor.pima_force_10002_zone3"]
    state = hass.states.get("binary_sensor.pima_force_10002_zone3")
    assert state is not None
    assert state.name == "Pima Force Garage"
    assert hass.states.get("binary_sensor.pima_force_10001_zone3") is None


async def test_options_flow_port_change_closed_dialog(hass: HomeAssistant) -> None:
    """Test closing the confirmation dialog keeps the port and entity IDs."""
    config_entry = await _setup_entry_with_zones(hass, [{CONF_NAME: "Front Door"}])

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_PORT: 10002}
    )
    assert result.get("step_id") == "confirm_port_change"
    hass.config_entries.options.async_abort(result["flow_id"])
    await hass.async_block_till_done()

    assert config_entry.options[CONF_PORT] == 10001
    assert config_entry.title == f"{TITLE} 10001"
    assert er.async_get(hass).async_get("binary_sensor.pima_force_10001_zone1")


async def test_options_flow_port_change_without_renames(
    hass: HomeAssistant, auto_mock_sia_client_tcp: MagicMock
) -> None:
    """Test a port change saves directly when no entity ID would change."""
    config_entry = await _setup_entry_with_zones(hass, [{CONF_NAME: "Front Door"}])
    er.async_get(hass).async_update_entity(
        "binary_sensor.pima_force_10001_zone1",
        new_entity_id="binary_sensor.front_door",
    )
    await hass.async_block_till_done()
    auto_mock_sia_client_tcp.async_start.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_PORT: 10002}
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_PORT] == 10002
    assert config_entry.title == f"{TITLE} 10002"
    assert er.async_get(hass).async_get("binary_sensor.front_door")
    # The title and the options are saved together, so it's reloaded once.
    auto_mock_sia_client_tcp.async_start.assert_awaited_once()


async def test_options_flow_same_port_keeps_title(hass: HomeAssistant) -> None:
    """Test changing only the zones keeps the port and the title."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{TITLE} 5000",
        options={CONF_PORT: 5000, CONF_ZONES: _zones()},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    new_zones = [{CONF_NAME: "Front Door"}, {CONF_NAME: "Back Door"}]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_PORT: 5000, CONF_ZONES: new_zones}
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_PORT: 5000, CONF_ZONES: new_zones}
    assert config_entry.title == f"{TITLE} 5000"
