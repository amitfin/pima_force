"""Tests for the binary sensor platform."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pima_force import PimaForceRuntimeData
from custom_components.pima_force.binary_sensor import PimaForceZoneBinarySensor
from custom_components.pima_force.const import (
    ATTR_LAST_CLOSE,
    ATTR_LAST_OPEN,
    ATTR_LAST_TOGGLE,
    ATTR_ZONE,
    CONF_ZONES,
    DEFAULT_LISTENING_PORT,
    DOMAIN,
    SERVICE_SET_CLOSED,
    SERVICE_SET_OPEN,
)
from custom_components.pima_force.coordinator import PimaForceDataUpdateCoordinator

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant


async def _setup_entities(
    hass: HomeAssistant, entry_id: str, zones: list[dict[str, str]]
) -> list[er.RegistryEntry]:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=entry_id,
        options={CONF_PORT: DEFAULT_LISTENING_PORT, CONF_ZONES: zones},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    return [
        entry
        for entry in registry.entities.values()
        if entry.config_entry_id == entry_id
    ]


def _sorted_entities(entries: list[er.RegistryEntry]) -> list[er.RegistryEntry]:
    return sorted(entries, key=lambda entry: int(entry.unique_id.split("_")[-1]))


def _stored_state(entity_id: str, state: str) -> State:
    return State(entity_id, state)


def _stored_state_with_attrs(
    entity_id: str, state: str, attributes: dict[str, str | None]
) -> State:
    return State(entity_id, state, attributes=attributes)


async def test_async_setup_entry_adds_named_zones(hass: HomeAssistant) -> None:
    """Test entities are created only for zones with names."""
    entry_id = "test_entry"
    entities = _sorted_entities(
        await _setup_entities(
            hass,
            entry_id,
            [
                {CONF_NAME: ""},
                {CONF_NAME: "Front Door"},
                {CONF_NAME: "Back Door"},
            ],
        )
    )

    assert [entry.entity_id for entry in entities] == [
        f"binary_sensor.{DOMAIN}_{DEFAULT_LISTENING_PORT}_zone2",
        f"binary_sensor.{DOMAIN}_{DEFAULT_LISTENING_PORT}_zone3",
    ]
    assert [entry.unique_id for entry in entities] == [
        f"{entry_id}_2",
        f"{entry_id}_3",
    ]
    assert [entry.original_name for entry in entities] == [
        "Front Door",
        "Back Door",
    ]


async def test_is_on_prefers_live_zone_state(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test live zone values override restored state."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    coordinator = PimaForceDataUpdateCoordinator(hass, config_entry)
    config_entry.runtime_data = PimaForceRuntimeData(coordinator)

    sensor = PimaForceZoneBinarySensor(config_entry, 1, "Front Door")
    sensor.hass = hass
    coordinator.zones[1] = False
    monkeypatch.setattr(
        sensor,
        "async_get_last_state",
        AsyncMock(return_value=_stored_state("binary_sensor.front_door", STATE_ON)),
    )
    write_state = MagicMock()
    monkeypatch.setattr(sensor, "async_write_ha_state", write_state)

    await sensor.async_added_to_hass()
    coordinator.async_update_listeners()

    assert sensor.is_on is False


@pytest.mark.parametrize(
    ("restored_state", "expected"), [(STATE_ON, True), (STATE_OFF, False)]
)
async def test_is_on_uses_restored_state(
    hass: HomeAssistant,
    restored_state: str,
    *,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test restored state is used when no live zone data exists."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    config_entry.runtime_data = PimaForceRuntimeData(
        PimaForceDataUpdateCoordinator(hass, config_entry)
    )

    sensor = PimaForceZoneBinarySensor(config_entry, 2, "Back Door")
    monkeypatch.setattr(
        sensor,
        "async_get_last_state",
        AsyncMock(
            return_value=_stored_state("binary_sensor.back_door", restored_state)
        ),
    )

    await sensor.async_added_to_hass()

    assert sensor.is_on is expected


async def test_is_on_defaults_off(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test default state is off with no data."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    config_entry.runtime_data = PimaForceRuntimeData(
        PimaForceDataUpdateCoordinator(hass, config_entry)
    )

    sensor = PimaForceZoneBinarySensor(config_entry, 3, "Garage")
    monkeypatch.setattr(sensor, "async_get_last_state", AsyncMock(return_value=None))

    await sensor.async_added_to_hass()

    assert sensor.is_on is False


async def test_handle_update_skips_missing_zone(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test coordinator updates are ignored when zone data is missing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    coordinator = PimaForceDataUpdateCoordinator(hass, config_entry)
    config_entry.runtime_data = PimaForceRuntimeData(coordinator)

    sensor = PimaForceZoneBinarySensor(config_entry, 4, "Office")
    sensor.hass = hass
    monkeypatch.setattr(sensor, "async_get_last_state", AsyncMock(return_value=None))
    write_state = MagicMock()
    monkeypatch.setattr(sensor, "async_write_ha_state", write_state)

    await sensor.async_added_to_hass()
    coordinator.async_update_listeners()

    write_state.assert_not_called()


async def test_handle_update_skips_unchanged_state(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test coordinator updates are ignored when state is unchanged."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    coordinator = PimaForceDataUpdateCoordinator(hass, config_entry)
    config_entry.runtime_data = PimaForceRuntimeData(coordinator)

    sensor = PimaForceZoneBinarySensor(config_entry, 5, "Kitchen")
    sensor.hass = hass
    coordinator.zones[5] = True
    monkeypatch.setattr(
        sensor,
        "async_get_last_state",
        AsyncMock(
            return_value=_stored_state_with_attrs(
                "binary_sensor.kitchen",
                STATE_ON,
                {
                    ATTR_LAST_OPEN: "2024-01-01T00:00:00+00:00",
                    ATTR_LAST_CLOSE: None,
                    ATTR_LAST_TOGGLE: "2024-01-01T00:00:00+00:00",
                },
            )
        ),
    )
    write_state = MagicMock()
    monkeypatch.setattr(sensor, "async_write_ha_state", write_state)

    await sensor.async_added_to_hass()
    coordinator.async_update_listeners()

    write_state.assert_not_called()


async def test_handle_update_sets_timestamps_when_last_toggle_missing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test timestamps are updated when last toggle is missing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    coordinator = PimaForceDataUpdateCoordinator(hass, config_entry)
    config_entry.runtime_data = PimaForceRuntimeData(coordinator)

    sensor = PimaForceZoneBinarySensor(config_entry, 5, "Kitchen")
    sensor.hass = hass
    coordinator.zones[5] = True
    monkeypatch.setattr(
        sensor,
        "async_get_last_state",
        AsyncMock(
            return_value=_stored_state_with_attrs("binary_sensor.kitchen", STATE_ON, {})
        ),
    )
    write_state = MagicMock()
    monkeypatch.setattr(sensor, "async_write_ha_state", write_state)

    await sensor.async_added_to_hass()

    old_tz = dt_util.DEFAULT_TIME_ZONE
    dt_util.set_default_time_zone(dt_util.UTC)
    try:
        freezer.move_to(datetime(2024, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC))
        coordinator.async_update_listeners()
    finally:
        dt_util.set_default_time_zone(old_tz)

    write_state.assert_called_once()
    assert sensor.extra_state_attributes == {
        ATTR_LAST_OPEN: "2024-01-01T00:00:00+00:00",
        ATTR_LAST_CLOSE: None,
        ATTR_LAST_TOGGLE: "2024-01-01T00:00:00+00:00",
        ATTR_ZONE: 5,
    }


async def test_handle_update_sets_timestamps(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test timestamp attributes are updated on state changes."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    coordinator = PimaForceDataUpdateCoordinator(hass, config_entry)
    config_entry.runtime_data = PimaForceRuntimeData(coordinator)

    sensor = PimaForceZoneBinarySensor(config_entry, 6, "Basement")
    sensor.hass = hass
    monkeypatch.setattr(sensor, "async_get_last_state", AsyncMock(return_value=None))
    monkeypatch.setattr(sensor, "async_write_ha_state", MagicMock())

    await sensor.async_added_to_hass()

    tz = dt_util.get_time_zone("America/New_York")
    assert tz is not None
    old_tz = dt_util.DEFAULT_TIME_ZONE
    dt_util.set_default_time_zone(tz)
    try:
        freezer.move_to(datetime(2024, 1, 1, 0, 0, 0, tzinfo=tz))
        coordinator.zones[6] = True
        coordinator.async_update_listeners()

        assert sensor.extra_state_attributes == {
            ATTR_LAST_OPEN: "2024-01-01T00:00:00-05:00",
            ATTR_LAST_CLOSE: None,
            ATTR_LAST_TOGGLE: "2024-01-01T00:00:00-05:00",
            ATTR_ZONE: 6,
        }

        freezer.move_to(datetime(2024, 1, 1, 0, 10, 0, tzinfo=tz))
        coordinator.zones[6] = False
        coordinator.async_update_listeners()

        assert sensor.extra_state_attributes == {
            ATTR_LAST_OPEN: "2024-01-01T00:00:00-05:00",
            ATTR_LAST_CLOSE: "2024-01-01T00:10:00-05:00",
            ATTR_LAST_TOGGLE: "2024-01-01T00:10:00-05:00",
            ATTR_ZONE: 6,
        }
    finally:
        dt_util.set_default_time_zone(old_tz)


async def test_restores_timestamp_attributes(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test timestamp attributes are restored from stored state."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_PORT: DEFAULT_LISTENING_PORT},
    )
    config_entry.runtime_data = PimaForceRuntimeData(
        PimaForceDataUpdateCoordinator(hass, config_entry)
    )

    sensor = PimaForceZoneBinarySensor(config_entry, 7, "Side Door")
    monkeypatch.setattr(
        sensor,
        "async_get_last_state",
        AsyncMock(
            return_value=_stored_state_with_attrs(
                "binary_sensor.side_door",
                STATE_ON,
                {
                    ATTR_LAST_OPEN: "2024-01-01T01:00:00+00:00",
                    ATTR_LAST_CLOSE: "2023-12-31T23:00:00+00:00",
                    ATTR_LAST_TOGGLE: "2024-01-01T01:00:00+00:00",
                },
            )
        ),
    )

    await sensor.async_added_to_hass()

    assert sensor.extra_state_attributes == {
        ATTR_LAST_OPEN: "2024-01-01T01:00:00+00:00",
        ATTR_LAST_CLOSE: "2023-12-31T23:00:00+00:00",
        ATTR_LAST_TOGGLE: "2024-01-01T01:00:00+00:00",
        ATTR_ZONE: 7,
    }


def _zone_unique_ids(entry_id: str, zones: list[int]) -> list[str]:
    return [f"{entry_id}_{zone}" for zone in zones]


async def test_async_setup_entry_handles_zone_option_changes(
    hass: HomeAssistant,
) -> None:
    """Test zone additions, removals, renames, and reorders."""
    entry_id = "test_entry"
    entities = _sorted_entities(
        await _setup_entities(
            hass,
            entry_id,
            [
                {CONF_NAME: "Front Door"},
                {CONF_NAME: "Back Door"},
                {CONF_NAME: "Garage"},
            ],
        )
    )
    assert [entry.original_name for entry in entities] == [
        "Front Door",
        "Back Door",
        "Garage",
    ]
    assert [entry.unique_id for entry in entities] == _zone_unique_ids(
        entry_id, [1, 2, 3]
    )

    entry_id = "test_entry_2"
    entities = _sorted_entities(
        await _setup_entities(
            hass,
            entry_id,
            [
                {CONF_NAME: "Front Door"},
                {CONF_NAME: "Back Door"},
                {CONF_NAME: "Garage"},
                {CONF_NAME: "Office"},
                {CONF_NAME: "Patio"},
            ],
        )
    )
    assert [entry.original_name for entry in entities] == [
        "Front Door",
        "Back Door",
        "Garage",
        "Office",
        "Patio",
    ]
    assert [entry.unique_id for entry in entities] == _zone_unique_ids(
        entry_id, [1, 2, 3, 4, 5]
    )

    entry_id = "test_entry_3"
    entities = _sorted_entities(
        await _setup_entities(
            hass,
            entry_id,
            [
                {CONF_NAME: "Front Door"},
                {CONF_NAME: ""},
                {CONF_NAME: "Garage"},
                {CONF_NAME: ""},
                {CONF_NAME: "Patio"},
            ],
        )
    )
    assert [entry.original_name for entry in entities] == [
        "Front Door",
        "Garage",
        "Patio",
    ]
    assert [entry.unique_id for entry in entities] == _zone_unique_ids(
        entry_id, [1, 3, 5]
    )

    entry_id = "test_entry_4"
    entities = _sorted_entities(
        await _setup_entities(
            hass,
            entry_id,
            [
                {CONF_NAME: "Front Entry"},
                {CONF_NAME: ""},
                {CONF_NAME: "Garage Bay"},
                {CONF_NAME: ""},
                {CONF_NAME: "Patio Door"},
            ],
        )
    )
    assert [entry.original_name for entry in entities] == [
        "Front Entry",
        "Garage Bay",
        "Patio Door",
    ]
    assert [entry.unique_id for entry in entities] == _zone_unique_ids(
        entry_id, [1, 3, 5]
    )

    entry_id = "test_entry_5"
    entities = _sorted_entities(
        await _setup_entities(
            hass,
            entry_id,
            [
                {CONF_NAME: "Patio Door"},
                {CONF_NAME: ""},
                {CONF_NAME: "Front Entry"},
                {CONF_NAME: ""},
                {CONF_NAME: "Garage Bay"},
            ],
        )
    )
    assert [entry.original_name for entry in entities] == [
        "Patio Door",
        "Front Entry",
        "Garage Bay",
    ]
    assert [entry.unique_id for entry in entities] == _zone_unique_ids(
        entry_id, [1, 3, 5]
    )


async def test_entity_services_update_zone_state(hass: HomeAssistant) -> None:
    """Test entity services update zone states."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_PORT: DEFAULT_LISTENING_PORT,
            CONF_ZONES: [{CONF_NAME: "Front Door"}],
        },
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"binary_sensor.{DOMAIN}_{DEFAULT_LISTENING_PORT}_zone1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_OPEN,
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CLOSED,
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
