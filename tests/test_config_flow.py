"""Tests for the config flow."""

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType, InvalidData
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
