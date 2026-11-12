"""Config flow: the Orange Internet On the move portal account, with reauth and reconfigure."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import OrangeIotmAuthError, OrangeIotmClient, OrangeIotmError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_USERNAME = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username"))
_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password"))


def _schema(username: str | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username or vol.UNDEFINED): _USERNAME,
            vol.Required(CONF_PASSWORD): _PASSWORD,
        }
    )


class OrangeIotmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sign in to the portal."""

    # 2: standard username / password keys and a unique ID (1 was rexave's integration).
    VERSION = 2
    MINOR_VERSION = 1

    async def _async_check(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Log in with the given credentials; return the form errors."""
        client = OrangeIotmClient(
            async_get_clientsession(self.hass), user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )
        try:
            await client.async_login()
        except OrangeIotmAuthError:
            return {"base": "invalid_auth"}
        except OrangeIotmError as err:
            _LOGGER.debug("Cannot reach the portal: %s", err)
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error while signing in")
            return {"base": "unknown"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the portal credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {**user_input, CONF_USERNAME: user_input[CONF_USERNAME].strip()}
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()
            errors = await self._async_check(user_input)
            if not errors:
                return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
        return self.async_show_form(
            step_id="user",
            # Keep the login after an error, never the password.
            data_schema=self.add_suggested_values_to_schema(
                _schema(), {CONF_USERNAME: user_input[CONF_USERNAME]} if user_input else {}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, _entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The portal rejected the stored credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the password again (same account)."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_USERNAME: entry.data[CONF_USERNAME], CONF_PASSWORD: user_input[CONF_PASSWORD]}
            errors = await self._async_check(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the password, or the account login, of the entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {**user_input, CONF_USERNAME: user_input[CONF_USERNAME].strip()}
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            # Another account would be a new entry, not this one.
            if entry.unique_id is not None:
                self._abort_if_unique_id_mismatch(reason="wrong_account")
            errors = await self._async_check(user_input)
            if not errors:
                return self.async_update_reload_and_abort(entry, unique_id=self.unique_id, data_updates=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(entry.data[CONF_USERNAME]),
            errors=errors,
        )
