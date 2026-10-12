"""DataUpdateCoordinator for pima_force integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_PORT
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
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
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from pysiaalarm.event import SIAEvent

    from . import PimaForceConfigEntry

NO_MESSAGES_TIMEOUT = timedelta(minutes=30)
ISSUE_NO_MESSAGES = "no_messages"


class PimaForceDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage Pima Force data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PimaForceConfigEntry,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(hass, LOGGER, config_entry=config_entry, name=DOMAIN)
        self.zones: dict[int, bool] = {}  # zone number -> open state
        self._last_message: datetime | None = None
        self._port: int = config_entry.options[CONF_PORT]
        self._issue_id = f"{ISSUE_NO_MESSAGES}_{config_entry.entry_id}"
        self._cancel_watchdog: CALLBACK_TYPE | None = None
        self._sia_client = SIAClient(  # type: ignore[abstract]
            "",
            self._port,
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
        """Process a message from the panel, including keep-alives."""
        self._last_message = dt_util.utcnow()
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
        if self._cancel_watchdog is not None:
            self._async_start_watchdog()
        self._handle_event(event)

    @callback
    def _async_start_watchdog(self) -> None:
        """Raise an issue if no message (including keep-alive) arrives in time."""
        self._async_cancel_watchdog()
        self._cancel_watchdog = async_call_later(
            self.hass, NO_MESSAGES_TIMEOUT, self._async_no_messages
        )

    @callback
    def _async_cancel_watchdog(self) -> None:
        """Cancel the no-messages timer."""
        if self._cancel_watchdog is not None:
            self._cancel_watchdog()
            self._cancel_watchdog = None

    @callback
    def _async_no_messages(self, _: datetime) -> None:
        """Raise the no-messages issue."""
        silence = (
            dt_util.utcnow() - self._last_message
            if self._last_message
            else NO_MESSAGES_TIMEOUT
        )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            learn_more_url="https://github.com/amitfin/pima_force#monitoring-station",
            translation_key=ISSUE_NO_MESSAGES,
            translation_placeholders={
                "port": str(self._port),
                "minutes": str(int(silence.total_seconds() // 60)),
            },
        )

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

    @property
    def last_message(self) -> datetime | None:
        """Return when the last message (including keep-alive) was received."""
        return self._last_message

    @property
    def listening(self) -> bool:
        """Return whether the SIA server is accepting connections."""
        server = getattr(self._sia_client, "server", None)
        return server is not None and bool(server.is_serving())

    async def async_start(self) -> None:
        """Start the SIA server."""
        await self._sia_client.async_start()
        self._async_start_watchdog()

    async def async_stop(self) -> None:
        """Shutdown the SIA server."""
        # pysiaalarm waits for open connections, such as the panel's, to close.
        if (server := getattr(self._sia_client, "server", None)) is not None:
            server.close_clients()
        await self._sia_client.async_stop()
        self._async_cancel_watchdog()
