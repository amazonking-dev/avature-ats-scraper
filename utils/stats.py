"""
Statistics tracking and reporting for site scraping.

Tracks per-site stats and writes to CSV file.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from utils.logger import get_logger

logger = get_logger(__name__)


class SiteStatsTracker:
    """Tracks statistics for each site scraped."""

    CSV_HEADERS = [
        "site_url",
        "timestamp",
        "status",
        "total_jobs_scraped",
        "endpoint_used",
        "error_message",
    ]

    def __init__(self, output_dir: str = "output"):
        """
        Initialize stats tracker.

        Args:
            output_dir: Directory to write stats CSV file
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.stats_file = self.output_dir / "site_stats.csv"
        self._ensure_csv_header()

    def record_site(
        self,
        site_url: str,
        status: str,
        total_jobs_scraped: int = 0,
        endpoint_used: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """
        Record statistics for a site.

        Args:
            site_url: URL of the site scraped
            status: "success" or "failure"
            total_jobs_scraped: Number of jobs scraped
            endpoint_used: Endpoint URL that was used
            error_message: Error message if status is "failure"
        """
        timestamp = datetime.now().isoformat()

        row = {
            "site_url": site_url,
            "timestamp": timestamp,
            "status": status,
            "total_jobs_scraped": str(total_jobs_scraped),
            "endpoint_used": endpoint_used or "",
            "error_message": error_message or "",
        }

        try:
            with open(self.stats_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                writer.writerow(row)

            logger.info(
                f"Recorded stats for {site_url}: {status}, {total_jobs_scraped} jobs"
            )
        except Exception as e:
            logger.error(f"Error writing stats to CSV: {e}")

    def _ensure_csv_header(self):
        """Ensure CSV file exists with headers."""
        if not self.stats_file.exists():
            try:
                with open(self.stats_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                    writer.writeheader()
            except Exception as e:
                logger.error(f"Error creating stats CSV file: {e}")

    def get_all_stats(self) -> List[Dict[str, str]]:
        """
        Read all stats from CSV file.

        Returns:
            List of stats dictionaries
        """
        stats = []
        if not self.stats_file.exists():
            return stats

        try:
            with open(self.stats_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                stats = list(reader)
        except Exception as e:
            logger.error(f"Error reading stats CSV: {e}")

        return stats


def create_stats_tracker(output_dir: str = "output") -> SiteStatsTracker:
    """
    Create a stats tracker instance.

    Args:
        output_dir: Directory to write stats CSV file

    Returns:
        SiteStatsTracker instance
    """
    return SiteStatsTracker(output_dir=output_dir)
