"""Custom integration to integrate ollama_conversation with Home Assistant.

For more details about this integration, please refer to
https://github.com/ej52/hass-ollama-conversation
"""
from __future__ import annotations
from packaging import version

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .agent import OllamaAgent
from .api import OllamaApiClient
from .coordinator import OllamaDataUpdateCoordinator
from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    OLLAMA_REQUIRED_VERSION,
)

from .exceptions import (
    ApiClientError
)

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
        response = await client.async_get_version()
        if not response:
            raise ApiClientError("Invalid Ollama server")
        if version.parse(response["version"]) < version.parse(OLLAMA_REQUIRED_VERSION):
            raise ApiClientError(f"Ollama server version needs to be {OLLAMA_REQUIRED_VERSION} or newer")
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