"""
Job detail fetcher for Avature ATS sites.

Fetches full job details from detail pages or APIs to enrich job summary objects.
"""

from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from scraper.client import HTTPClient
from utils.logger import get_logger

logger = get_logger(__name__)


class JobDetailFetcher:
    """Fetches and enriches job details from detail pages or APIs."""

    # Common keys for job ID
    ID_KEYS = ["id", "jobId", "job_id", "requisitionId", "requisition_id", "positionId"]

    # Common keys for job URL
    URL_KEYS = [
        "url",
        "jobUrl",
        "job_url",
        "detailUrl",
        "detail_url",
        "link",
        "href",
        "applicationUrl",
    ]

    # Common detail URL patterns
    DETAIL_URL_PATTERNS = [
        "/job/{id}",
        "/jobs/{id}",
        "/careers/{id}",
        "/position/{id}",
        "/requisition/{id}",
        "/job-detail/{id}",
        "/job-details/{id}",
        "/api/job/{id}",
        "/api/jobs/{id}",
        "/services/JobDetail?id={id}",
    ]

    def __init__(self, timeout: float = 30.0):
        """
        Initialize job detail fetcher.

        Args:
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.timeout = timeout

    def enrich(
        self, job_summary: Dict[str, Any], base_url: str
    ) -> Dict[str, Any]:
        """
        Enrich job summary with full details.

        Args:
            job_summary: Job summary object from job list
            base_url: Base URL of the careers site

        Returns:
            Enriched job object (or original if enrichment fails)
        """
        # Create a copy to avoid mutating original
        enriched_job = job_summary.copy()

        # Try to find job ID or URL
        job_id = self._extract_job_id(job_summary)
        job_url = self._extract_job_url(job_summary)

        if not job_id and not job_url:
            logger.debug("No job ID or URL found, skipping detail fetch")
            return enriched_job

        # Try to fetch detail
        detail_data = self._fetch_detail(job_id, job_url, base_url)

        if detail_data:
            # Extract and add description
            description = self._extract_description(detail_data)
            if description:
                enriched_job["full_description"] = description
                enriched_job["description_html"] = isinstance(description, str) and (
                    "<" in description and ">" in description
                )

            # Extract and add application URL
            application_url = self._extract_application_url(detail_data, base_url)
            if application_url:
                enriched_job["application_url"] = application_url

            logger.debug(f"Successfully enriched job {job_id or 'unknown'}")
        else:
            logger.debug(f"Could not fetch details for job {job_id or 'unknown'}")

        return enriched_job

    def _extract_job_id(self, job: Dict[str, Any]) -> Optional[str]:
        """Extract job ID from job object."""
        for key in self.ID_KEYS:
            if key in job and job[key]:
                return str(job[key])
        return None

    def _extract_job_url(self, job: Dict[str, Any]) -> Optional[str]:
        """Extract job URL from job object."""
        for key in self.URL_KEYS:
            if key in job and job[key]:
                url = job[key]
                # If relative URL, return as-is (will be joined with base_url)
                # If absolute URL, return as-is
                return url
        return None

    def _fetch_detail(
        self, job_id: Optional[str], job_url: Optional[str], base_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch job detail from URL or API.

        Args:
            job_id: Job ID if available
            job_url: Job URL if available
            base_url: Base URL of the site

        Returns:
            Parsed detail data (dict for JSON, BeautifulSoup for HTML) or None
        """
        # Try direct URL first if available
        if job_url:
            detail = self._try_url(job_url, base_url)
            if detail:
                return detail

        # Try constructing URLs from job ID
        if job_id:
            # Try detail URL patterns
            for pattern in self.DETAIL_URL_PATTERNS:
                url = pattern.replace("{id}", str(job_id))
                full_url = urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))
                detail = self._try_url(full_url, base_url)
                if detail:
                    return detail

            # Try API endpoints
            api_patterns = [
                f"/api/job/{job_id}",
                f"/api/jobs/{job_id}",
                f"/services/JobDetail?id={job_id}",
            ]
            for pattern in api_patterns:
                full_url = urljoin(base_url.rstrip("/") + "/", pattern.lstrip("/"))
                detail = self._try_api(full_url)
                if detail:
                    return detail

        return None

    def _try_url(self, url: str, base_url: str) -> Optional[Any]:
        """
        Try to fetch and parse detail from a URL.

        Args:
            url: URL to fetch (may be relative or absolute)
            base_url: Base URL for joining relative URLs

        Returns:
            BeautifulSoup object for HTML, dict for JSON, or None
        """
        # Join with base URL if relative
        if not url.startswith(("http://", "https://")):
            url = urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))

        with HTTPClient(timeout=self.timeout) as client:
            response = client.get(url)
            if not response:
                return None

            content_type = response.headers.get("content-type", "").lower()

            # Try JSON first
            if "application/json" in content_type:
                try:
                    return response.json()
                except Exception:
                    pass

            # Try HTML
            if "text/html" in content_type:
                try:
                    return BeautifulSoup(response.text, "lxml")
                except Exception:
                    pass

            # Fallback: try to parse as HTML anyway
            try:
                return BeautifulSoup(response.text, "lxml")
            except Exception:
                pass

        return None

    def _try_api(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Try to fetch detail from API endpoint.

        Args:
            url: API endpoint URL

        Returns:
            Parsed JSON response or None
        """
        with HTTPClient(timeout=self.timeout) as client:
            headers = {"Content-Type": "application/json"}
            response = client.get(url, headers=headers)
            if not response:
                return None

            try:
                return response.json()
            except Exception:
                return None

    def _extract_description(self, detail_data: Any) -> Optional[str]:
        """
        Extract full job description from detail data.

        Args:
            detail_data: BeautifulSoup object (HTML) or dict (JSON)

        Returns:
            Description text/HTML or None
        """
        if isinstance(detail_data, dict):
            # Try common JSON keys for description
            desc_keys = [
                "description",
                "fullDescription",
                "full_description",
                "jobDescription",
                "job_description",
                "details",
                "content",
                "body",
                "text",
            ]
            for key in desc_keys:
                if key in detail_data and detail_data[key]:
                    return str(detail_data[key])

            # Try nested structures
            if "data" in detail_data and isinstance(detail_data["data"], dict):
                return self._extract_description(detail_data["data"])

        elif hasattr(detail_data, "find"):  # BeautifulSoup object
            # Try common HTML selectors for job description
            selectors = [
                '[class*="description"]',
                '[class*="detail"]',
                '[id*="description"]',
                '[id*="detail"]',
                ".job-description",
                ".job-detail",
                ".description",
                ".details",
                "#description",
                "#details",
                "article",
                ".content",
            ]

            for selector in selectors:
                try:
                    element = detail_data.select_one(selector)
                    if element:
                        # Get inner HTML
                        return str(element)
                except Exception:
                    continue

            # Fallback: try to find main content area
            try:
                main = detail_data.find("main") or detail_data.find("article")
                if main:
                    return str(main)
            except Exception:
                pass

        return None

    def _extract_application_url(
        self, detail_data: Any, base_url: str
    ) -> Optional[str]:
        """
        Extract application URL from detail data.

        Args:
            detail_data: BeautifulSoup object (HTML) or dict (JSON)
            base_url: Base URL for joining relative URLs

        Returns:
            Application URL or None
        """
        if isinstance(detail_data, dict):
            # Try common JSON keys for application URL
            app_keys = [
                "applyUrl",
                "apply_url",
                "applicationUrl",
                "application_url",
                "applyLink",
                "apply_link",
                "url",
                "link",
            ]
            for key in app_keys:
                if key in detail_data and detail_data[key]:
                    url = str(detail_data[key])
                    # Make absolute if relative
                    if not url.startswith(("http://", "https://")):
                        url = urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))
                    return url

        elif hasattr(detail_data, "find"):  # BeautifulSoup object
            # Look for apply/application buttons/links
            apply_selectors = [
                'a[href*="apply"]',
                'a[href*="application"]',
                'a[class*="apply"]',
                'a[id*="apply"]',
                'button[onclick*="apply"]',
                ".apply-button",
                ".apply-btn",
                "#apply",
            ]

            for selector in apply_selectors:
                try:
                    element = detail_data.select_one(selector)
                    if element:
                        href = element.get("href") or element.get("data-href")
                        if href:
                            # Make absolute if relative
                            if not href.startswith(("http://", "https://")):
                                href = urljoin(
                                    base_url.rstrip("/") + "/", href.lstrip("/")
                                )
                            return href
                except Exception:
                    continue

        return None


def enrich_job(
    job_summary: Dict[str, Any], base_url: str, timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Convenience function to enrich a job summary with details.

    Args:
        job_summary: Job summary object from job list
        base_url: Base URL of the careers site
        timeout: Request timeout in seconds

    Returns:
        Enriched job object (or original if enrichment fails)
    """
    fetcher = JobDetailFetcher(timeout=timeout)
    return fetcher.enrich(job_summary, base_url)
