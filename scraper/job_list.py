"""
Job list fetcher for Avature ATS sites.

Fetches all pages of job listings using detected endpoint configuration.
"""

from typing import List, Dict, Any, Optional
from scraper.client import HTTPClient
from utils.logger import get_logger

logger = get_logger(__name__)


class JobListFetcher:
    """Fetches all job listings from an Avature endpoint."""

    # Common keys that might contain job arrays
    JOB_ARRAY_KEYS = [
        "jobs",
        "requisitions",
        "positions",
        "results",
        "items",
        "data",
        "postings",
        "jobListings",
        "job_listings",
    ]

    def __init__(self, timeout: float = 30.0):
        """
        Initialize job list fetcher.

        Args:
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.timeout = timeout

    def fetch_all(
        self, site_url: str, endpoint_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Fetch all job listings from the endpoint.

        Args:
            site_url: Base URL of the site (for reference)
            endpoint_config: Endpoint configuration from endpoint_detector

        Returns:
            List of raw job objects
        """
        method = endpoint_config.get("method", "GET")
        endpoint = endpoint_config.get("endpoint")
        pagination_type = endpoint_config.get("pagination_type", "unknown")
        schema_keys = endpoint_config.get("detected_schema_keys", [])

        if not endpoint:
            logger.error("Invalid endpoint config: missing endpoint")
            return []

        logger.info(f"Fetching jobs from {method} {endpoint}")

        all_jobs = []

        with HTTPClient(timeout=self.timeout) as client:
            if pagination_type == "page_based":
                jobs = self._fetch_page_based(client, method, endpoint, schema_keys)
            elif pagination_type == "offset_based":
                jobs = self._fetch_offset_based(client, method, endpoint, schema_keys)
            elif pagination_type == "cursor_based":
                jobs = self._fetch_cursor_based(client, method, endpoint, schema_keys)
            else:
                # Unknown pagination - try to fetch first page and see if there's more
                jobs = self._fetch_unknown_pagination(
                    client, method, endpoint, schema_keys
                )

            all_jobs.extend(jobs)

        logger.info(f"Total jobs fetched: {len(all_jobs)}")
        return all_jobs

    def _fetch_page_based(
        self,
        client: HTTPClient,
        method: str,
        endpoint: str,
        schema_keys: List[str],
    ) -> List[Dict[str, Any]]:
        """Fetch jobs using page-based pagination."""
        all_jobs = []
        page = 1
        page_size = 50  # Default page size

        while True:
            logger.debug(f"Fetching page {page}")

            payload = {"page": page, "pageSize": page_size}
            response_data = self._make_request(client, method, endpoint, payload)

            if not response_data:
                logger.debug(f"No response for page {page}, stopping")
                break

            jobs = self._extract_jobs(response_data, schema_keys)
            if not jobs:
                logger.debug(f"No jobs found on page {page}, stopping")
                break

            logger.info(f"Page {page}: Found {len(jobs)} jobs")
            all_jobs.extend(jobs)

            # Check if there are more pages
            if not self._has_more_pages(response_data, page):
                break

            page += 1

        return all_jobs

    def _fetch_offset_based(
        self,
        client: HTTPClient,
        method: str,
        endpoint: str,
        schema_keys: List[str],
    ) -> List[Dict[str, Any]]:
        """Fetch jobs using offset-based pagination."""
        all_jobs = []
        offset = 0
        limit = 50  # Default limit

        while True:
            logger.debug(f"Fetching offset {offset}")

            payload = {"offset": offset, "limit": limit}
            response_data = self._make_request(client, method, endpoint, payload)

            if not response_data:
                logger.debug(f"No response for offset {offset}, stopping")
                break

            jobs = self._extract_jobs(response_data, schema_keys)
            if not jobs:
                logger.debug(f"No jobs found at offset {offset}, stopping")
                break

            logger.info(f"Offset {offset}: Found {len(jobs)} jobs")
            all_jobs.extend(jobs)

            # If we got fewer jobs than limit, we're done
            if len(jobs) < limit:
                break

            offset += limit

        return all_jobs

    def _fetch_cursor_based(
        self,
        client: HTTPClient,
        method: str,
        endpoint: str,
        schema_keys: List[str],
    ) -> List[Dict[str, Any]]:
        """Fetch jobs using cursor-based pagination."""
        all_jobs = []
        cursor = None

        while True:
            logger.debug(f"Fetching with cursor: {cursor}")

            payload = {"pageSize": 50}
            if cursor:
                payload["cursor"] = cursor

            response_data = self._make_request(client, method, endpoint, payload)

            if not response_data:
                logger.debug("No response, stopping")
                break

            jobs = self._extract_jobs(response_data, schema_keys)
            if not jobs:
                logger.debug("No jobs found, stopping")
                break

            logger.info(f"Cursor {cursor or 'initial'}: Found {len(jobs)} jobs")
            all_jobs.extend(jobs)

            # Get next cursor
            next_cursor = self._get_next_cursor(response_data)
            if not next_cursor:
                break

            cursor = next_cursor

        return all_jobs

    def _fetch_unknown_pagination(
        self,
        client: HTTPClient,
        method: str,
        endpoint: str,
        schema_keys: List[str],
    ) -> List[Dict[str, Any]]:
        """Fetch jobs when pagination type is unknown - try first page only."""
        logger.warning("Unknown pagination type, attempting single page fetch")

        response_data = self._make_request(client, method, endpoint, {})

        if not response_data:
            return []

        jobs = self._extract_jobs(response_data, schema_keys)
        logger.info(f"Found {len(jobs)} jobs (single page)")
        return jobs

    def _make_request(
        self,
        client: HTTPClient,
        method: str,
        endpoint: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request and return parsed JSON.

        Args:
            client: HTTP client instance
            method: HTTP method (GET or POST)
            endpoint: Endpoint URL
            payload: Request payload

        Returns:
            Parsed JSON response or None
        """
        headers = {"Content-Type": "application/json"} if method == "POST" else None

        try:
            if method == "GET":
                response = client.get(endpoint, params=payload, headers=headers)
            else:  # POST
                response = client.post(endpoint, json=payload, headers=headers)

            if not response:
                return None

            return response.json()

        except Exception as e:
            logger.error(f"Error making request to {endpoint}: {e}")
            return None

    def _extract_jobs(
        self, response_data: Dict[str, Any], schema_keys: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract job objects from response data.

        Args:
            response_data: Parsed JSON response
            schema_keys: Known top-level keys from schema detection

        Returns:
            List of job objects
        """
        if not isinstance(response_data, dict):
            return []

        # Try to find job array in common locations
        for key in self.JOB_ARRAY_KEYS:
            if key in response_data:
                jobs = response_data[key]
                if isinstance(jobs, list):
                    return jobs

        # Try schema keys that were detected
        for key in schema_keys:
            if key in response_data:
                value = response_data[key]
                if isinstance(value, list):
                    # Check if items in list look like jobs (have common job fields)
                    if value and isinstance(value[0], dict):
                        return value

        # If response_data itself is a list, return it
        # (though this shouldn't happen based on endpoint detection)
        if isinstance(response_data, list):
            return response_data

        # Last resort: return empty list
        logger.warning("Could not find job array in response")
        return []

    def _has_more_pages(self, response_data: Dict[str, Any], current_page: int) -> bool:
        """
        Check if there are more pages available.

        Args:
            response_data: Response data dictionary
            current_page: Current page number

        Returns:
            True if more pages are available
        """
        # Check for explicit pagination indicators
        if "hasMore" in response_data:
            return response_data["hasMore"]
        if "has_more" in response_data:
            return response_data["has_more"]
        if "nextPage" in response_data:
            return response_data["nextPage"] is not None

        # Check total pages
        if "totalPages" in response_data:
            total_pages = response_data["totalPages"]
            return current_page < total_pages
        if "total_pages" in response_data:
            total_pages = response_data["total_pages"]
            return current_page < total_pages

        # If we can't determine, assume there might be more
        # (will stop when no jobs are returned)
        return True

    def _get_next_cursor(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract next cursor from response.

        Args:
            response_data: Response data dictionary

        Returns:
            Next cursor value or None
        """
        cursor_keys = ["nextCursor", "next_cursor", "cursor", "continuationToken"]
        for key in cursor_keys:
            if key in response_data and response_data[key]:
                return str(response_data[key])
        return None


def fetch_jobs(
    site_url: str, endpoint_config: Dict[str, Any], timeout: float = 30.0
) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch all jobs.

    Args:
        site_url: Base URL of the site
        endpoint_config: Endpoint configuration from endpoint_detector
        timeout: Request timeout in seconds

    Returns:
        List of raw job objects
    """
    fetcher = JobListFetcher(timeout=timeout)
    return fetcher.fetch_all(site_url, endpoint_config)
