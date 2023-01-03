"""Config flow"""
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pyrainbird.async_client import (
    AsyncRainbirdClient,
    AsyncRainbirdController,
    RainbirdApiException,
)
from logging import WARNING, Logger, getLogger, INFO, DEBUG, ERROR

from .const import DOMAIN

_LOGGER: Logger = getLogger(__package__)

class KurraliConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow"""
    controller = None


    """Kurrali config flow."""
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        await self.async_set_unique_id("kurrali.irrigation")
        self._abort_if_unique_id_configured()

        errors = {}

        if user_input is not None:
            client = AsyncRainbirdClient(async_get_clientsession(self.hass), user_input["rainbird_ip"], user_input["rainbird_password"])
            self.controller = AsyncRainbirdController(client)
            try:
                model_and_version = await self.controller.get_model_and_version()
                _LOGGER.info("Setting up controller with info: " + model_and_version)
                return
            except RainbirdApiException as e:
                errors['base'] = str(e)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("rainbird_ip"): str, vol.Required("rainbird_password"): str}),
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
            data_schema=vol.Schema({vol.Required("rainbird_ip"): str, vol.Required("rainbird_password"): str}),
            errors=errors
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
