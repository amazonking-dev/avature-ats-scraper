"""
Endpoint detection for Avature ATS job search APIs.

Detects working job search endpoints by trying common patterns and
validating responses heuristically.
"""

import json
from typing import Optional, Dict, Any, List, Set
from urllib.parse import urljoin
from scraper.client import HTTPClient
from utils.logger import get_logger

logger = get_logger(__name__)

# Common job-related field names to look for
JOB_FIELD_INDICATORS = {
    "jobId",
    "job_id",
    "id",
    "title",
    "jobTitle",
    "job_title",
    "description",
    "location",
    "department",
    "jobs",
    "requisitions",
    "positions",
    "results",
    "items",
    "data",
    "postings",
}

# Pagination field indicators
PAGINATION_INDICATORS = {
    "page",
    "pageNumber",
    "page_number",
    "currentPage",
    "totalPages",
    "total_pages",
    "totalCount",
    "total_count",
    "total",
    "hasMore",
    "has_more",
    "nextPage",
    "next_page",
    "offset",
    "limit",
    "perPage",
    "per_page",
}


class EndpointDetector:
    """Detects working job search API endpoints for Avature sites."""

    # Endpoint templates to try: (method, path, requires_json_body)
    ENDPOINT_TEMPLATES = [
        ("POST", "/services/JobSearch", True),
        ("POST", "/careers/SearchJobs", True),
        ("GET", "/api/jobs", False),
        ("GET", "/api/v1/jobs", False),
        ("POST", "/api/jobs/search", True),
        ("GET", "/careers/api/jobs", False),
    ]

    def __init__(self, timeout: float = 15.0):
        """
        Initialize endpoint detector.

        Args:
            timeout: Request timeout in seconds (default: 15.0)
        """
        self.timeout = timeout

    def detect(self, base_url: str) -> Optional[Dict[str, Any]]:
        """
        Detect a working job search endpoint for the given base URL.

        Args:
            base_url: Base URL of the Avature careers site

        Returns:
            Config dict with method, endpoint, pagination_type, detected_schema_keys,
            or None if no working endpoint found
        """
        base_url = base_url.rstrip("/")

        logger.info(f"Detecting endpoint for {base_url}")

        with HTTPClient(timeout=self.timeout) as client:
            for method, path, requires_json in self.ENDPOINT_TEMPLATES:
                endpoint_url = urljoin(base_url, path)
                logger.debug(f"Trying {method} {endpoint_url}")

                response = self._try_endpoint(
                    client, method, endpoint_url, requires_json
                )

                if response:
                    config = self._validate_and_extract_config(
                        response, method, endpoint_url
                    )
                    if config:
                        logger.info(
                            f"Detected working endpoint: {method} {endpoint_url}"
                        )
                        return config

        logger.warning(f"No working endpoint detected for {base_url}")
        return None

    def _try_endpoint(
        self,
        client: HTTPClient,
        method: str,
        url: str,
        requires_json: bool,
    ) -> Optional[Any]:
        """
        Try a specific endpoint and return response if valid.

        Args:
            client: HTTP client instance
            method: HTTP method (GET or POST)
            url: Full endpoint URL
            requires_json: Whether to send JSON body for POST requests

        Returns:
            Parsed JSON response if valid, None otherwise
        """
        headers = {"Content-Type": "application/json"} if requires_json else None

        try:
            if method == "GET":
                response = client.get(url, headers=headers)
            else:  # POST
                # Try with minimal JSON payload
                payload = {"page": 1, "pageSize": 10} if requires_json else None
                response = client.post(url, json=payload, headers=headers)

            if not response:
                return None

            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if "application/json" not in content_type:
                logger.debug(f"Response is not JSON: {content_type}")
                return None

            # Parse JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                logger.debug(f"Failed to parse JSON from {url}")
                return None

        except Exception as e:
            logger.debug(f"Error trying {method} {url}: {e}")
            return None

    def _validate_and_extract_config(
        self, data: Any, method: str, endpoint: str
    ) -> Optional[Dict[str, Any]]:
        """
        Validate response contains job-like data and extract config.

        Args:
            data: Parsed JSON response
            method: HTTP method used
            endpoint: Endpoint URL
            method: HTTP method

        Returns:
            Config dict if valid, None otherwise
        """
        if not isinstance(data, dict):
            return None

        # Find job-like fields in the response
        detected_keys = self._find_job_fields(data)
        if not detected_keys:
            logger.debug(f"No job-like fields found in response from {endpoint}")
            return None

        # Detect pagination type
        pagination_type = self._detect_pagination_type(data)

        # Extract schema keys (top-level keys that might contain job data)
        schema_keys = list(data.keys())

        return {
            "method": method,
            "endpoint": endpoint,
            "pagination_type": pagination_type,
            "detected_schema_keys": schema_keys,
            "job_fields_found": list(detected_keys),
        }

    def _find_job_fields(self, data: Any, depth: int = 0) -> Set[str]:
        """
        Recursively find job-related fields in the response.

        Args:
            data: Data structure to search
            depth: Current recursion depth (max 3 levels)

        Returns:
            Set of found job-related field names
        """
        found_fields = set()

        if depth > 3:  # Limit recursion depth
            return found_fields

        if isinstance(data, dict):
            for key, value in data.items():
                key_lower = key.lower()
                # Check if key matches job indicators
                if any(indicator.lower() in key_lower for indicator in JOB_FIELD_INDICATORS):
                    found_fields.add(key)

                # Recursively search nested structures
                if isinstance(value, (dict, list)):
                    found_fields.update(self._find_job_fields(value, depth + 1))

        elif isinstance(data, list) and len(data) > 0:
            # Check first item in list
            found_fields.update(self._find_job_fields(data[0], depth + 1))

        return found_fields

    def _detect_pagination_type(self, data: Dict[str, Any]) -> str:
        """
        Detect pagination type from response structure.

        Args:
            data: Response data dictionary

        Returns:
            Pagination type: 'page_based', 'offset_based', 'cursor_based', or 'unknown'
        """
        data_str = json.dumps(data).lower()

        # Check for page-based pagination
        if any(key in data_str for key in ["page", "pagenumber", "totalpages"]):
            return "page_based"

        # Check for offset-based pagination
        if any(key in data_str for key in ["offset", "limit"]):
            return "offset_based"

        # Check for cursor-based pagination
        if any(key in data_str for key in ["cursor", "nextcursor", "continuation"]):
            return "cursor_based"

        return "unknown"


def detect_endpoint(base_url: str, timeout: float = 15.0) -> Optional[Dict[str, Any]]:
    """
    Convenience function to detect endpoint for a base URL.

    Args:
        base_url: Base URL of the Avature careers site
        timeout: Request timeout in seconds

    Returns:
        Config dict or None if no endpoint found
    """
    detector = EndpointDetector(timeout=timeout)
    return detector.detect(base_url)
