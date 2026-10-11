"""Diagnostics support for Pima Force."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import PimaForceConfigEntry


async def async_get_config_entry_diagnostics(
    _: HomeAssistant, entry: PimaForceConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: dict[str, Any] = {"state": entry.state.value, "options": dict(entry.options)}
    if (runtime_data := getattr(entry, "runtime_data", None)) is not None:
        data["listening"] = runtime_data.coordinator.listening
        data["zone_states"] = runtime_data.coordinator.zones
    return data
