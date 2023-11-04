"""Adds config flow for Ollama."""
from __future__ import annotations

import types
from types import MappingProxyType
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    TemplateSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    OllamaApiClient,
    OllamaApiClientAuthenticationError,
    OllamaApiClientCommunicationError,
    OllamaApiClientError,
)
from .const import (
    DOMAIN, LOGGER,

    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_CTX_SIZE,
    CONF_MAX_TOKENS,
    CONF_TEMPERATURE,

    DEFAULT_BASE_URL,
    DEFAULT_CHAT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_CTX_SIZE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
    }
)

DEFAULT_OPTIONS = types.MappingProxyType(
    {
        CONF_BASE_URL: DEFAULT_BASE_URL,
        CONF_CHAT_MODEL: DEFAULT_CHAT_MODEL,
        CONF_PROMPT: DEFAULT_PROMPT,
        CONF_CTX_SIZE: DEFAULT_CTX_SIZE,
        CONF_MAX_TOKENS: DEFAULT_MAX_TOKENS,
        CONF_TOP_K: DEFAULT_TOP_K,
        CONF_TOP_P: DEFAULT_TOP_P,
        CONF_TEMPERATURE: DEFAULT_TEMPERATURE
    }
)

class OllamaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ollama Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )


        errors = {}
        try:
            client = OllamaApiClient(
                base_url=cv.url_no_path(user_input[CONF_BASE_URL]).rstrip("/"),
                session=async_create_clientsession(self.hass),
            )
            await client.async_get_heartbeat()
        except vol.Invalid:
            errors["base"] = "invalid_url"
        except OllamaApiClientAuthenticationError:
            errors["base"] = "invalid_auth"
        except OllamaApiClientCommunicationError:
            errors["base"] = "cannot_connect"
        except OllamaApiClientError as exception:
            LOGGER.exception("Unexpected exception: %s", exception)
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="Ollama Conversation", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OllamaOptionsFlow(config_entry)


class OllamaOptionsFlow(config_entries.OptionsFlow):
    """Ollama config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="Ollama Conversation", data=user_input)

        try:
            client = OllamaApiClient(
                base_url=cv.url_no_path(self.config_entry.data[CONF_BASE_URL]).rstrip("/"),
                session=async_create_clientsession(self.hass),
            )
            response = await client.async_get_models()
            models = response["models"]
        except OllamaApiClientError as exception:
            LOGGER.exception("Unexpected exception: %s", exception)
            models = []

        schema = ollama_config_option_schema(self.config_entry.options, [model["name"] for model in models])
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema)
        )


def ollama_config_option_schema(options: MappingProxyType[str, Any], MODELS: []) -> dict:
    """Return a schema for Ollama completion options."""
    if not options:
        options = DEFAULT_OPTIONS
    return {
        vol.Optional(
            CONF_PROMPT,
            description={"suggested_value": options[CONF_PROMPT]},
            default=DEFAULT_PROMPT,
        ): TemplateSelector(),
        vol.Optional(
            CONF_CHAT_MODEL,
            description={
                "suggested_value": options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
            },
            default=DEFAULT_CHAT_MODEL
        ): SelectSelector(
            SelectSelectorConfig(
                options=MODELS,
                mode=SelectSelectorMode.DROPDOWN,
                custom_value=True,
                translation_key=CONF_CHAT_MODEL,
                sort=True
            )
        ),
        vol.Optional(
            CONF_CTX_SIZE,
            description={"suggested_value": options.get(CONF_CTX_SIZE, DEFAULT_CTX_SIZE)},
            default=DEFAULT_CTX_SIZE,
        ): int,
        vol.Optional(
            CONF_MAX_TOKENS,
            description={"suggested_value": options[CONF_MAX_TOKENS]},
            default=DEFAULT_MAX_TOKENS,
        ): int,
        vol.Optional(
            CONF_TEMPERATURE,
            description={"suggested_value": options[CONF_TEMPERATURE]},
            default=DEFAULT_TEMPERATURE,
        ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
        vol.Optional(
            CONF_TOP_K,
            description={"suggested_value": options[CONF_TOP_K]},
            default=DEFAULT_TOP_K,
        ): NumberSelector(NumberSelectorConfig(min=0, max=100, step=1)),
        vol.Optional(
            CONF_TOP_P,
            description={"suggested_value": options[CONF_TOP_P]},
            default=DEFAULT_TOP_P,
        ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
    }
