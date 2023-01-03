"""Config flow"""
from typing import Any
from logging import Logger, getLogger

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import voluptuous as vol
import asyncio

import pyrainbird
from pyrainbird import async_client

from .const import (
    DOMAIN,
    CONF_RAINBIRD_IP,
    CONF_RAINBIRD_PASSWORD
)

_LOGGER: Logger = getLogger(__package__)

_LOGGER.info(pyrainbird)

class KurraliConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow"""
    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize."""
        self.controller = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Kurrali config flow."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            gathered_controller = await asyncio.gather(
                    _setup_controller(self.hass, user_input.get(CONF_RAINBIRD_IP), user_input.get(CONF_RAINBIRD_PASSWORD))
            )
            self.controller = gathered_controller[0]

            try:
                model_and_version = await self.controller.get_model_and_version()
                _LOGGER.info("Setting up controller with info: " + model_and_version)
                return
            except async_client.RainbirdApiException as e:
                errors['base'] = str(e)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_RAINBIRD_IP): str, vol.Required(CONF_RAINBIRD_PASSWORD): str}),
            errors=errors
        )

    async def async_step_setup_zones(self, user_input: dict[str, Any] | None = None):
        """Handle the setup of rainbird zones"""
        if self.controller is None:
            return await self.async_step_user()

        errors = {}

        if user_input is not None:
            try:
                # Handle user input
                return
            except Exception as e:
                errors['base'] = str(e)

        model_and_version = await self.controller.get_model_and_version()

        zones = []

        for enabled in (await self.controller.get_available_stations()).stations.states:
            if enabled:
                zones += "Zone"

        print(zones)

        return self.async_show_form(
            step_id="setup_zones",
            description_placeholders={"model", model_and_version.model_name},
            data_schema=vol.Schema({vol.Required(CONF_RAINBIRD_IP): str, vol.Required(CONF_RAINBIRD_PASSWORD): str}),
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

async def _setup_controller(hass, server, password):
    """Set up a controller."""
    client = async_client.AsyncRainbirdClient(async_get_clientsession(hass), server, password)
    controller = async_client.AsyncRainbirdController(client)
    return controller

class OptionsFlowHandler(config_entries.OptionsFlow):
    """The options handler"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("schedule_to_modify"): vol.In(["create"])
            }),
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(
                title="Test", data=self.options
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule_to_modify"): vol.In(["create"])
                }
            ),
        )