"""Config flow"""
from typing import Any
import logging
import datetime as dt
import copy

from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.selector import selector
import homeassistant.helpers.config_validation as cv

import voluptuous as vol

from pyrainbird.resources import RAINBIRD_MODELS

from . import async_setup_controller
from .kurrali_irrigation import RunSchedule, StartTrigger, IrrigationOptions, KEY_NAME, KEY_TRIGGERS, KEY_ZONES, KEY_TIME, KEY_DAY, dictfdelta

from .const import (
    DOMAIN,
    CONF_RAINBIRD_IP,
    CONF_RAINBIRD_PASSWORD,
    STATIONS
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

class KurraliConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow"""
    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize."""
        self.controller = None
        self.config = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Kurrali config flow."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            self.controller = await async_setup_controller(self.hass, user_input[CONF_RAINBIRD_IP], user_input[CONF_RAINBIRD_PASSWORD])

            try:
                await self.controller.get_serial_number()
                self.config[CONF_RAINBIRD_IP] = user_input[CONF_RAINBIRD_IP]
                self.config[CONF_RAINBIRD_PASSWORD] = user_input[CONF_RAINBIRD_PASSWORD]
                return await self.async_step_setup_stations()
            except Exception as e:
                errors['base'] = str(e)

        return self.async_show_form(
            step_id="user",
            last_step=False,
            data_schema=vol.Schema({vol.Required(CONF_RAINBIRD_IP): str, vol.Required(CONF_RAINBIRD_PASSWORD): str}),
            errors=errors
        )

    async def async_step_setup_stations(self, user_input: dict[str, Any] | None = None):
        """Handle the setup of rainbird zones"""
        if self.controller is None:
            return await self.async_step_user()

        if user_input is not None:
            names = []
            for name in user_input.values():
                names.append(name)

            self.config[STATIONS] = names
            return self.async_create_entry(
                    title="", data=self.config
            )

        model_and_version = await self.controller.get_model_and_version()

        zones = {}
        states = (await self.controller.get_available_stations()).stations
        for i in range(1, states.count + 1):
            if states.active(i):
                zones[vol.Required("station_" + str(i), default="Station " + str(i))] = str

        return self.async_show_form(
            step_id="setup_stations",
            description_placeholders={"model", model_and_version.model_name},
            data_schema=vol.Schema(zones)
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """The options handler"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

        self.current_schedule: RunSchedule = None
        self.schedule_save_callback = None

        self.options = IrrigationOptions(copy.deepcopy(dict(config_entry.options)))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            name: str = user_input['schedule_to_modify']

            for i, sched in enumerate(self.options.schedules):
                if name == sched.name:
                    self.current_schedule = RunSchedule(sched.as_dict())

                    def save_func():
                        self.options.schedules[i] = self.current_schedule
                    self.schedule_save_callback = save_func

                    return await self.async_step_modify_schedule()

            self.current_schedule = RunSchedule({
                KEY_NAME: '',
                KEY_ZONES: {},
                KEY_TRIGGERS: {
                    KEY_DAY: {
                        "frequency": 1,
                        "frequency_start": "2022-01-01"
                    },
                    KEY_TIME: {
                        "template": "00:10"
                    }
                }
            })
            self.schedule_save_callback = lambda: self.options.schedules.append(self.current_schedule)

            return await self.async_step_modify_schedule()

        schedules = []
        for sched in self.options.schedules:
            schedules.append(sched.name)

        schedules.append("Create New Schedule")

        return self.async_show_form(
            step_id="init",
            last_step=False,
            data_schema=vol.Schema({
                vol.Required("schedule_to_modify"): vol.In(schedules)
            }),
        )

    async def async_step_modify_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            stations = {}

            self.current_schedule.name = user_input['name']

            for station in user_input["stations"]:
                time = self.current_schedule.zones[station] if station in self.current_schedule.zones else dt.timedelta(minutes=10)
                stations[station] = time

            self.current_schedule.zones = stations

            self.current_schedule.trigger.day_config['frequency'] = int(user_input['frequency'])
            self.current_schedule.trigger.day_config['frequency_start'] = user_input['frequency_start']
            self.current_schedule.trigger.time_config['template'] = user_input['time_template']

            return await self.async_step_modify_run_times()

        trigger = self.current_schedule.trigger

        return self.async_show_form(
            step_id="modify_schedule",
            last_step=False,
            data_schema=vol.Schema({
                vol.Required("name", default=self.current_schedule.name): str,
                vol.Required("stations", default=list(self.current_schedule.zones)): selector({
                    'entity': {
                        'multiple': True,
                        'integration': DOMAIN,
                        'domain': Platform.BINARY_SENSOR
                    }
                }),
                vol.Required("frequency", default=trigger.day_config['frequency']): selector({
                    'number': {
                        'min': 0,
                        'max': 7
                    }
                }),
                vol.Required("frequency_start", default=trigger.day_config['frequency_start']): selector({
                    'date': {}
                }),
                vol.Required("time_template", default=trigger.time_config['template']): selector({
                    'template': {}
                })
            }),
        )

    async def async_step_modify_run_times(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            stations = list(self.current_schedule.zones)
            for i, station_id in enumerate(stations):
                time = user_input["time_for_" + str(i)]
                self.current_schedule.zones[station_id] = cv.positive_time_period(time)

            self.schedule_save_callback()

            self.current_schedule = None
            self.schedule_save_callback = None

            return self.async_create_entry(title="", data=self.options.as_dict())

        schema = {}

        for i, (station, time) in enumerate(self.current_schedule.zones.items()):
            name = self.hass.states.get(station).attributes["friendly_name"]
            schema[vol.Optional("label_for_" + str(i), default=name)] = vol.In([name])
            schema[vol.Required("time_for_" + str(i), default=dictfdelta(time))] = selector({'duration': {}})

        return self.async_show_form(
            step_id="modify_run_times",
            description_placeholders={'schedule_name': self.current_schedule.name},
            data_schema=vol.Schema(schema),
            last_step=True
        )
