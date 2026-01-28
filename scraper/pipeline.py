"""
Main scraping pipeline for Avature ATS sites.

Orchestrates endpoint detection, job fetching, enrichment, normalization,
deduplication, and statistics tracking.
"""

from typing import List, Dict, Any, Optional
from scraper.endpoint_detector import detect_endpoint
from scraper.job_list import fetch_jobs
from scraper.job_detail import enrich_job
from scraper.normalizer import normalize_job
from utils.deduplicator import JobDeduplicator
from utils.stats import SiteStatsTracker
from utils.logger import get_logger

logger = get_logger(__name__)


class ScrapingPipeline:
    """Main pipeline for scraping Avature ATS sites."""

    def __init__(
        self,
        timeout: float = 30.0,
        enrich_details: bool = True,
        output_dir: str = "output",
    ):
        """
        Initialize scraping pipeline.

        Args:
            timeout: Request timeout in seconds
            enrich_details: Whether to fetch full job details
            output_dir: Directory for output files
        """
        self.timeout = timeout
        self.enrich_details = enrich_details
        self.deduplicator = JobDeduplicator()
        self.stats_tracker = SiteStatsTracker(output_dir=output_dir)

    def scrape_site(self, site_url: str) -> List[Dict[str, Any]]:
        """
        Scrape a single site and return normalized jobs.

        Args:
            site_url: Base URL of the Avature careers site

        Returns:
            List of normalized, deduplicated job objects
        """
        logger.info(f"Starting scrape for {site_url}")

        endpoint_config = None
        raw_jobs = []
        normalized_jobs = []

        try:
            # Step 1: Detect endpoint
            logger.info(f"Detecting endpoint for {site_url}")
            endpoint_config = detect_endpoint(site_url, timeout=self.timeout)

            if not endpoint_config:
                logger.warning(f"No endpoint detected for {site_url}")
                self.stats_tracker.record_site(
                    site_url=site_url,
                    status="failure",
                    error_message="No endpoint detected",
                )
                return []

            endpoint_url = endpoint_config.get("endpoint", "")
            logger.info(f"Detected endpoint: {endpoint_url}")

            # Step 2: Fetch job list
            logger.info(f"Fetching job list from {endpoint_url}")
            raw_jobs = fetch_jobs(site_url, endpoint_config, timeout=self.timeout)

            if not raw_jobs:
                logger.warning(f"No jobs found for {site_url}")
                self.stats_tracker.record_site(
                    site_url=site_url,
                    status="success",
                    total_jobs_scraped=0,
                    endpoint_used=endpoint_url,
                )
                return []

            logger.info(f"Fetched {len(raw_jobs)} raw jobs")

            # Step 3: Enrich with details (optional)
            if self.enrich_details:
                logger.info("Enriching jobs with full details")
                enriched_jobs = []
                for i, job in enumerate(raw_jobs, 1):
                    if i % 10 == 0:
                        logger.debug(f"Enriched {i}/{len(raw_jobs)} jobs")
                    enriched_job = enrich_job(job, site_url, timeout=self.timeout)
                    enriched_jobs.append(enriched_job)
                raw_jobs = enriched_jobs

            # Step 4: Normalize jobs
            logger.info("Normalizing jobs")
            normalized_jobs = [
                normalize_job(job, source_site=site_url) for job in raw_jobs
            ]

            # Step 5: Deduplicate
            logger.info("Deduplicating jobs")
            normalized_jobs = self.deduplicator.deduplicate(normalized_jobs)

            # Step 6: Record success stats
            self.stats_tracker.record_site(
                site_url=site_url,
                status="success",
                total_jobs_scraped=len(normalized_jobs),
                endpoint_used=endpoint_url,
            )

            logger.info(
                f"Successfully scraped {len(normalized_jobs)} unique jobs from {site_url}"
            )

            return normalized_jobs

        except Exception as e:
            logger.error(f"Error scraping {site_url}: {e}", exc_info=True)
            self.stats_tracker.record_site(
                site_url=site_url,
                status="failure",
                total_jobs_scraped=len(normalized_jobs),
                endpoint_used=endpoint_config.get("endpoint", "") if endpoint_config else "",
                error_message=str(e),
            )
            return normalized_jobs

    def scrape_sites(self, site_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape multiple sites and return all normalized jobs.

        Args:
            site_urls: List of base URLs of Avature careers sites

        Returns:
            List of all normalized, deduplicated job objects
        """
        all_jobs = []

        for site_url in site_urls:
            site_url = site_url.strip()
            if not site_url or site_url.startswith("#"):
                continue

            jobs = self.scrape_site(site_url)
            all_jobs.extend(jobs)

            # Reset deduplicator between sites to allow same job from different sites
            # (or keep it to deduplicate across all sites)
            # For now, keeping it to deduplicate across all sites

        return all_jobs

    def reset_deduplicator(self):
        """Reset the deduplicator's seen hashes."""
        self.deduplicator.reset()
