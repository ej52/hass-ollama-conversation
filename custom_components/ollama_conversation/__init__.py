"""Custom integration to integrate ollama_conversation with Home Assistant.

For more details about this integration, please refer to
https://github.com/ej52/hass-ollama-conversation
"""
from __future__ import annotations

import json
from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed, TemplateError
from homeassistant.helpers import intent, template
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import ulid

from .api import (
    OllamaApiClient,
    OllamaApiClientAuthenticationError,
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

    DEFAULT_CHAT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_CTX_SIZE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P
)
from .coordinator import OllamaDataUpdateCoordinator

# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ollama conversation using UI."""
    hass.data.setdefault(DOMAIN, {})
    client = OllamaApiClient(
        base_url=entry.data[CONF_BASE_URL],
        session=async_get_clientsession(hass),
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator = OllamaDataUpdateCoordinator(
        hass,
        client,
    )
    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    try:
        await client.async_get_heartbeat()
    except OllamaApiClientAuthenticationError as exception:
        raise ConfigEntryAuthFailed(exception) from exception
    except OllamaApiClientError as err:
        raise ConfigEntryNotReady(err) from err

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    conversation.async_set_agent(hass, entry, OllamaAgent(hass, entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ollama conversation."""
    conversation.async_unset_agent(hass, entry)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Ollama conversation."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class OllamaAgent(conversation.AbstractConversationAgent):
    """Ollama conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: OllamaApiClient) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.client = client
        self.history: dict[str, list[dict]] = {}

    @property
    def attribution(self):
        """Return the attribution."""
        return {"name": "Powered by Ollama", "url": "https://github.com/ej52/hass-ollama-conversation"}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""

        intent_response = intent.IntentResponse(language=user_input.language)

        model = self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            context = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid()
            context = None

        try:
            system_prompt = self._async_generate_prompt(prompt)
        except TemplateError as err:
            LOGGER.error("Error rendering prompt: %s", err)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem with my template: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        payload = {
            "model": model,
            "context": context,
            "system": system_prompt,
            "prompt": user_input.text,
            "stream": False,
            "options": {
                "top_k": self.entry.options.get(CONF_TOP_K, DEFAULT_TOP_K),
                "top_p": self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P),
                "num_ctx": self.entry.options.get(CONF_CTX_SIZE, DEFAULT_CTX_SIZE),
                "num_predict": self.entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                "temperature": self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
            }
        }

        LOGGER.debug("Prompt for %s: %s", model, json.dumps(payload))

        try:
            result = await self.client.async_generate(payload)
        except OllamaApiClientError as err:
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem talking to the Ollama server: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        LOGGER.debug("Response %s", json.dumps(result))

        self.history[conversation_id] = result["context"]
        intent_response.async_set_speech(result["response"])

        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _async_generate_prompt(self, raw_prompt: str) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
            },
            parse_result=False,
        )
