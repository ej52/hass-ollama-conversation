"""Constants for ollama_conversation."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Ollama Conversation"
DOMAIN = "ollama_conversation"
OLLAMA_REQUIRED_VERSION = "0.1.26"

MENU_OPTIONS = ["general_config", "model_config", "prompt_system"]

INTENT_HANDLER_OPTIONS = {
    'none': 'No intent handling',
    'builtin': 'Use built-in agent only'
}

CONF_BASE_URL = "base_url"
CONF_TIMEOUT = "timeout"
CONF_INTENT_HANDLER = "intent_handler"
CONF_MODEL = "chat_model"
CONF_CTX_SIZE = "ctx_size"
CONF_MAX_TOKENS = "max_tokens"
CONF_MIROSTAT_MODE = "mirostat_mode"
CONF_MIROSTAT_ETA = "mirostat_eta"
CONF_MIROSTAT_TAU = "mirostat_tau"
CONF_TEMPERATURE = "temperature"
CONF_REPEAT_PENALTY = "repeat_penalty"
CONF_TOP_K = "top_k"
CONF_TOP_P = "top_p"
CONF_PROMPT_SYSTEM = "prompt"

DEFAULT_BASE_URL = "http://homeassistant.local:11434"
DEFAULT_TIMEOUT = 60
DEFAULT_INTENT_HANDLER = 'builtin'
DEFAULT_MODEL = "llama2:latest"
DEFAULT_CTX_SIZE = 2048
DEFAULT_MAX_TOKENS = 128
DEFAULT_MIROSTAT_MODE = "0"
DEFAULT_MIROSTAT_ETA = 0.1
DEFAULT_MIROSTAT_TAU = 5.0
DEFAULT_TEMPERATURE = 0.8
DEFAULT_REPEAT_PENALTY = 1.1
DEFAULT_TOP_K = 40
DEFAULT_TOP_P = 0.9
DEFAULT_PROMPT_SYSTEM = """This smart home is controlled by Home Assistant.

Current Time: {{now()}}
Current Area: {{area_name(current_device_id)}}

An overview of the areas and the available devices in this smart home:
{% for area_id, entities in exposed_entities.items() -%}
{{ area_name(area_id) }} (Area ID: {{ area_id }}):
  {% for entity in entities -%}
{{ entity.name }} (Entity ID: {{ entity.id }} ) is {{ entity.state }}
  {% endfor -%}
{% endfor -%}

Answer the user's questions about the world truthfully.

The current state of devices is provided in available devices.
If the user wants to control a device, reject the request and suggest using the Home Assistant app.
"""
