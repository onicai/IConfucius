"""iconfucius.http_utils — HTTP helpers with retry logic."""

import time

from curl_cffi import requests as cffi_requests

from iconfucius.config import log


def cffi_get_with_retry(url, *, params=None, timeout=10,
                        retries=3, backoff=(3, 8, 15),
                        **kwargs):
    """GET request via curl_cffi with retry on transient failures.

    Retries on any exception (network error, timeout, etc.).
    Does NOT retry on non-200 HTTP status codes — those are valid responses.

    Args:
        url: The URL to request.
        params: Query parameters.
        timeout: Request timeout in seconds.
        retries: Number of retry attempts (default 3).
        backoff: Tuple of wait times in seconds between retries.
        **kwargs: Additional kwargs passed to curl_cffi requests.get().

    Returns:
        The curl_cffi Response object.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc = None
    for attempt in range(1 + retries):
        try:
            resp = cffi_requests.get(
                url,
                params=params,
                impersonate="chrome",
                headers={"Accept": "application/json"},
                timeout=timeout,
                **kwargs,
            )
            return resp
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                wait = backoff[attempt] if attempt < len(backoff) else backoff[-1]
                log(f"  HTTP GET {url} failed (attempt {attempt + 1}/{1 + retries}): "
                    f"{exc}. Retrying in {wait}s...")
                time.sleep(wait)
    raise last_exc
