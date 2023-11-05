"""Ollama API Client."""
from __future__ import annotations

import asyncio
import socket

import aiohttp
import async_timeout

from .const import TIMEOUT


class OllamaApiClientError(Exception):
    """Exception to indicate a general API error."""


class OllamaApiClientCommunicationError(
    OllamaApiClientError
):
    """Exception to indicate a communication error."""


class OllamaApiClientAuthenticationError(
    OllamaApiClientError
):
    """Exception to indicate an authentication error."""


class OllamaApiClient:
    """Sample API Client."""

    def __init__(
        self,
        base_url: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._base_url = base_url.rstrip("/")
        self._session = session

    async def async_get_heartbeat(self) -> bool:
        """Get heartbeat from the API."""
        response = await self._api_wrapper(
            method="get", url=self._base_url, decode_json=False
        )
        return response == "Ollama is running"

    async def async_get_models(self) -> any:
        """Get models from the API."""
        return await self._api_wrapper(
            method="get",
            url=f"{self._base_url}/api/tags",
            headers={"Content-type": "application/json; charset=UTF-8"},
        )

    async def async_generate(self, data: dict | None = None,) -> any:
        """Generate a completion from the API."""
        return await self._api_wrapper(
            method="post",
            url=f"{self._base_url}/api/generate",
            data=data,
            headers={"Content-type": "application/json; charset=UTF-8"},
        )


    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
        decode_json: bool = True,
    ) -> any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    raise_for_status=True,
                    json=data,
                )

                if response.status in (401, 403):
                    raise OllamaApiClientAuthenticationError(
                        "Invalid credentials",
                    )

                if decode_json:
                    return await response.json()
                return await response.text()

        except asyncio.TimeoutError as exception:
            raise OllamaApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise OllamaApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            raise OllamaApiClientError(
                "Something really wrong happened!"
            ) from exception
