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
    SelectOptionDict
)

from .api import OllamaApiClient
from .const import (
    DOMAIN, LOGGER,
    MENU_OPTIONS,

    CONF_BASE_URL,
    CONF_TIMEOUT,
    CONF_MODEL,
    CONF_CTX_SIZE,
    CONF_MAX_TOKENS,
    CONF_MIROSTAT_MODE,
    CONF_MIROSTAT_ETA,
    CONF_MIROSTAT_TAU,
    CONF_TEMPERATURE,
    CONF_REPEAT_PENALTY,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_PROMPT_SYSTEM,

    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    DEFAULT_MODEL,
    DEFAULT_CTX_SIZE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MIROSTAT_MODE,
    DEFAULT_MIROSTAT_ETA,
    DEFAULT_MIROSTAT_TAU,
    DEFAULT_TEMPERATURE,
    DEFAULT_REPEAT_PENALTY,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    DEFAULT_PROMPT_SYSTEM
)
from .exceptions import (
    ApiClientError,
    ApiCommError,
    ApiTimeoutError
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,
    }
)

DEFAULT_OPTIONS = types.MappingProxyType(
    {
        CONF_BASE_URL: DEFAULT_BASE_URL,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_MODEL: DEFAULT_MODEL,
        CONF_CTX_SIZE: DEFAULT_CTX_SIZE,
        CONF_MAX_TOKENS: DEFAULT_MAX_TOKENS,
        CONF_MIROSTAT_MODE: DEFAULT_MIROSTAT_MODE,
        CONF_MIROSTAT_ETA: DEFAULT_MIROSTAT_ETA,
        CONF_MIROSTAT_TAU: DEFAULT_MIROSTAT_TAU,
        CONF_TEMPERATURE: DEFAULT_TEMPERATURE,
        CONF_REPEAT_PENALTY: DEFAULT_REPEAT_PENALTY,
        CONF_TOP_K: DEFAULT_TOP_K,
        CONF_TOP_P: DEFAULT_TOP_P,
        CONF_PROMPT_SYSTEM: DEFAULT_PROMPT_SYSTEM
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

        # Search for duplicates with the same CONF_BASE_URL value.
        for existing_entry in self._async_current_entries(include_ignore=False):
            if existing_entry.data.get(CONF_BASE_URL) == user_input[CONF_BASE_URL]:
                return self.async_abort(reason="already_configured")

        errors = {}
        try:
            self.client = OllamaApiClient(
                base_url=cv.url_no_path(user_input[CONF_BASE_URL]),
                timeout=user_input[CONF_TIMEOUT],
                session=async_create_clientsession(self.hass),
            )
            response = await self.client.async_get_heartbeat()
            if not response:
                raise vol.Invalid("Invalid Ollama server")
        except vol.Invalid:
            errors["base"] = "invalid_url"
        except ApiTimeoutError:
            errors["base"] = "timeout_connect"
        except ApiCommError:
            errors["base"] = "cannot_connect"
        except ApiClientError as exception:
            LOGGER.exception("Unexpected exception: %s", exception)
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=f"Ollama - {user_input[CONF_BASE_URL]}", data={
                CONF_BASE_URL: user_input[CONF_BASE_URL]
            }, options={
                CONF_TIMEOUT: user_input[CONF_TIMEOUT]
            })

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
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=MENU_OPTIONS
        )

    async def async_step_general_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage General Settings."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        schema = ollama_schema_general_config(self.config_entry.options)
        return self.async_show_form(
            step_id="general_config",
            data_schema=vol.Schema(schema)
        )

    async def async_step_prompt_system(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Prompt Templates."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        schema = ollama_schema_prompt_system(self.config_entry.options)
        return self.async_show_form(
            step_id="prompt_system",
            data_schema=vol.Schema(schema)
        )

    async def async_step_model_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Model Settings."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        try:
            client = OllamaApiClient(
                base_url=cv.url_no_path(self.config_entry.data[CONF_BASE_URL]),
                timeout=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                session=async_create_clientsession(self.hass),
            )
            response = await client.async_get_models()
            models = response["models"]
        except ApiClientError as exception:
            LOGGER.exception("Unexpected exception: %s", exception)
            models = []

        schema = ollama_schema_model_config(self.config_entry.options, [model["name"] for model in models])
        return self.async_show_form(
            step_id="model_config",
            data_schema=vol.Schema(schema)
        )

def ollama_schema_general_config(options: MappingProxyType[str, Any]) -> dict:
    """Return a schema for general config."""
    if not options:
        options = DEFAULT_OPTIONS
    return {
        vol.Optional(
            CONF_TIMEOUT,
            description={"suggested_value": options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)},
            default=DEFAULT_TIMEOUT,
        ): int,
    }

