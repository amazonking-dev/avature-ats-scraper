"""
HTTP client for web scraping.

Provides a reusable HTTP client with sensible defaults, timeout handling,
and graceful error handling.
"""

import httpx
from typing import Optional, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class HTTPClient:
    """Reusable HTTP client with default headers and error handling."""

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        headers: Optional[Dict[str, str]] = None,
        follow_redirects: bool = True,
    ):
        """
        Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds (default: 30.0)
            headers: Additional headers to include (default: None)
            follow_redirects: Whether to follow redirects (default: True)
        """
        default_headers = {
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        if headers:
            default_headers.update(headers)

        self.timeout = timeout
        self.client = httpx.Client(
            headers=default_headers,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[httpx.Response]:
        """
        Perform GET request.

        Args:
            url: URL to request
            params: Query parameters
            headers: Additional headers for this request

        Returns:
            Response object if successful, None if error occurred
        """
        try:
            response = self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            logger.error(f"Timeout error fetching {url}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} fetching {url}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[httpx.Response]:
        """
        Perform POST request.

        Args:
            url: URL to request
            data: Form data to send
            json: JSON data to send
            headers: Additional headers for this request

        Returns:
            Response object if successful, None if error occurred
        """
        try:
            response = self.client.post(url, data=data, json=json, headers=headers)
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            logger.error(f"Timeout error posting to {url}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} posting to {url}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error posting to {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error posting to {url}: {e}")
            return None

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
