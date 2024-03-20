"""The exceptions used by Ollama Conversation."""
from homeassistant.exceptions import HomeAssistantError

class ApiError(HomeAssistantError):
    """Exception to indicate a general API error."""

class ApiClientError(ApiError):
    """Exception to indicate a general API error."""

class ApiCommError(ApiError):
    """Exception to indicate a communication error."""

class ApiJsonError(ApiError):
    """Exception to indicate an error with json response."""

class ApiTimeoutError(ApiError):
     """Exception to indicate a timeout error."""
