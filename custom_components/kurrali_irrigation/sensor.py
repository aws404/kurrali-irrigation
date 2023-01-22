"""Binary sensor platform for irrigation_unlimited."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant import config_entries
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pyrainbird.async_client import AsyncRainbirdController, RainbirdApiException
from pyrainbird.data import States

from .coordinator import RainbirdUpdateCoordinator

from .const import (
    DOMAIN,
    RAINBIRD,
    RAINBIRD_CONTROLLER,
)

async def async_setup_entry(hass, entry: config_entries.ConfigEntry, async_add_devices):
    """Setup binary_sensor platform."""

    rainbird_coordinator: RainbirdUpdateCoordinator = hass.data[DOMAIN][RAINBIRD]
    controller: AsyncRainbirdController = hass.data[DOMAIN][RAINBIRD_CONTROLLER]

    try:
        controller_sn = await controller.get_serial_number()
        controller_model = (await controller.get_model_and_version()).model_name
    except RainbirdApiException as err:
        raise PlatformNotReady(f"Failed to get stations: {str(err)}") from err

    controller = RainbirdControllerEntity(
        rainbird_coordinator,
        controller_model,
        controller_sn,
    )

    try:
        await rainbird_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        raise PlatformNotReady(f"Failed to load zone state: {str(err)}") from err

    async_add_devices([controller])


class RainbirdControllerEntity(CoordinatorEntity[RainbirdUpdateCoordinator[States]], SensorEntity):
    """The entity representing a rainbird controller"""
    def __init__(self,
        coordinator: RainbirdUpdateCoordinator[States],
        rainbird_model: str,
        rainbird_sn: str,
    ):
        super().__init__(coordinator)
        self._rainbird_sn = rainbird_sn
        self._rainbird_model = rainbird_model
        self._attr_unique_id = "irrigation_controller"

    @property
    def native_value(self):
        for index in range(1, self.coordinator.data.count + 1):
            if self.coordinator.data.active(index):
                return "Station " + str(index)

        return "Not Watering"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._rainbird_sn)
            },
            name="Kurrali Rainbird Controller",
            manufacturer=RAINBIRD,
            model=self._rainbird_model,
        )

    @property
    def extra_state_attributes(self):
        """Return state attributes."""

        next_sched, next_runtime = self.coordinator.next_schedule

        return {
            "total_stations": self.coordinator.data.count,
            "next_schedule": "None" if next_sched is None else next_sched.name,
            "next_schedule_time": str(next_runtime),
            "schedules": self.coordinator.next_runs
        }
