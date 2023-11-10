"""The exceptions used by Extended OpenAI Conversation."""
from homeassistant.exceptions import HomeAssistantError

class ApiClientError(HomeAssistantError):
    """Exception to indicate a general API error."""

class ApiCommError(ApiClientError):
    """Exception to indicate a communication error."""

class ApiJsonError(ApiClientError):
    """Exception to indicate an error with json response."""

class ApiTimeoutError(ApiClientError):
     """Exception to indicate a timeout error."""
