import random

from homeassistant.components import conversation, intent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import intent, template
from homeassistant.util import ulid
from home_assistant_intents import get_languages

from .api import OllamaApiClient
from .const import *
from .const import LOGGER
from .exceptions import ApiError
from .helpers import get_exposed

class OllamaAgent(conversation.AbstractConversationAgent):
    """Ollama conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: OllamaApiClient) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.client = client
        self.handler = DEFAULT_INTENT_HANDLER
        self.history: dict[str, list[dict[str, str]]] = {}

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return get_languages()

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        use_builtin_agent = (self.entry.options.get(CONF_INTENT_HANDLER, DEFAULT_INTENT_HANDLER) == 'builtin')

        if use_builtin_agent:
            if result := await self._call_builtin_agent(user_input):
                return result

        intent_response = intent.IntentResponse(language=user_input.language)
        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            user_input.conversation_id = conversation_id = ulid.ulid()
            try:
                system_prompt = self._async_generate_prompt(user_input)
                messages = [{"role": "user", "content": system_prompt}]
            except TemplateError as err:
                LOGGER.error("Error rendering system prompt: %s", err)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "I had a problem with my system prompt, please check the logs for more information.",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )

        messages.append({"role": "user", "content": user_input.text})
        try:
            response = await self._call_llm(messages)
        except (
            ApiError
        ) as err:
            LOGGER.error("API error: %s", err)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Something went wrong, please check the logs for more information.",
            )
        except HomeAssistantError as err:
            LOGGER.error("Something went wrong: %s", err)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                "Something went wrong, please check the logs for more information.",
            )

        if intent_response.response_type is not intent.IntentResponseType.ERROR:
            messages.append({"role": "assistant", "content": response})
            self.history[conversation_id] = messages
            intent_response.async_set_speech(response)

        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _async_generate_prompt(self, user_input: conversation.ConversationInput) -> str:
        """Generate a prompt for the user."""

        raw_prompt = str(self.entry.options.get(CONF_PROMPT_SYSTEM, DEFAULT_PROMPT_SYSTEM))
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
                "current_device_id": user_input.device_id,
                "exposed_entities": get_exposed(self.hass)
            },
            parse_result=False,
        )

    async def _call_builtin_agent(self, user_input: conversation.ConversationInput):
        agent: conversation.DefaultAgent = await conversation._get_agent_manager(self.hass).async_get_agent()
        if not (recognize_result := await agent.async_recognize(user_input)):
            return None

        result = await agent.async_process(user_input)
        result.conversation_id = user_input.conversation_id

        content = str(result.response.speech.get('plain', {}).get('speech', ''))
        if recognize_result.intent.name == 'HassGetState' and (content == 'Not any' or result.response.response_type is intent.IntentResponseType.ERROR):
            return None

        return result

    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Process a sentence."""
        model = self.entry.options.get(CONF_MODEL, DEFAULT_MODEL)
        LOGGER.debug("Prompt for %s: %s", model, messages)

        result = await self.client.async_chat({
            "model": model,
            "messages": messages,
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

        LOGGER.debug("Response: %s", result)
        return result["message"]["content"]