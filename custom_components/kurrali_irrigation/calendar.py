from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from pydantic import ValidationError
import voluptuous as vol
from pyrainbird.async_client import States

from homeassistant.components.calendar import (
    EVENT_RRULE,
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady

from .coordinator import RainbirdUpdateCoordinator
from .const import DOMAIN, RAINBIRD

_LOGGER: logging.Logger = logging.getLogger(__package__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the local calendar platform."""
    coordinator = hass.data[DOMAIN][RAINBIRD]

    entity = LocalCalendarEntity(coordinator, "Kurrali Irrigation", unique_id=config_entry.entry_id)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        raise PlatformNotReady(f"Failed to load zone state: {str(err)}") from err

    async_add_entities([entity], True)


class LocalCalendarEntity(CoordinatorEntity[RainbirdUpdateCoordinator[States]], CalendarEntity):
    """The calendar displaying the schdedule."""

    _attr_has_entity_name = True
    _attr_supported_features = (
   #     CalendarEntityFeature.CREATE_EVENT
   #     | CalendarEntityFeature.DELETE_EVENT
    )

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize LocalCalendarEntity."""
        super().__init__(coordinator)
        self._event: CalendarEvent | None = None
        self._attr_name = name.capitalize()
        self._attr_unique_id = unique_id

    def get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        events = []
        for i in range((end_date - start_date).days + 1):
            date = (start_date + timedelta(days=i)).date()
            for sched in self.coordinator.options.schedules:
                zones = sched.get_zones_for_date(hass, date)
                if zones is not None:
                    for zone, length, time in zones:
                        events.append(CalendarEvent(time, time + length, zone))

        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        now = datetime(hour=now.hour, minute=now.minute, day=now.day, month=now.month, year=now.year)
        events = self.get_events(self.hass, now, now)

        for event in events:
            if now < event.end:

                return event

        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return self.get_events(hass, start_date, end_date)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.serial_number)
            },
            name="Kurrali Rainbird Controller",
            manufacturer=RAINBIRD,
            model=self.coordinator.model_number,
        )