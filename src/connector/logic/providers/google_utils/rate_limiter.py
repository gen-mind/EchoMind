"""Rate limit handling for Google API responses."""

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx

from connector.logic.exceptions import RateLimitError

logger = logging.getLogger("echomind-connector.google_rate_limiter")

# Maximum retry attempts for rate-limited requests
MAX_RATE_LIMIT_RETRIES = 6

# Default sleep time when Retry-After is not provided
DEFAULT_RETRY_SECONDS = 60

# Buffer to add to retry-after time
RETRY_BUFFER_SECONDS = 3


async def handle_rate_limit(response: httpx.Response, provider: str) -> None:
    """Parse rate limit response and sleep for the indicated duration.

    Call this when a Google API returns 429. It will sleep for the
    appropriate duration based on the Retry-After header or error
    message timestamp.

    Args:
        response: The 429 response from Google API.
        provider: Provider name for error messages.

    Raises:
        RateLimitError: If called (caller should implement retry loop).
    """
    retry_after = response.headers.get("Retry-After")

    if retry_after:
        sleep_time = int(retry_after)
    else:
        # Try to parse timestamp from error body
        sleep_time = _parse_retry_timestamp(response.text)

    sleep_time += RETRY_BUFFER_SECONDS

    logger.warning(
        f"⚠️ [{provider}] Rate limited. Sleeping for {sleep_time}s"
    )
    await asyncio.sleep(sleep_time)


def _parse_retry_timestamp(error_text: str) -> int:
    """Extract retry delay from Google error message timestamp.

    Google sometimes includes a timestamp like:
    "Retry after 2026-02-07T10:30:00.000Z"

    Args:
        error_text: The error response body text.

    Returns:
        Seconds to wait, or DEFAULT_RETRY_SECONDS if parsing fails.
    """
    match = re.search(
        r"Retry after (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)",
        error_text,
    )
    if match:
        try:
            retry_after_dt = datetime.fromisoformat(
                match.group(1).replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            delta = (retry_after_dt - now).total_seconds()
            return max(int(delta), 0)
        except (ValueError, OSError):
            pass

    return DEFAULT_RETRY_SECONDS
