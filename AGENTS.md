# AGENTS.md

Guidance for working in this repository.

## What this is

A Home Assistant custom integration (HACS) for Pima Force alarm panels. It is
**read-only**: it runs a SIA DC-09 TCP server (via `pysiaalarm`), receives
ADM-CID events the panel sends to its "monitoring station", and exposes one
`binary_sensor` per configured zone. It never sends anything to the panel
other than SIA ACKs.

- Minimum Home Assistant: **2026.10.0** (`hacs.json`). Schemas use `probatio`
  (HA's replacement for `voluptuous`); do not import `voluptuous`.
- Python 3.14, mypy `--strict`, ruff with `select = ["ALL"]`.

## Layout

```
custom_components/pima_force/
  __init__.py       setup/unload, runtime data, get_zones / set_zones actions
  coordinator.py    PimaForceDataUpdateCoordinator: owns the SIAClient, filters events, holds `zones`
  binary_sensor.py  PimaForceZoneBinarySensor, set_open / set_closed entity actions, zone_entity_id()
  entity.py         PimaForceEntity base (device info, has_entity_name)
  config_flow.py    user flow + options flow (port, ordered zone names, port-change confirmation)
  const.py          constants, including the ADM-CID codes
  services.yaml, icons.json, strings.json, translations/{en,he}.json
tests/              pytest + pytest-homeassistant-custom-component
scripts/            setup, lint, develop
config/             dev HA config (only configuration.yaml is tracked)
```

## Runtime flow

1. `async_setup` registers the domain actions `get_zones` and `set_zones`. Both
   raise `ServiceValidationError` (`invalid_config_entry`) unless the entry ID
   belongs to a `pima_force` entry.
2. `async_setup_entry` creates the coordinator (passing `config_entry`
   explicitly), stores it in `entry.runtime_data` (`PimaForceRuntimeData`),
   starts the SIA server, then forwards to the `binary_sensor` platform.
   - If the port can't be bound (`OSError`), it raises `ConfigEntryNotReady`
     (`cannot_listen`), so HA retries.
   - If forwarding the platforms fails, it stops the server before re-raising,
     because a failed setup is not unloaded.
3. `SIAClient` listens on `""` (all interfaces) at the configured port with a
   single wildcard account (`SIAAccount("")` matches any account ID), no
   encryption, and response qualifier `KC`.
4. `coordinator._handle_event` keeps only events with `event_type == "760"`,
   qualifier `"1"` (open) or `"3"` (close), and a numeric `ri`. It sets
   `zones[int(ri)]` and calls `async_update_listeners()`.
5. Platform setup removes registry entries of this config entry whose zone no
   longer has a name, then adds one entity per named zone.
6. Each sensor restores its last state, then applies any value already in
   `coordinator.zones`. The server starts before the platform, so events can
   arrive before the entity exists.
7. A sensor writes state **only when its zone's value changes**, and then
   updates `last_set` and either `last_open` or `last_close`
   (`_apply_zone_state`).
8. Any options change triggers a full entry reload through the update listener.
9. Unload unloads the platforms first, and stops the SIA server only if that
   succeeds.

The coordinator is a plain listener hub (`DataUpdateCoordinator[None]`): it has
no `update_method` and no `update_interval`, and `coordinator.data` is unused.
Zone state lives in `coordinator.zones`.

## Domain rules worth knowing

- **Zone numbering is positional.** The options store an ordered list
  `zones: [{"name": ...}, ...]`. List index + 1 is the alarm's zone number.
  Empty names are placeholders: they keep numbering aligned but create no
  entity.
- **Ports are unique per entry.** The value must be 1–65535 (`cv.port`). The
  user flow aborts with `already_configured`, and the options flow shows a
  field error, when another `pima_force` entry uses the port.
- **Entity IDs.** `unique_id` is `f"{entry_id}_{zone}"`. The `entity_id` is
  `zone_entity_id(port, zone)` = `binary_sensor.pima_force_<port>_zone<n>`, set
  on first registration; the registry keeps it afterwards.
  - A port change in the options flow shows a `confirm_port_change` step. The
    step names one example rename, and it is shown only when at least one entity
    still has the default ID for the old port.
  - On confirmation, those entities are renamed in the registry, and history
    follows. Customized entity IDs are never touched.
- `_attr_has_entity_name = True` with the device named "Pima Force", so friendly
  names are `"Pima Force <zone name>"`. The README templates rely on
  `.split()[2:]`.
- State and the timestamp attributes are restored with `RestoreEntity`. Events
  sent while HA is down are lost. The panel only reports changes, so a missed
  event is corrected at the zone's next change.
- All extra attributes are in `_unrecorded_attributes` (not written to the
  recorder).
- `set_open` / `set_closed` are testing aids. They mutate `coordinator.zones`
  directly and only affect HA.

## Commands

```bash
scripts/setup          # install deps (uv), pytest-homeassistant-custom-component, prek hooks
scripts/lint           # ruff format + ruff check --fix + mypy --strict
scripts/lint --no-fix  # CI mode
pytest                 # runs with --cov-fail-under=100 (pytest.ini)
scripts/develop        # run a dev HA instance on :8123 using ./config
```

Run `scripts/lint` and `pytest` after every change. Both also run as prek
pre-commit hooks and in CI (`.github/workflows/lint.yml`, `validate.yml`, which
also runs hassfest and HACS validation). Ruff also formats Python code blocks
inside Markdown files.

## Testing conventions

- **100% line coverage is enforced.** `.coveragerc` excludes only
  `if TYPE_CHECKING:`. A new branch needs a test.
- **Any WARNING or higher log fails the test** (hook in `tests/conftest.py`).
  For expected logs use `@pytest.mark.allowed_logs(["message prefix", ...])`.
- `SIAClient` is auto-mocked for every test (`auto_mock_sia_client_tcp`
  fixture), so no sockets are opened. Request the fixture to assert on
  `async_start` / `async_stop`. To exercise the coordinator callback, patch
  `custom_components.pima_force.coordinator.SIAClient` with a factory. The
  callback is the 4th constructor argument.
- Custom integrations are auto-enabled. Use `MockConfigEntry(domain=DOMAIN,
  options={CONF_PORT: ..., CONF_ZONES: [...]})`. All configuration lives in
  `options`; `data` is always `{}`.
- Use `freezer` for timestamps; `dt_util.now()` uses HA's configured time zone,
  not UTC. Use `monkeypatch` on `async_get_last_state`, or `mock_restore_cache`,
  for restore tests (see `tests/test_binary_sensor.py`).
- Prefer driving flows and actions through HA's real managers
  (`hass.config_entries.flow` / `.options`, `hass.services.async_call`) over
  calling handlers directly.

## Style

- ruff `ALL`, with ignores listed in `.ruff.toml`. Docstrings on everything,
  including tests. Multi-line docstrings put the summary on the second line.
- `from __future__ import annotations`, with type-only imports under
  `if TYPE_CHECKING:`. Relative imports inside the package.
- Name unused required parameters `_` instead of adding `noqa`.
- Keep `# type: ignore[...]` codes specific. mypy strict warns on unused
  ignores.
- Spell checking (cspell, `.cspell.json`) runs in CI over Markdown, code, and
  `translations/en.json`. Add domain words to `.cspell.json`.

## When changing user-facing text or actions

- Update `strings.json` **and** `translations/en.json` (keep them identical
  except for resolved `[%key:...]` references) **and** `translations/he.json`.
  Errors raised to users use translated exceptions (`exceptions` section).
- New actions need entries in `services.yaml`, `icons.json`, and the
  `services` section of the strings, plus a README section.
- Keep `README.md` in sync with behaviour (entity ID format, attributes,
  actions).

## Release

Publishing a GitHub release runs `.github/workflows/release.yml`. It writes the
tag into `manifest.json` `version`, zips `custom_components/pima_force`, and
attaches `pima_force.zip`, which HACS installs (`zip_release: true`). Do not
bump `manifest.json` `version` by hand. When raising the minimum HA version,
update `hacs.json`.
