"""Dedicated Ollama provider client for Prompt Compiler."""

from typing import Any
import httpx
from app.config import settings


class OllamaError(Exception):
    """Base exception for all Ollama provider client errors."""


class EmptyPromptError(OllamaError):
    """Raised when the prompt passed to Ollama is empty."""


class OllamaConnectionError(OllamaError):
    """Raised when the Ollama server cannot be reached."""


class OllamaTimeoutError(OllamaError):
    """Raised when a request to Ollama exceeds the configured timeout."""


class OllamaHTTPError(OllamaError):
    """Raised when Ollama returns an HTTP error status code."""

    def __init__(self, message: str, status_code: int, response_body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class OllamaResponseError(OllamaError):
    """Raised when the response from Ollama is malformed or missing expected fields."""


class OllamaClient:
    """Asynchronous client for local Ollama HTTP API interactions."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT
        self._external_client = client is not None
        self._client = client

    async def __aenter__(self) -> "OllamaClient":
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client if internally managed."""
        if not self._external_client and self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt to Ollama's /api/generate endpoint and return the generated text.

        Args:
            prompt: Non-empty prompt text to send to the model.
            system: Optional system prompt to override the default system instruction.

        Returns:
            The generated response string from the model.

        Raises:
            EmptyPromptError: If the prompt is empty or only whitespace.
            OllamaConnectionError: If connection to Ollama fails.
            OllamaTimeoutError: If the request times out.
            OllamaHTTPError: If Ollama returns a non-200 HTTP status.
            OllamaResponseError: If the response is not valid JSON or lacks 'response'.
        """
        if not prompt or not prompt.strip():
            raise EmptyPromptError("Prompt must not be empty.")

        url = f"{self.base_url}/api/generate"
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        # Use the persistent client if managed in an async context, otherwise use a single-use client
        if self._client is not None and not self._client.is_closed:
            return await self._send_request(self._client, url, payload)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._send_request(client, url, payload)

    async def generate_async(self, prompt: str, system: str | None = None) -> str:
        """Async alias for generate to support engine components expecting generate_async."""
        return await self.generate(prompt=prompt, system=system)

    async def _send_request(self, client: httpx.AsyncClient, url: str, payload: dict) -> str:
        try:
            response = await client.post(url, json=payload, timeout=self.timeout)
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at '{self.base_url}'. Ensure the Ollama daemon is running."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(
                f"Request to Ollama timed out after {self.timeout}s."
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaConnectionError(
                f"Network communication error with Ollama at '{self.base_url}': {exc}"
            ) from exc

        if response.status_code != 200:
            raise OllamaHTTPError(
                f"Ollama returned HTTP error {response.status_code}: {response.text}",
                status_code=response.status_code,
                response_body=response.text,
            )

        try:
            data = response.json()
        except Exception as exc:
            raise OllamaResponseError(
                f"Invalid JSON received from Ollama: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise OllamaResponseError(
                f"Unexpected JSON structure from Ollama: expected dictionary, got {type(data).__name__}."
            )

        if "response" not in data:
            raise OllamaResponseError(
                "Ollama response JSON is missing the required 'response' field."
            )

        return str(data["response"])

    async def check_availability(self, timeout: float = 2.5) -> dict[str, Any]:
        """Check if local Ollama daemon is running and if the configured model is installed.

        Uses a lightweight check with a short timeout to prevent blocking.
        Does NOT download any models.
        """
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return {
                        "status": "unavailable",
                        "model": self.model,
                        "model_available": False,
                        "details": f"Ollama returned HTTP {resp.status_code}",
                    }
                data = resp.json()
                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]
                target = self.model.lower()
                target_base = target.split(":")[0]

                is_available = any(
                    name.lower() == target
                    or name.lower().startswith(f"{target}:")
                    or name.lower() == f"{target}:latest"
                    or (":" not in target and name.lower().startswith(f"{target_base}:"))
                    for name in model_names
                )
                return {
                    "status": "available",
                    "model": self.model,
                    "model_available": is_available,
                    "details": "Model is installed and ready" if is_available else f"Model '{self.model}' is not installed in local Ollama",
                }
        except Exception as exc:
            return {
                "status": "unavailable",
                "model": self.model,
                "model_available": False,
                "details": f"Cannot reach Ollama daemon at '{self.base_url}': {exc}",
            }


async def generate(prompt: str) -> str:
    """Convenience helper to generate text using the default OllamaClient configuration."""
    client = OllamaClient()
    return await client.generate(prompt)
