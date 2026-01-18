# Pima Force

[![HACS Badge](https://img.shields.io/badge/HACS-Default-31A9F4.svg?style=for-the-badge)](https://github.com/hacs/integration)

[![GitHub Release](https://img.shields.io/github/release/amitfin/pima_force.svg?style=for-the-badge&color=blue)](https://github.com/amitfin/pima_force/releases)

![Download](https://img.shields.io/github/downloads/amitfin/pima_force/total.svg?style=for-the-badge&color=blue) ![Analytics](https://img.shields.io/badge/dynamic/json?style=for-the-badge&color=blue&label=Analytics&suffix=%20Installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.pima_force.total)

![Project Maintenance](https://img.shields.io/badge/maintainer-Amit%20Finkelstein-blue.svg?style=for-the-badge)

***This integration is not affiliated with Pima.***

The integration creates `binary_sensor` entities for [Pima Force](https://www.pima-alarms.com/our-products/force-security-system/) alarm system zones. The sensors turn `on` when the zone is "open" (i.e., it causes the alarm to trigger when it is armed). This is a read-only integration and does not have the ability to control or change the alarm system. It reads [SIA events](https://www.securityindustry.org/industry-standards/dc-09-2021/) with [ADM-CID payload](https://www.securityindustry.org/industry-standards/dc-05-2016/) sent from the alarm. The integration does not require additional hardware.

Note: a guide to controlling Pima Force (outside of this read-only integration) is available [here](https://docs.google.com/document/d/14H0u2NchUvVmQAxFU8D5C2-KNui8gWwFPb2p-ZRuWFo).

## Install

HACS is the preferred and easiest way to install the component and can be done using this My button:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=amitfin&repository=pima_force&category=integration)

Otherwise, download `pima_force.zip` from the [latest release](https://github.com/amitfin/pima_force/releases), extract and copy the content under `custom_components` directory.

A Home Assistant restart is required once the integration files are copied (either by HACS or manually).

The integration should also be added to the configuration. This can be done using this My button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=pima_force)

There are 2 fields:
1. `Port`: the port to listen for incoming events. The default is `10001`, which is also the default port in the alarm. It should be kept as is unless there is a specific reason not to.
2. `Zone names`: an ordered list of zones that should be copied from the alarm's zone list. If a specific zone in the alarm is not used, there should be a corresponding empty item on the list. For example, if the alarm has 3 zones: "zone 1: door, zone 2: [not used], zone 3: window", the list should be "door, [empty], window".

After the component is installed, it can be reconfigured using the Configure dialog, which can be accessed via this My button:

[![Open your Home Assistant instance and show an integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=pima_force)

| <img width="396" height="429" alt="image" src="https://github.com/user-attachments/assets/f9b88109-ea7f-431e-a865-def673b9c813" /> |
| --- |

## Pima Force Setup

### Codes

There are 3 sets of codes:
1) Regular user code: the code to arm / disarm the system and configure basic settings (e.g. bypass zones).
2) Master user code: opens additional options in the user menu.
3) Master technician code: a different menu used by installers to set up the system.

This setup can be done only with the master technician code. User codes, either regular or master, are not enough. Please make sure you know the master technician code before proceeding. The rest of the instructions assume you entered the technician menu by entering the master technician code.

### Keyboard

The alarm's keypad has limited capabilities, so here are a few tips on how to use it:
- Press star (`*`) to change from capital letters to small letters and then to numbers (circular). Only numbers (and dots) will be used for this configuration.
- When entering numbers, pressing twice on the number one (`1`) produces a dot (`.`).
- Pressing twice on the hash key (`#`) clears the value.
- After changing a value, press enter (`⏎`) to exit (and not the back key `↺`).
- To save a changed configuration, press back (`↺`) multiple times until exiting from the main menu. The alarm will reboot.

### Monitoring Station

Home Assistant IP:port should be configured as a Central Monitoring Station (CMS) in the alarm's configuration. The alarm sends the events to its monitoring stations.

- `System Configuration => CMS & Communications => Monitoring Stations => CMS 1 => Communication Paths => Network (Ethernet) => Network Addresses`:
  - `IP 1`: enter Home Assistant's IP address, e.g. `192.168.1.100`.
  - `Port 1`: the port which is configured for the integration. The default port is the same in the alarm and the integration (`10001`) so there is no need to change it.
- `System Configuration => CMS & Communications => Monitoring Stations => CMS 1 => Communication Paths => Network (Ethernet) => Account IDs`:
  - `Partition 1`: enter a 6-character account ID. The actual value is ignored, but must be present. `111111` will do (or anything else).
- `System Configuration => CMS & Communications => Monitoring Stations => CMS 1 => Communication Paths => Network (Ethernet)`:
  - `Disable encryption`: this is not checked by default. Press enter (`⏎`) to disable encryption (which is not supported).
- `System Configuration => CMS & Communications => Monitoring Stations => CMS 1 => Event Reporting`:
  - `Zone/output Toggle`: this is not checked by default. Press enter (`⏎`) to set the alarm to send events on zone status changes. Without this option selected, the relevant events won't be sent and the integration will not be notified when a zone is opened or closed.

## Binary Sensors

The integration creates a binary sensor for each zone. It skips zones with an empty name (but it takes empty zones into account for numbering correctly the rest of the zones).

The `entity_id` has the format of `binary_sensor.pima_force_<port>_zone<#>`. For example: `binary_sensor.pima_force_10001_zone5`.

The default device class is `Door`, but it can be changed by [customizing the entity](https://www.home-assistant.io/docs/configuration/customizing-devices/).

Each sensor exposes attributes (timestamps are local time, ISO 8601):
- `zone`: zone number from the configured list.
- `last_set`: last time the zone state was set (including test services).
- `last_open`: last time the zone reported open.
- `last_close`: last time the zone reported closed.

The state is restored after Home Assistant restarts, but events that occur during downtime can be missed. For example, if a door opens while Home Assistant is rebooting, the sensor will still show "closed" (`off`) until the next change. Because the alarm only sends events on changes (not periodically), any mismatch is corrected the next time that zone reports a change.

## Dashboard

Here is an example of a markdown card which lists all zones sorted by their last status change:

```yaml
- title: Zone Status History
  type: markdown
  content: |
    | Zone | Set | Open | Closed |
    |------|-----|------|--------|
    {% for sensor in states.binary_sensor |
         selectattr('entity_id', 'in', integration_entities('pima_force')) |
         sort(attribute='attributes.friendly_name') |
         sort(attribute='attributes.last_set', reverse=True)
    -%}
    | {{ sensor.attributes.friendly_name.split()[2:] | join(' ') }} |
    {{- as_timestamp(sensor.attributes.last_set) | timestamp_custom('%H:%M:%S %d/%m/%y', true) }} |
    {{- (as_timestamp(sensor.attributes.last_open) | timestamp_custom('%H:%M:%S %d/%m/%y', true)) if sensor.attributes.last_open else '' }} |
    {{- as_timestamp(sensor.attributes.last_close) | timestamp_custom('%H:%M:%S %d/%m/%y', true) }} |
    {% endfor %}
```

| <img width="477" height="316" alt="image" src="https://github.com/user-attachments/assets/41395634-9b5a-47e2-abfd-8552c646a1aa" /> |
| --- |

## Automation

The sensors can be used also in automation rules. For example,

```yaml
alias: Safe is open
triggers:
  - trigger: state
    entity_id: binary_sensor.pima_force_10001_zone999  # safe's zone
    to: "on"
actions:
  - action: notify.mobile_app
    data:
      title: Alarm System
      message: Safe is open!
```

Another ideas can be:
- Turning on lights using motion sensors.
- Use motion sensors for presence (or absence) detection.
- Notify on door sensors, for example, when the backyard door (the pool area) is open.

## Services

The integration exposes services to read and update the configured zone names.
It also provides testing-only actions that can simulate zone state changes in Home Assistant.

### `pima_force.get_zones`

Returns the zone name list for a specific config entry. Empty items are preserved
to keep zone numbering aligned with the alarm. The response payload contains
`zones`, an ordered list of strings.

```yaml
service: pima_force.get_zones
data:
  config_entry_id: 1234567890abcdef1234567890abcdef
```

### `pima_force.set_zones`

Replaces the zone name list for a specific config entry. Provide an ordered list
of strings; use empty strings for unused zones.

```yaml
service: pima_force.set_zones
data:
  config_entry_id: 1234567890abcdef1234567890abcdef
  zones:
    - Front Door
    - ""
    - Back Door
```

### `pima_force.set_open` (testing only)

Marks a zone as open in Home Assistant without sending anything to the alarm system.
Use this only for testing automations and dashboards. The zone stays open until the alarm explicitly reports otherwise or `pima_force.set_closed` action is performed.

```yaml
service: pima_force.set_open
target:
  entity_id: binary_sensor.pima_force_10001_zone5
```

### `pima_force.set_closed` (testing only)

Marks a zone as closed in Home Assistant without sending anything to the alarm system.
Use this only for testing automations and dashboards. The zone stays closed until the alarm explicitly reports otherwise or `pima_force.set_open` action is performed.

```yaml
service: pima_force.set_closed
target:
  entity_id: binary_sensor.pima_force_10001_zone5
```

## Uninstall

1. **Delete the configuration:**
   - Open the integration page ([my-link](https://my.home-assistant.io/redirect/integration/?domain=pima_force)), click the 3‑dot menu (⋮), and select **Delete**.

2. **Remove the integration files:**
   - If the integration was installed via **HACS**, follow the [official HACS removal instructions](https://www.hacs.xyz/docs/use/repositories/dashboard/#removing-a-repository).
   - Otherwise, manually delete the integration’s folder `custom_components/pima_force`.

📌 A **Home Assistant core restart** is required in both cases to fully apply the removal.

## Contributions are welcome!

If you want to contribute to this, please read the [Contribution guidelines](CONTRIBUTING.md).
