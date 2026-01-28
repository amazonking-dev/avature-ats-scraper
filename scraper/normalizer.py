"""
Job data normalizer for Avature ATS sites.

Converts raw job data into a canonical schema with consistent field names and formats.
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from utils.logger import get_logger

logger = get_logger(__name__)


class JobNormalizer:
    """Normalizes raw job data into canonical schema."""

    # Field mapping: canonical_field -> list of possible source field names
    FIELD_MAPPINGS = {
        "job_id": [
            "id",
            "jobId",
            "job_id",
            "requisitionId",
            "requisition_id",
            "positionId",
            "position_id",
            "jobNumber",
            "job_number",
        ],
        "title": [
            "title",
            "jobTitle",
            "job_title",
            "name",
            "position",
            "positionTitle",
            "position_title",
        ],
        "description_html": [
            "full_description",
            "description",
            "fullDescription",
            "jobDescription",
            "job_description",
            "details",
            "content",
            "body",
            "text",
        ],
        "location": [
            "location",
            "city",
            "cityState",
            "city_state",
            "address",
            "workLocation",
            "work_location",
            "officeLocation",
            "office_location",
        ],
        "date_posted": [
            "datePosted",
            "date_posted",
            "postedDate",
            "posted_date",
            "createdDate",
            "created_date",
            "publishDate",
            "publish_date",
            "posted",
            "created",
            "date",
        ],
        "apply_url": [
            "application_url",
            "applyUrl",
            "apply_url",
            "applicationUrl",
            "url",
            "jobUrl",
            "job_url",
            "link",
            "href",
        ],
    }

    def __init__(self, source_site: Optional[str] = None):
        """
        Initialize job normalizer.

        Args:
            source_site: Source site URL (will be extracted from job data if not provided)
        """
        self.source_site = source_site

    def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize raw job data into canonical schema.

        Args:
            raw_job: Raw job object from scraper

        Returns:
            Normalized job object with canonical schema
        """
        normalized = {}

        # Extract source site
        source_site = self.source_site or self._extract_source_site(raw_job)
        normalized["source_site"] = source_site

        # Map each canonical field
        normalized["job_id"] = self._extract_field(raw_job, "job_id")
        normalized["title"] = self._extract_field(raw_job, "title")
        normalized["location"] = self._extract_field(raw_job, "location")
        normalized["apply_url"] = self._extract_field(raw_job, "apply_url")

        # Handle description (HTML and text)
        description_html = self._extract_field(raw_job, "description_html")
        normalized["description_html"] = description_html
        normalized["description_text"] = self._html_to_text(description_html)

        # Handle date
        normalized["date_posted"] = self._normalize_date(
            self._extract_field(raw_job, "date_posted")
        )

        return normalized

    def _extract_field(self, raw_job: Dict[str, Any], canonical_field: str) -> Optional[str]:
        """
        Extract field value using field mappings.

        Args:
            raw_job: Raw job object
            canonical_field: Canonical field name

        Returns:
            Field value or None if not found
        """
        if canonical_field not in self.FIELD_MAPPINGS:
            return None

        # Try each possible source field name
        for source_field in self.FIELD_MAPPINGS[canonical_field]:
            if source_field in raw_job:
                value = raw_job[source_field]
                if value is not None:
                    return str(value).strip() if isinstance(value, str) else str(value)

        return None

    def _extract_source_site(self, raw_job: Dict[str, Any]) -> str:
        """
        Extract source site URL from job data.

        Args:
            raw_job: Raw job object

        Returns:
            Source site URL or empty string
        """
        # Try common URL fields
        url_fields = ["url", "jobUrl", "apply_url", "application_url", "source_site"]
        for field in url_fields:
            if field in raw_job and raw_job[field]:
                url = str(raw_job[field])
                try:
                    parsed = urlparse(url)
                    if parsed.netloc:
                        scheme = parsed.scheme or "https"
                        return f"{scheme}://{parsed.netloc}"
                except Exception:
                    pass

        return ""

    def _html_to_text(self, html: Optional[str]) -> str:
        """
        Convert HTML to clean text without third-party libraries.

        Args:
            html: HTML string or None

        Returns:
            Clean text string
        """
        if not html:
            return ""

        # If it doesn't look like HTML, return as-is
        if not isinstance(html, str) or ("<" not in html and ">" not in html):
            return html.strip()

        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html, "lxml")

            # Remove script and style elements
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()

            # Get text
            text = soup.get_text(separator=" ", strip=True)

            # Clean up whitespace
            text = re.sub(r"\s+", " ", text)  # Multiple spaces to single space
            text = re.sub(r"\n\s*\n", "\n\n", text)  # Multiple newlines to double newline
            text = text.strip()

            return text

        except Exception as e:
            logger.debug(f"Error converting HTML to text: {e}")
            # Fallback: simple regex-based cleaning
            text = re.sub(r"<[^>]+>", "", html)  # Remove HTML tags
            text = re.sub(r"\s+", " ", text)  # Clean whitespace
            return text.strip()

    def _normalize_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Normalize date string to ISO-8601 format.

        Args:
            date_str: Date string in various formats

        Returns:
            ISO-8601 date string (YYYY-MM-DD) or None if parsing fails
        """
        if not date_str:
            return None

        # Convert to string and clean
        date_str = str(date_str).strip()
        if not date_str:
            return None

        # Common date formats to try
        date_formats = [
            "%Y-%m-%d",  # ISO format
            "%Y-%m-%dT%H:%M:%S",  # ISO with time
            "%Y-%m-%dT%H:%M:%SZ",  # ISO with time and Z
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with microseconds and Z
            "%Y-%m-%d %H:%M:%S",  # Space-separated
            "%m/%d/%Y",  # US format
            "%d/%m/%Y",  # European format
            "%d-%m-%Y",  # European with dashes
            "%B %d, %Y",  # "January 1, 2024"
            "%b %d, %Y",  # "Jan 1, 2024"
            "%d %B %Y",  # "1 January 2024"
            "%d %b %Y",  # "1 Jan 2024"
            "%Y/%m/%d",  # Alternative ISO-like
        ]

        # Try parsing with each format
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Return ISO-8601 date format (YYYY-MM-DD)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Try parsing as Unix timestamp (if numeric)
        try:
            timestamp = float(date_str)
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass

        # Try parsing relative dates (e.g., "2 days ago", "1 week ago")
        relative_match = re.match(
            r"(\d+)\s*(day|days|week|weeks|month|months|year|years)\s*ago",
            date_str.lower(),
        )
        if relative_match:
            try:
                from datetime import timedelta

                amount = int(relative_match.group(1))
                unit = relative_match.group(2).rstrip("s")  # Remove plural

                if unit == "day":
                    delta = timedelta(days=amount)
                elif unit == "week":
                    delta = timedelta(weeks=amount)
                elif unit == "month":
                    delta = timedelta(days=amount * 30)  # Approximate
                elif unit == "year":
                    delta = timedelta(days=amount * 365)  # Approximate
                else:
                    return None

                dt = datetime.now() - delta
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        logger.debug(f"Could not parse date: {date_str}")
        return None


def normalize_job(
    raw_job: Dict[str, Any], source_site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to normalize a job object.

    Args:
        raw_job: Raw job object from scraper
        source_site: Optional source site URL

    Returns:
        Normalized job object with canonical schema
    """
    normalizer = JobNormalizer(source_site=source_site)
    return normalizer.normalize(raw_job)


def normalize_jobs(
    raw_jobs: list[Dict[str, Any]], source_site: Optional[str] = None
) -> list[Dict[str, Any]]:
    """
    Normalize a list of job objects.

    Args:
        raw_jobs: List of raw job objects
        source_site: Optional source site URL

    Returns:
        List of normalized job objects
    """
    normalizer = JobNormalizer(source_site=source_site)
    return [normalizer.normalize(job) for job in raw_jobs]
