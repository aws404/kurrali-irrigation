"""Update coordinators for rainbird."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime as dt
import logging
from typing import TypeVar

import async_timeout
from pyrainbird.async_client import RainbirdApiException, AsyncRainbirdController

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    HassJob
)

from .kurrali_irrigation import RunSchedule, IrrigationOptions
from .const import DOMAIN

TIMEOUT_SECONDS = 20
UPDATE_INTERVAL = dt.timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


class RainbirdUpdateCoordinator(DataUpdateCoordinator[_T]):
    """Coordinator for rainbird API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        rainbird_controller: AsyncRainbirdController
    ) -> None:
        """Initialize ZoneStateUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Rainbird Stations",
            update_method=rainbird_controller.get_zone_states,
            update_interval=UPDATE_INTERVAL,
        )
        self.controller = rainbird_controller

        self.serial_number = None
        self.model_number = None

        self.options: IrrigationOptions = None

    async def reload_schedule(self, entry: ConfigEntry):
        """Reload all schedules"""
        self.options = IrrigationOptions(dict(entry.options))
        await self.async_request_refresh()

    async def _async_update_data(self) -> _T:
        """Fetch data from API endpoint."""
        if self.model_number is None:
            self.model_number = (await self.controller.get_model_and_version()).model_name
        if self.serial_number is None:
            self.model_number = await self.controller.get_serial_number()

        try:
            async with async_timeout.timeout(TIMEOUT_SECONDS):
                return await self.update_method()  # type: ignore[misc]
        except RainbirdApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
