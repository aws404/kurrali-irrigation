"""Kurrali irrigation general classes"""
import datetime as dt
import logging

from pyrainbird.async_client import AsyncRainbirdController

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template, config_validation as cv

from .const import DOMAIN, SERVICE_MANUAL_IRRIGATION, DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)

KEY_DAY = "day"
KEY_TIME = "time"

class StartTrigger:
    """Represents the starting of a schedule"""
    def __init__(self, config: dict):
        self.day_config: dict = config[KEY_DAY]
        self.time_config: dict = config[KEY_TIME]

    def as_dict(self):
        """Get the trigger as a dict"""
        return {
            KEY_DAY: self.day_config,
            KEY_TIME: self.time_config
        }

    def get_run_for_date(self, hass: HomeAssistant, date: dt.date):
        """Get the run time (or None) for the specified day"""
        if "frequency" in self.day_config:
            frequency = self.day_config["frequency"]
            frequency_start: dt.date = cv.date(self.day_config["frequency_start"])

            if (date - frequency_start).days % frequency != 0:
                return None

        if "template" in self.time_config:
            time_template = template.Template(self.time_config["template"], hass)
            next_time = cv.time(time_template.async_render())

            #event.async_track_template_result()

        return next_time

KEY_NAME = "name"
KEY_ZONES = "zones"
KEY_TRIGGERS = "trigger"

def dictfdelta(tdelta: dt.timedelta):
    """Get time delta as string"""
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
    }

class RunSchedule:
    """Represents a run schedule"""
    def __init__(self, config: dict):
        self.name: str = config[KEY_NAME]
        self.zones: dict[str, dt.timedelta] = {}
        for zone in list(config[KEY_ZONES]):
            time = config[KEY_ZONES][zone]
            self.zones[zone] = cv.positive_time_period(time)

        self.trigger = StartTrigger(config[KEY_TRIGGERS])
        self.last_run_time = None

    def as_dict(self):
        """Get as a dict"""
        zones = {}
        for zone, time in self.zones.items():
            zones[zone] = dictfdelta(time)

        return {
            KEY_NAME: self.name,
            KEY_ZONES: zones,
            KEY_TRIGGERS: self.trigger.as_dict(),
        }

    def get_run_for_date(self, hass: HomeAssistant, date: dt.date):
        """Get the run time or None for the specified day"""
        return self.trigger.get_run_for_date(hass, date)

    def get_zones_for_date(self, hass: HomeAssistant, date: dt.date):
        """Get the run time or None for the specified day"""
        start_time = self.get_run_for_date(hass, date)
        if start_time is None:
            return None

        start = dt.datetime.combine(date, start_time)
        start_times: list[tuple[str, dt.timedelta, dt.datetime]] = []
        for zone, length in self.zones.items():
            start_times.append((zone, length, start))
            start = start + length

        return start_times

    def get_total_duration(self):
        """Get the total duration for the schdeule"""
        delta = dt.timedelta()
        for zone in self.zones.values():
            delta = delta + zone
        return delta

SCHEDULES = "schedules"

class IrrigationOptions:
    """Irrigation options"""
    def __init__(self, config: dict):
        self.schedules: list[RunSchedule] = []
        if SCHEDULES in config:
            for schedule in config[SCHEDULES]:
                self.schedules.append(RunSchedule(schedule))

    def as_dict(self):
        """Convert to serialisable form"""
        schedules = []
        for schedule in self.schedules:
            schedules.append(schedule.as_dict())

        return {
            SCHEDULES: schedules
        }
