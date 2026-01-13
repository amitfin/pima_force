"""DataUpdateCoordinator for pima_force integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pysiaalarm.account import SIAAccount
from pysiaalarm.aio.client import SIAClient

from .const import (
    ADM_CID_EVENT_QUALIFIER_CLOSE,
    ADM_CID_EVENT_QUALIFIER_OPEN,
    ADM_CID_PIMA_ZONE_STATUS_CODE,
    DOMAIN,
    LOGGER,
    SIA_PIMA_KEEP_CONNECTED_QUALIFIER,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pysiaalarm.event import SIAEvent

    from . import PimaForceConfigEntry


class PimaForceDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage Pima Force data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PimaForceConfigEntry,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(hass, LOGGER, name=DOMAIN)
        self._config_entry = config_entry
        self.zones: dict[int, bool] = {}  # zone number -> open state
        self._sia_client = SIAClient(  # type: ignore[abstract]
            "",
            config_entry.options[CONF_PORT],
            [
                SIAAccount(
                    "",
                    allowed_timeband=None,
                    response_qualifier=SIA_PIMA_KEEP_CONNECTED_QUALIFIER,
                )
            ],
            self.process_event,
        )  # pyright: ignore[reportAbstractUsage]

    async def process_event(self, event: SIAEvent) -> None:
        """Process new SIA ADM-CID event."""
        self._handle_event(event)

    @callback
    def _handle_event(self, event: SIAEvent) -> None:
        """Handle a parsed SIA ADM-CID event."""
        if (
            event.event_type != ADM_CID_PIMA_ZONE_STATUS_CODE
            or event.event_qualifier
            not in (
                ADM_CID_EVENT_QUALIFIER_OPEN,
                ADM_CID_EVENT_QUALIFIER_CLOSE,
            )
            or not event.ri
            or not event.ri.isdigit()
        ):
            return

        self.zones[int(event.ri)] = (
            event.event_qualifier == ADM_CID_EVENT_QUALIFIER_OPEN
        )
        self.async_update_listeners()

    async def async_start(self) -> None:
        """Start the SIA server."""
        await self._sia_client.async_start()

    async def async_stop(self) -> None:
        """Shutdown the SIA server."""
        await self._sia_client.async_stop()
