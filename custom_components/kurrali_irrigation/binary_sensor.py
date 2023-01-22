"""Binary sensor platform for irrigation_unlimited."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import async_get_current_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant import config_entries
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pyrainbird import AvailableStations
from pyrainbird.async_client import AsyncRainbirdController, RainbirdApiException
from pyrainbird.data import States

import voluptuous as vol
from datetime import timedelta

from .coordinator import RainbirdUpdateCoordinator

from .const import (
    DOMAIN,
    RAINBIRD,
    RAINBIRD_CONTROLLER,
    ICON_ZONE_ON,
    ICON_ZONE_OFF,
    SERVICE_MANUAL_IRRIGATION
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry, async_add_devices):
    """Setup binary_sensor platform."""
    entities = []

    rainbird_coordinator: RainbirdUpdateCoordinator = hass.data[DOMAIN][RAINBIRD]
    controller: AsyncRainbirdController = hass.data[DOMAIN][RAINBIRD_CONTROLLER]

    try:
        available_stations: AvailableStations = (
            await controller.get_available_stations()
        )
    except RainbirdApiException as err:
        raise PlatformNotReady(f"Failed to get stations: {str(err)}") from err

    if not (available_stations and available_stations.stations):
        return

    for zone in range(1, available_stations.stations.count + 1):
        if available_stations.stations.active(zone):
            name: str = entry.data["stations"][zone - 1]
            _LOGGER.info("Setting up rainbird station %s with name %s" % (str(zone), name))
            entities.append(
                RainbirdStationEntity(
                    rainbird_coordinator,
                    zone,
                    name
                )
            )

    async_add_devices(entities)

    platform = async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_MANUAL_IRRIGATION,
        {
            vol.Required('time'): cv.positive_time_period,
        },
        SERVICE_MANUAL_IRRIGATION,
    )

    async def stop_irrigation(service):
        await controller.stop_irrigation()
        await rainbird_coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        "stop_irrigation",
        stop_irrigation,
    )

    try:
        await rainbird_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        raise PlatformNotReady(f"Failed to load zone state: {str(err)}") from err

class RainbirdStationEntity(CoordinatorEntity[RainbirdUpdateCoordinator[States]], BinarySensorEntity):
    """The entity representing a rainbird station"""

    def __init__(self,
        coordinator: RainbirdUpdateCoordinator[States],
        index: int,
        friendly_name: str
    ):
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = "irrigation_station_" + str(index)
        self._name = friendly_name
        self._attr_icon = ICON_ZONE_OFF

    @property
    def name(self):
        """Get the name of the zone."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return state attributes."""
        return {"index": self._index}

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.coordinator.data.active(self._index)

    @property
    def icon(self):
        return ICON_ZONE_ON if self.is_on else ICON_ZONE_OFF

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

    async def manual_irrigation(self, time: timedelta):
        """Trigger a manual irrigation"""
        controller: AsyncRainbirdController = self.hass.data[DOMAIN][RAINBIRD_CONTROLLER]
        await controller.irrigate_zone(self._index, int(time.seconds / 60))
        await self.coordinator.async_request_refresh()