def ollama_schema_prompt_system(options: MappingProxyType[str, Any]) -> dict:
    """Return a schema for system prompt."""
    if not options:
        options = DEFAULT_OPTIONS
    return {
        vol.Optional(
            CONF_PROMPT_SYSTEM,
            description={"suggested_value": options.get(CONF_PROMPT_SYSTEM, DEFAULT_PROMPT_SYSTEM)},
            default=DEFAULT_PROMPT_SYSTEM,
        ): TemplateSelector()
    }

def ollama_schema_model_config(options: MappingProxyType[str, Any], MODELS: []) -> dict:
    """Return a schema for model config."""
    if not options:
        options = DEFAULT_OPTIONS
    return {
        vol.Required(
            CONF_MODEL,
            description={
                "suggested_value": options.get(CONF_MODEL, DEFAULT_MODEL)
            },
            default=DEFAULT_MODEL
        ): SelectSelector(
            SelectSelectorConfig(
                options=MODELS,
                mode=SelectSelectorMode.DROPDOWN,
                custom_value=True,
                translation_key=CONF_MODEL,
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
            description={"suggested_value": options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)},
            default=DEFAULT_MAX_TOKENS,
        ): int,
        vol.Required(
            CONF_MIROSTAT_MODE,
            description={
                "suggested_value": options.get(CONF_MIROSTAT_MODE, DEFAULT_MIROSTAT_MODE)
            },
            default=DEFAULT_MIROSTAT_MODE
        ): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value="0", label="Disabled"),
                    SelectOptionDict(value="1", label="Mirostat (Enabled)"),
                    SelectOptionDict(value="2", label="Mirostat 2.0 (Enabled)"),
                ],
                mode=SelectSelectorMode.DROPDOWN,
                custom_value=False,
                translation_key=CONF_MIROSTAT_MODE,
                sort=True
            )
        ),
        vol.Optional(
            CONF_MIROSTAT_ETA,
            description={"suggested_value": options.get(CONF_MIROSTAT_ETA, DEFAULT_MIROSTAT_ETA)},
            default=DEFAULT_MIROSTAT_ETA,
        ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
        vol.Optional(
            CONF_MIROSTAT_TAU,
            description={"suggested_value": options.get(CONF_MIROSTAT_TAU, DEFAULT_MIROSTAT_TAU)},
            default=DEFAULT_MIROSTAT_TAU,
        ): NumberSelector(NumberSelectorConfig(min=0, max=10, step=0.5)),
        vol.Optional(
            CONF_TEMPERATURE,
            description={"suggested_value": options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)},
            default=DEFAULT_TEMPERATURE,
        ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
        vol.Optional(
            CONF_REPEAT_PENALTY,
            description={"suggested_value": options.get(CONF_REPEAT_PENALTY, DEFAULT_REPEAT_PENALTY)},
            default=DEFAULT_REPEAT_PENALTY,
        ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
        vol.Optional(
            CONF_TOP_K,
            description={"suggested_value": options.get(CONF_TOP_K, DEFAULT_TOP_K)},
            default=DEFAULT_TOP_K,
        ): NumberSelector(NumberSelectorConfig(min=0, max=100, step=1)),
        vol.Optional(
            CONF_TOP_P,
            description={"suggested_value": options.get(CONF_TOP_P, DEFAULT_TOP_P)},
            default=DEFAULT_TOP_P,
        ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
    }
