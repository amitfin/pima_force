# Project Context (pima_force)

## Overview
- Home Assistant custom integration for Pima Force alarm systems.
- Read-only: listens for SIA ADM-CID events and exposes one `binary_sensor` per zone.
- Default listening port is `10001`, configured via config flow options.
- Entities are created only for zones with non-empty names.

## Core Runtime Flow
- `custom_components/pima_force/__init__.py` sets up a `PimaForceDataUpdateCoordinator`, starts it, and forwards setup to the binary sensor platform.
- `custom_components/pima_force/coordinator.py` starts a `pysiaalarm` SIA server and updates `zones` (zone number -> open state) when matching events arrive.
- `custom_components/pima_force/binary_sensor.py` creates `PimaForceZoneBinarySensor` entities, restores last state, and updates state only when coordinator data changes.
- `custom_components/pima_force/entity.py` provides device info shared by all entities.

## Config Flow and Options
- `custom_components/pima_force/config_flow.py` defines a user flow and options flow for port and ordered zone names.
- `custom_components/pima_force/strings.json` and translations in `custom_components/pima_force/translations/` provide UI text.

## Tests
- Tests target 100% coverage and fail on warnings by default (`tests/conftest.py`).
- Key tests:
  - `tests/test_binary_sensor.py` validates sensor creation and state updates.
  - `tests/test_coordinator.py` validates event parsing and client lifecycle.
  - `tests/test_config_flow.py` validates config/options flows.
  - `tests/test_init.py` validates setup/unload lifecycle.

## Tooling and Scripts
- Lint/format/type-check: `scripts/lint` (ruff format/check + mypy strict).
- Dependencies: `scripts/setup` installs runtime deps (uses `uv`).
- Dev run: `scripts/develop` starts Home Assistant using the local `custom_components` path.

## Keep In Mind
- Entity IDs are explicitly set to `binary_sensor.pima_force_<port>_zone<#>` for user-friendly naming.
- SIA events are filtered to Pima zone status codes before updating coordinator state.
- Run `scripts/lint` and `pytest` after every change to avoid regressions.
