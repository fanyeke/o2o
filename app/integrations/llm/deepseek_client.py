"""DeepSeek LLM Client with JSON Mode support."""

import json
import logging
import time
from typing import Dict, Any, Tuple
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """Client for DeepSeek API with JSON Mode."""

    def __init__(self):
        """Initialize DeepSeek client."""
        settings = get_settings()
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model or "deepseek-v4-flash"
        self.endpoint = f"{settings.llm_endpoint}/chat/completions"  # Use config endpoint
        self.timeout = settings.llm_timeout or 30  # Use config timeout

        if not self.api_key:
            logger.warning("DeepSeek API key not configured")

    def generate_json(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> Tuple[Dict[str, Any], int, float]:
        """Generate structured JSON response using DeepSeek API.

        Args:
            prompt: Input prompt for LLM
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            Tuple of (parsed_json, tokens_used, latency_seconds)

        Raises:
            Exception: If API call fails or JSON parsing fails
        """
        if not self.api_key:
            raise Exception("DeepSeek API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},  # JSON Mode
        }

        start_time = time.time()

        try:
            logger.info(f"Calling DeepSeek API with model {self.model}")
            # Use httpx instead of requests (httpx is already imported)
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()

            latency = time.time() - start_time

            if response.status_code != 200:
                error_msg = response.text
                logger.error(f"DeepSeek API error: {response.status_code} - {error_msg}")
                raise Exception(f"DeepSeek API error: {response.status_code}")

            result = response.json()

            # Extract response content
            content = result["choices"][0]["message"]["content"]
            tokens_used = result["usage"]["total_tokens"]

            logger.info(
                f"DeepSeek response: tokens={tokens_used}, latency={latency:.2f}s"
            )

            # Parse JSON content
            try:
                parsed_json = json.loads(content)
                return parsed_json, tokens_used, latency
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw content: {content}")
                raise Exception(f"Invalid JSON response: {e}")

        except httpx.TimeoutException:
            latency = time.time() - start_time
            logger.error(f"DeepSeek API timeout after {latency:.2f}s")
            raise Exception("DeepSeek API timeout")

        except httpx.RequestError as e:
            logger.error(f"DeepSeek API request error: {e}")
            raise Exception(f"DeepSeek API request failed: {e}")

    def generate_json_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> Tuple[Dict[str, Any], int, float]:
        """Generate JSON response with retry logic.

        Args:
            prompt: Input prompt for LLM
            max_retries: Maximum retry attempts
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Tuple of (parsed_json, tokens_used, latency_seconds)

        Raises:
            Exception: If all retries fail
        """
        retry_delays = [5, 10, 20]  # seconds

        for attempt in range(max_retries):
            try:
                return self.generate_json(prompt, max_tokens, temperature)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.warning(
                        f"DeepSeek API attempt {attempt + 1} failed, "
                        f"retrying in {delay}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed: {e}")
                    raise

        # Should never reach here
        raise Exception("Unexpected error in retry logic")