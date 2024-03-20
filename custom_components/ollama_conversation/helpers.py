"""Helper functions for Ollama."""

from homeassistant.components.conversation import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

def get_exposed(hass: HomeAssistant):
    """Return exposed entities grouped by area."""
    hass_entity = entity_registry.async_get(hass)
    exposed_entities: dict[str, list[dict]] = {}

    for state in hass.states.async_all():
        if async_should_expose(hass, CONVERSATION_DOMAIN, state.entity_id):
            entity = hass_entity.async_get(state.entity_id)
            area = entity.area_id or 'none'

            exposed_entities[area] = exposed_entities.get(area, [])
            exposed_entities[area].append({
                "id": state.entity_id,
                "name": state.name,
                "state": state.state,
                "aliases": entity.aliases if entity else []
            })

    return dict(sorted(exposed_entities.items()))
