"""Constants for the pima_force integration."""

import logging
from typing import Final

DOMAIN: Final = "pima_force"
TITLE: Final = "Pima Force"
LOGGER = logging.getLogger(__package__)

DEFAULT_LISTENING_PORT: Final = 10001
CONF_ZONES: Final = "zones"

DEVICE_MANUFACTURER: Final = "Pima"
DEVICE_MODEL: Final = "Force"

ATTR_LAST_OPEN: Final = "last_open"
ATTR_LAST_CLOSE: Final = "last_close"
ATTR_LAST_TOGGLE: Final = "last_toggle"
ATTR_ZONE: Final = "zone"

SIA_PIMA_KEEP_CONNECTED_QUALIFIER: Final = "KC"
ADM_CID_PIMA_ZONE_STATUS_CODE: Final = "760"
ADM_CID_EVENT_QUALIFIER_OPEN: Final = "1"
ADM_CID_EVENT_QUALIFIER_CLOSE: Final = "3"
