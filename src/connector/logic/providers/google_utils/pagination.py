"""Generic paginated Google API fetcher with rate limit handling."""

from typing import Any, AsyncIterator

import httpx

from connector.logic.exceptions import DownloadError, RateLimitError
from connector.logic.providers.google_utils.rate_limiter import (
    MAX_RATE_LIMIT_RETRIES,
    handle_rate_limit,
)


async def google_paginate(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any],
    items_key: str,
    provider: str,
    page_token_key: str = "pageToken",
    next_page_token_key: str = "nextPageToken",
    max_pages: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Paginate through a Google API endpoint, yielding individual items.

    Handles rate limiting (429) with automatic retry and sleep.
    Raises on non-200 responses after rate limit retries are exhausted.

    Args:
        client: httpx async client for requests.
        url: Full API endpoint URL.
        headers: Request headers (must include Authorization).
        params: Query parameters (pageToken will be managed automatically).
        items_key: JSON key containing the list of items (e.g., "messages",
            "events", "connections").
        provider: Provider name for error messages.
        page_token_key: Parameter name for sending page token (default:
            "pageToken").
        next_page_token_key: Response key for next page token (default:
            "nextPageToken").
        max_pages: Maximum number of pages to fetch. None for unlimited.

    Yields:
        Individual item dicts from each page.

    Raises:
        RateLimitError: If rate limit retries are exhausted.
        DownloadError: If a non-200/non-429 response is received.
    """
    page_count = 0
    page_token: str | None = None

    while True:
        if max_pages is not None and page_count >= max_pages:
            return

        request_params = dict(params)
        if page_token:
            request_params[page_token_key] = page_token

        response = await _fetch_with_rate_limit(
            client=client,
            url=url,
            headers=headers,
            params=request_params,
            provider=provider,
        )

        data = response.json()
        items = data.get(items_key, [])

        for item in items:
            yield item

        page_count += 1
        page_token = data.get(next_page_token_key)

        if not page_token:
            return


async def _fetch_with_rate_limit(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any],
    provider: str,
) -> httpx.Response:
    """Execute a GET request with automatic rate limit retry.

    Args:
        client: httpx async client.
        url: Request URL.
        headers: Request headers.
        params: Query parameters.
        provider: Provider name for error messages.

    Returns:
        Successful httpx.Response (status 200).

    Raises:
        RateLimitError: If max retries exhausted on 429 responses.
        DownloadError: If a non-200/non-429 response is received.
    """
    for attempt in range(MAX_RATE_LIMIT_RETRIES):
        response = await client.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response

        if response.status_code == 429:
            if attempt >= MAX_RATE_LIMIT_RETRIES - 1:
                raise RateLimitError(provider)
            await handle_rate_limit(response, provider)
            continue

        raise DownloadError(
            provider,
            url,
            f"Google API error {response.status_code}: {response.text}",
        )

    # Should not be reached, but satisfy type checker
    raise RateLimitError(provider)
