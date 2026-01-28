"""
Endpoint detection for Avature ATS job search APIs.

Detects working job search endpoints by trying common patterns and
validating responses heuristically.
"""

import json
import re
from typing import Optional, Dict, Any, List, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup
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

    def __init__(self, timeout: float = 15.0, inspect_scripts: bool = True):
        """
        Initialize endpoint detector.

        Args:
            timeout: Request timeout in seconds (default: 15.0)
            inspect_scripts: Whether to inspect inline scripts for config (default: True)
        """
        self.timeout = timeout
        self.inspect_scripts = inspect_scripts

    def detect(self, base_url: str) -> Optional[Dict[str, Any]]:
        """
        Detect a working job search endpoint for the given base URL.

        Args:
            base_url: Base URL of the Avature careers site

        Returns:
            Config dict with method, endpoint, pagination_type, detected_schema_keys,
            config_hints, or None if no working endpoint found
        """
        base_url = base_url.rstrip("/")

        logger.info(f"Detecting endpoint for {base_url}")

        # Optional: Inspect scripts for config hints
        config_hints = None
        if self.inspect_scripts:
            try:
                config_hints = self._extract_config_from_scripts(base_url)
                if config_hints:
                    logger.debug(f"Found config hints: {list(config_hints.keys())}")
            except Exception as e:
                logger.debug(f"Script inspection failed (non-critical): {e}")

        # Try endpoint templates, optionally prioritizing hints
        endpoint_templates = self._prioritize_endpoints(
            self.ENDPOINT_TEMPLATES, config_hints
        )

        with HTTPClient(timeout=self.timeout) as client:
            for method, path, requires_json in endpoint_templates:
                endpoint_url = urljoin(base_url, path)
                logger.debug(f"Trying {method} {endpoint_url}")

                # Use config hints to improve request if available
                response = self._try_endpoint(
                    client, method, endpoint_url, requires_json, config_hints
                )

                if response:
                    config = self._validate_and_extract_config(
                        response, method, endpoint_url
                    )
                    if config:
                        # Add config hints to returned config
                        if config_hints:
                            config["config_hints"] = config_hints
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
        config_hints: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        Try a specific endpoint and return response if valid.

        Args:
            client: HTTP client instance
            method: HTTP method (GET or POST)
            url: Full endpoint URL
            requires_json: Whether to send JSON body for POST requests
            config_hints: Optional config hints from script inspection

        Returns:
            Parsed JSON response if valid, None otherwise
        """
        headers = {"Content-Type": "application/json"} if requires_json else None

        try:
            if method == "GET":
                # Use config hints for GET params if available
                params = None
                if config_hints and "api_params" in config_hints:
                    params = config_hints.get("api_params", {})
                response = client.get(url, params=params, headers=headers)
            else:  # POST
                # Build payload with config hints if available
                payload = {"page": 1, "pageSize": 10} if requires_json else None
                if config_hints:
                    # Merge config hints into payload
                    if "api_params" in config_hints:
                        if payload:
                            payload.update(config_hints["api_params"])
                        else:
                            payload = config_hints["api_params"].copy()
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

    def _extract_config_from_scripts(
        self, base_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract configuration from inline scripts and JS bundles.

        Args:
            base_url: Base URL of the careers site

        Returns:
            Dictionary with extracted config hints or None
        """
        try:
            with HTTPClient(timeout=self.timeout) as client:
                response = client.get(base_url)
                if not response:
                    return None

                soup = BeautifulSoup(response.text, "lxml")
                config_hints = {}

                # Find all script tags
                scripts = soup.find_all("script")

                for script in scripts:
                    script_content = script.string
                    if not script_content:
                        # Check src attribute for external scripts
                        src = script.get("src", "")
                        if src and "avature" in src.lower():
                            # Could fetch external scripts, but skip for now
                            continue
                        continue

                    # Look for common Avature config patterns
                    config_patterns = [
                        r"window\.__AVATURE_CONFIG__\s*=\s*({[^;]+})",
                        r"window\.avatureConfig\s*=\s*({[^;]+})",
                        r"var\s+avatureConfig\s*=\s*({[^;]+})",
                        r"const\s+avatureConfig\s*=\s*({[^;]+})",
                        r"AVATURE_CONFIG\s*=\s*({[^;]+})",
                        r"avature\.config\s*=\s*({[^;]+})",
                    ]

                    for pattern in config_patterns:
                        match = re.search(pattern, script_content, re.IGNORECASE | re.DOTALL)
                        if match:
                            try:
                                config_json = match.group(1)
                                # Try to parse as JSON
                                config_data = json.loads(config_json)
                                config_hints.update(self._extract_useful_params(config_data))
                                logger.debug("Found Avature config in scripts")
                            except (json.JSONDecodeError, ValueError):
                                # Try to extract key-value pairs manually
                                self._extract_key_value_pairs(script_content, config_hints)

                    # Look for API endpoint patterns
                    api_patterns = [
                        r"apiEndpoint\s*[:=]\s*['\"]([^'\"]+)['\"]",
                        r"apiUrl\s*[:=]\s*['\"]([^'\"]+)['\"]",
                        r"baseUrl\s*[:=]\s*['\"]([^'\"]+)['\"]",
                        r"endpoint\s*[:=]\s*['\"]([^'\"]+)['\"]",
                    ]

                    for pattern in api_patterns:
                        matches = re.findall(pattern, script_content, re.IGNORECASE)
                        if matches:
                            if "api_endpoints" not in config_hints:
                                config_hints["api_endpoints"] = []
                            config_hints["api_endpoints"].extend(matches)

                    # Look for pagination/page size hints
                    page_size_patterns = [
                        r"pageSize\s*[:=]\s*(\d+)",
                        r"page_size\s*[:=]\s*(\d+)",
                        r"itemsPerPage\s*[:=]\s*(\d+)",
                    ]

                    for pattern in page_size_patterns:
                        match = re.search(pattern, script_content, re.IGNORECASE)
                        if match:
                            page_size = int(match.group(1))
                            if "api_params" not in config_hints:
                                config_hints["api_params"] = {}
                            config_hints["api_params"]["pageSize"] = page_size

                return config_hints if config_hints else None

        except Exception as e:
            logger.debug(f"Error extracting config from scripts: {e}")
            return None

    def _extract_useful_params(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract useful parameters from config object.

        Args:
            config_data: Parsed config dictionary

        Returns:
            Dictionary with useful parameters
        """
        useful_params = {}
        api_params = {}

        # Look for API-related config
        api_keys = ["api", "apiUrl", "apiEndpoint", "baseUrl", "endpoint"]
        for key in api_keys:
            if key in config_data:
                value = config_data[key]
                if isinstance(value, str):
                    if "api_endpoints" not in useful_params:
                        useful_params["api_endpoints"] = []
                    useful_params["api_endpoints"].append(value)

        # Look for pagination config
        pagination_keys = ["pageSize", "page_size", "itemsPerPage", "limit"]
        for key in pagination_keys:
            if key in config_data:
                value = config_data[key]
                if isinstance(value, (int, str)):
                    try:
                        api_params["pageSize"] = int(value)
                    except (ValueError, TypeError):
                        pass

        # Look for other useful params
        if "api_params" not in useful_params:
            useful_params["api_params"] = {}
        useful_params["api_params"].update(api_params)

        return useful_params

    def _extract_key_value_pairs(
        self, script_content: str, config_hints: Dict[str, Any]
    ):
        """
        Extract key-value pairs from script content using regex.

        Args:
            script_content: Script content string
            config_hints: Dictionary to update with extracted values
        """
        # Look for API endpoint patterns
        api_pattern = r"(?:apiEndpoint|apiUrl|endpoint)\s*[:=]\s*['\"]([^'\"]+)['\"]"
        api_matches = re.findall(api_pattern, script_content, re.IGNORECASE)
        if api_matches:
            if "api_endpoints" not in config_hints:
                config_hints["api_endpoints"] = []
            config_hints["api_endpoints"].extend(api_matches)

        # Look for page size patterns
        page_size_pattern = r"(?:pageSize|page_size|itemsPerPage)\s*[:=]\s*(\d+)"
        page_size_match = re.search(page_size_pattern, script_content, re.IGNORECASE)
        if page_size_match:
            page_size = int(page_size_match.group(1))
            if "api_params" not in config_hints:
                config_hints["api_params"] = {}
            config_hints["api_params"]["pageSize"] = page_size

    def _prioritize_endpoints(
        self,
        endpoint_templates: List[tuple],
        config_hints: Optional[Dict[str, Any]],
    ) -> List[tuple]:
        """
        Prioritize endpoint templates based on config hints.

        Args:
            endpoint_templates: List of (method, path, requires_json) tuples
            config_hints: Optional config hints from script inspection

        Returns:
            Prioritized list of endpoint templates
        """
        if not config_hints or "api_endpoints" not in config_hints:
            return endpoint_templates

        # If we found API endpoints in config, prioritize matching paths
        api_endpoints = config_hints.get("api_endpoints", [])
        prioritized = []
        remaining = list(endpoint_templates)

        for api_endpoint in api_endpoints:
            # Extract path from full URL if needed
            if "/" in api_endpoint:
                path = "/" + "/".join(api_endpoint.split("/")[-2:])
            else:
                path = api_endpoint

            # Find matching templates
            for template in remaining[:]:
                _, template_path, _ = template
                if path.lower() in template_path.lower() or template_path.lower() in path.lower():
                    prioritized.append(template)
                    remaining.remove(template)

        # Add remaining templates
        prioritized.extend(remaining)
        return prioritized


def detect_endpoint(
    base_url: str, timeout: float = 15.0, inspect_scripts: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to detect endpoint for a base URL.

    Args:
        base_url: Base URL of the Avature careers site
        timeout: Request timeout in seconds
        inspect_scripts: Whether to inspect inline scripts for config (default: True)

    Returns:
        Config dict or None if no endpoint found
    """
    detector = EndpointDetector(timeout=timeout, inspect_scripts=inspect_scripts)
    return detector.detect(base_url)
