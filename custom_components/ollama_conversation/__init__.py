"""Custom integration to integrate ollama_conversation with Home Assistant.

For more details about this integration, please refer to
https://github.com/ej52/hass-ollama-conversation
"""
from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, TemplateError
from homeassistant.helpers import intent, template
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import ulid

from .api import OllamaApiClient
from .const import (
    DOMAIN, LOGGER,

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
from .coordinator import OllamaDataUpdateCoordinator
from .exceptions import (
    ApiClientError,
    ApiCommError,
    ApiJsonError,
    ApiTimeoutError
)
from .helpers import get_exposed_entities

# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ollama conversation using UI."""
    hass.data.setdefault(DOMAIN, {})
    client = OllamaApiClient(
        base_url=entry.data[CONF_BASE_URL],
        timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        session=async_get_clientsession(hass),
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator = OllamaDataUpdateCoordinator(
        hass,
        client,
    )
    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    try:
        response = await client.async_get_heartbeat()
        if not response:
            raise ApiClientError("Invalid Ollama server")
    except ApiClientError as err:
        raise ConfigEntryNotReady(err) from err

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    conversation.async_set_agent(hass, entry, OllamaAgent(hass, entry, client))
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
        self.history: dict[str, dict] = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        raw_system_prompt = self.entry.options.get(CONF_PROMPT_SYSTEM, DEFAULT_PROMPT_SYSTEM)
        exposed_entities = get_exposed_entities(self.hass)

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid()
            try:
                system_prompt = self._async_generate_prompt(raw_system_prompt, exposed_entities)
            except TemplateError as err:
                LOGGER.error("Error rendering system prompt: %s", err)
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "I had a problem with my system prompt, please check the logs for more information.",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )
            messages = {
                "system": system_prompt,
                "context": None,
            }

        messages["prompt"] = user_input.text

        try:
            response = await self.query(messages)
        except (
            ApiCommError,
            ApiJsonError,
            ApiTimeoutError
        ) as err:
            LOGGER.error("Error generating prompt: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Something went wrong, {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )
        except HomeAssistantError as err:
            LOGGER.error("Something went wrong: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                "Something went wrong, please check the logs for more information.",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        messages["context"] = response["context"]
        self.history[conversation_id] = messages

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response["response"])
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _async_generate_prompt(self, raw_prompt: str, exposed_entities) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
                "exposed_entities": exposed_entities,
            },
            parse_result=False,
        )

    async def query(
        self,
        messages
    ):
        """Process a sentence."""
        model = self.entry.options.get(CONF_MODEL, DEFAULT_MODEL)

        LOGGER.debug("Prompt for %s: %s", model, messages["prompt"])

        result = await self.client.async_generate({
            "model": model,
            "context": messages["context"],
            "system": messages["system"],
            "prompt": messages["prompt"],
            "stream": False,
            "options": {
                "mirostat": int(self.entry.options.get(CONF_MIROSTAT_MODE, DEFAULT_MIROSTAT_MODE)),
                "mirostat_eta": self.entry.options.get(CONF_MIROSTAT_ETA, DEFAULT_MIROSTAT_ETA),
                "mirostat_tau": self.entry.options.get(CONF_MIROSTAT_TAU, DEFAULT_MIROSTAT_TAU),
                "num_ctx": self.entry.options.get(CONF_CTX_SIZE, DEFAULT_CTX_SIZE),
                "num_predict": self.entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                "temperature": self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                "repeat_penalty": self.entry.options.get(CONF_REPEAT_PENALTY, DEFAULT_REPEAT_PENALTY),
                "top_k": self.entry.options.get(CONF_TOP_K, DEFAULT_TOP_K),
                "top_p": self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
            }
        })

        response: str = result["response"]
        LOGGER.debug("Response %s", response)
        return result
