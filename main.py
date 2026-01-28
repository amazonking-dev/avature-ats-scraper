"""
Main entry point for the Avature scraper project.

Loads sites from input file and runs the complete scraping pipeline.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from scraper.pipeline import ScrapingPipeline
from utils.logger import get_logger

logger = get_logger(__name__)


def load_sites(input_file: str = "input/avature_sites.txt") -> List[str]:
    """
    Load site URLs from input file.

    Args:
        input_file: Path to input file containing site URLs

    Returns:
        List of site URLs (non-empty, non-comment lines)
    """
    input_path = Path(input_file)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_file}")
        logger.info("Please create input/avature_sites.txt with one URL per line")
        return []

    sites = []
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Basic URL validation
                if not line.startswith(("http://", "https://")):
                    logger.warning(
                        f"Line {line_num}: '{line}' doesn't look like a URL, skipping"
                    )
                    continue

                sites.append(line)

        logger.info(f"Loaded {len(sites)} site(s) from {input_file}")
        return sites

    except Exception as e:
        logger.error(f"Error reading input file {input_file}: {e}")
        return []


def save_jobs(jobs: List[Dict[str, Any]], output_file: str = "output/jobs.json"):
    """
    Save jobs to JSON file.

    Args:
        jobs: List of normalized job objects
        output_file: Path to output JSON file
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(jobs)} job(s) to {output_file}")

    except Exception as e:
        logger.error(f"Error saving jobs to {output_file}: {e}")
        raise


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("Avature ATS Scraper - Starting")
    logger.info("=" * 60)

    # Load sites from input file
    sites = load_sites("input/avature_sites.txt")

    if not sites:
        logger.error("No sites to scrape. Exiting.")
        sys.exit(1)

    # Initialize pipeline
    logger.info("Initializing scraping pipeline...")
    pipeline = ScrapingPipeline(
        timeout=30.0,
        enrich_details=True,
        output_dir="output",
    )

    # Scrape all sites
    logger.info(f"Starting scrape for {len(sites)} site(s)...")
    logger.info("-" * 60)

    try:
        all_jobs = pipeline.scrape_sites(sites)

        logger.info("-" * 60)
        logger.info(f"Scraping completed. Total unique jobs: {len(all_jobs)}")

        # Save jobs to JSON
        if all_jobs:
            save_jobs(all_jobs, "output/jobs.json")
            logger.info("Jobs saved successfully")
        else:
            logger.warning("No jobs were scraped. Check logs for details.")

        # Summary
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Sites processed: {len(sites)}")
        logger.info(f"  Total jobs scraped: {len(all_jobs)}")
        logger.info(f"  Jobs saved to: output/jobs.json")
        logger.info(f"  Stats saved to: output/site_stats.csv")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.warning("\nScraping interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error during scraping: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
