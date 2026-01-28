"""
Job deduplication utility.

Deduplicates jobs using a hash of (title + location + source_site).
"""

import hashlib
from typing import List, Dict, Any, Set


class JobDeduplicator:
    """Deduplicates jobs based on title, location, and source site."""

    def __init__(self):
        """Initialize deduplicator with empty seen set."""
        self.seen_hashes: Set[str] = set()

    def deduplicate(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate jobs from list.

        Args:
            jobs: List of job objects (normalized or raw)

        Returns:
            List of unique jobs
        """
        unique_jobs = []
        duplicates_count = 0

        for job in jobs:
            job_hash = self._compute_hash(job)
            if job_hash not in self.seen_hashes:
                self.seen_hashes.add(job_hash)
                unique_jobs.append(job)
            else:
                duplicates_count += 1

        if duplicates_count > 0:
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.info(f"Removed {duplicates_count} duplicate job(s)")

        return unique_jobs

    def _compute_hash(self, job: Dict[str, Any]) -> str:
        """
        Compute hash for a job based on title, location, and source_site.

        Args:
            job: Job object

        Returns:
            SHA256 hash as hex string
        """
        # Extract fields (handle both normalized and raw jobs)
        title = self._get_field(job, ["title", "jobTitle", "job_title", "name"])
        location = self._get_field(job, ["location", "city", "cityState", "workLocation"])
        source_site = self._get_field(job, ["source_site", "sourceSite", "site"])

        # Normalize values for hashing
        title = (title or "").lower().strip()
        location = (location or "").lower().strip()
        source_site = (source_site or "").lower().strip()

        # Create hash string
        hash_string = f"{title}|{location}|{source_site}"

        # Compute SHA256 hash
        return hashlib.sha256(hash_string.encode("utf-8")).hexdigest()

    def _get_field(self, job: Dict[str, Any], field_names: List[str]) -> str:
        """
        Get field value from job using multiple possible field names.

        Args:
            job: Job object
            field_names: List of possible field names to try

        Returns:
            Field value or empty string
        """
        for field_name in field_names:
            if field_name in job and job[field_name]:
                return str(job[field_name])
        return ""

    def reset(self):
        """Reset the seen hashes set."""
        self.seen_hashes.clear()


def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convenience function to deduplicate jobs.

    Args:
        jobs: List of job objects

    Returns:
        List of unique jobs
    """
    deduplicator = JobDeduplicator()
    return deduplicator.deduplicate(jobs)
