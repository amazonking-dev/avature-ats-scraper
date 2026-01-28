# Avature ATS Scraper

A production-grade web scraper for extracting job postings from Avature ATS-powered career sites. Designed with coverage-first principles to handle the diverse implementations across Avature's client base.

## Overview

This scraper addresses the challenge of extracting job data from Avature ATS sites, which exhibit significant variation in API endpoints, response schemas, and pagination strategies. Rather than hardcoding site-specific logic, the system employs adaptive detection and heuristic validation to maximize coverage across different implementations.

**Key Features:**
- Automatic endpoint detection with script inspection
- Multi-strategy pagination handling
- Opportunistic job detail enrichment
- Canonical schema normalization
- Cross-site deduplication
- Per-site statistics tracking

## Architecture

### Project Structure

```
avature-scraper/
├── main.py                    # Entry point and orchestration
├── input/
│   └── avature_sites.txt      # Site URLs (one per line)
├── output/
│   ├── jobs.json              # Normalized job data
│   └── site_stats.csv         # Per-site scraping statistics
├── scraper/
│   ├── client.py              # Reusable HTTP client
│   ├── endpoint_detector.py   # Endpoint discovery and validation
│   ├── job_list.py            # Paginated job fetching
│   ├── job_detail.py          # Optional detail enrichment
│   ├── normalizer.py          # Schema normalization
│   └── pipeline.py            # End-to-end orchestration
└── utils/
    ├── deduplicator.py        # Job deduplication logic
    ├── logger.py              # Logging configuration
    └── stats.py               # Statistics tracking
```

## Avature Site Discovery Strategy

Sites are loaded from `input/avature_sites.txt` (one URL per line). The system processes each site independently, allowing partial success when some sites fail. Comments and empty lines are automatically skipped.

**Input Format:**
```
https://careers.example.com
https://jobs.company.com
# https://old-site.com  # Commented out
```

## Endpoint Detection Approach

The endpoint detector employs a multi-phase strategy to maximize success rate:

### Phase 1: Script Inspection (Optional)
- Fetches the careers page HTML
- Parses inline scripts and JS bundles
- Extracts configuration objects (e.g., `window.__AVATURE_CONFIG__`)
- Identifies API endpoints, pagination parameters, and other hints
- **Non-breaking**: Failures are logged but don't interrupt detection

### Phase 2: Template Matching
Tests common Avature endpoint patterns:
- `POST /services/JobSearch`
- `POST /careers/SearchJobs`
- `GET /api/jobs`
- `GET /api/v1/jobs`
- `POST /api/jobs/search`
- `GET /careers/api/jobs`

If script inspection found hints, matching endpoints are prioritized.

### Phase 3: Heuristic Validation
Each candidate endpoint is validated by:
1. **Content-Type check**: Must return JSON
2. **Schema detection**: Recursively searches for job-related fields (`jobId`, `title`, `jobs`, `requisitions`, etc.)
3. **Pagination inference**: Detects pagination type (page-based, offset-based, cursor-based)
4. **Response structure**: Extracts top-level schema keys

Only endpoints that pass validation are returned. This prevents false positives from error pages or unrelated APIs.

## Data Extraction and Normalization

### Extraction Pipeline

1. **Job List Fetching** (`job_list.py`)
   - Handles three pagination strategies:
     - **Page-based**: Increments page number until empty results
     - **Offset-based**: Uses offset/limit until fewer results than limit
     - **Cursor-based**: Follows cursor tokens until exhausted
   - Logs progress per page for monitoring
   - Gracefully handles pagination edge cases

2. **Detail Enrichment** (`job_detail.py`)
   - **Opportunistic**: Attempts to fetch full job details but continues if unavailable
   - Tries multiple URL patterns and API endpoints
   - Extracts full HTML description and application URLs
   - Returns original job object if enrichment fails (never breaks pipeline)

3. **Normalization** (`normalizer.py`)
   - Maps diverse field names to canonical schema:
     - `job_id`: From `id`, `jobId`, `requisitionId`, etc.
     - `title`: From `title`, `jobTitle`, `name`, etc.
     - `description_html` / `description_text`: HTML cleaned to text
     - `location`: From `location`, `city`, `workLocation`, etc.
     - `date_posted`: Normalized to ISO-8601 (YYYY-MM-DD)
     - `apply_url`: From `applyUrl`, `applicationUrl`, etc.
     - `source_site`: Extracted from URLs or provided explicitly
   - Handles missing fields safely (returns `None` or empty string)
   - Converts HTML to readable text using BeautifulSoup (no external text cleaning libraries)

4. **Deduplication** (`deduplicator.py`)
   - Uses SHA256 hash of `(title + location + source_site)`
   - Preserves jobs from different sites even if title/location match
   - Tracks seen hashes across all sites

## Coverage-First Design Decisions

### 1. Heuristic Over Hardcoding
Rather than maintaining site-specific configurations, the system uses pattern matching and heuristics. This trades some precision for broader coverage and lower maintenance.

### 2. Graceful Degradation
- Endpoint detection failures don't crash the pipeline
- Missing job details don't prevent normalization
- Invalid dates return `None` rather than causing errors
- Each component handles errors independently

### 3. Opportunistic Enrichment
Job detail fetching is optional and non-blocking. If a site doesn't expose detail endpoints, the scraper still extracts available summary data.

### 4. Schema Flexibility
The normalizer handles multiple field name variations, allowing the same code to work across different Avature implementations without modification.

### 5. Statistics Tracking
Every site scrape is logged with success/failure status, endpoint used, and job count. This enables monitoring and debugging without requiring code changes.

## Edge Cases and Tradeoffs

### Edge Cases Handled

1. **Missing Endpoints**: Returns `None` and logs failure, allowing other sites to proceed
2. **Empty Job Lists**: Detected during pagination and stops gracefully
3. **Non-Standard Pagination**: Falls back to single-page fetch with warning
4. **Malformed Dates**: Returns `None` instead of crashing; supports relative dates ("2 days ago")
5. **Missing Fields**: All fields are optional; missing values become `None` or empty strings
6. **Duplicate Jobs**: Deduplicated using content hash, preserving cross-site uniqueness
7. **Script Inspection Failures**: Logged at debug level, detection continues normally

### Tradeoffs

| Decision | Benefit | Cost |
|----------|---------|------|
| Heuristic validation | Works across diverse sites | May miss edge cases |
| Opportunistic enrichment | Doesn't break on missing details | Some jobs lack full descriptions |
| Template-based endpoints | Broad coverage | May try unnecessary endpoints |
| Single deduplicator instance | Cross-site deduplication | Can't distinguish same job on different sites |
| Script inspection optional | Faster when disabled | May miss optimal endpoints |

## How to Run

### Prerequisites

- Python 3.9+
- Virtual environment (recommended)

### Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Add site URLs to `input/avature_sites.txt` (one per line):
   ```
   https://careers.example.com
   https://jobs.company.com
   ```

2. (Optional) Adjust settings in `main.py`:
   - Timeout values
   - Enable/disable detail enrichment
   - Output directory

### Execution

```bash
python main.py
```

### Output

- **`output/jobs.json`**: Array of normalized job objects with canonical schema
- **`output/site_stats.csv`**: Per-site statistics including:
  - Site URL
  - Timestamp
  - Status (success/failure)
  - Total jobs scraped
  - Endpoint used
  - Error message (if failed)

### Example Output Schema

```json
{
  "job_id": "12345",
  "title": "Software Engineer",
  "description_html": "<p>Job description...</p>",
  "description_text": "Job description...",
  "location": "San Francisco, CA",
  "date_posted": "2024-01-15",
  "apply_url": "https://careers.example.com/apply/12345",
  "source_site": "https://careers.example.com"
}
```

## Time Spent

**Estimated Development Time**: ~8-10 hours

- Project scaffolding: 30 minutes
- HTTP client and logging: 1 hour
- Endpoint detection: 2 hours
- Job list fetching with pagination: 1.5 hours
- Job detail enrichment: 1 hour
- Normalization and deduplication: 1.5 hours
- Pipeline orchestration: 1 hour
- Script inspection enhancement: 1 hour
- Testing and refinement: 1 hour

## Future Improvements

### Short-term
- **Retry logic**: Add exponential backoff for transient failures
- **Rate limiting**: Respect site rate limits and add delays
- **Parallel processing**: Scrape multiple sites concurrently
- **Incremental updates**: Track last scrape time and only fetch new jobs
- **Better date parsing**: Support more date formats and timezones

### Medium-term
- **Machine learning**: Train model to identify job-related fields
- **Schema learning**: Automatically learn field mappings from examples
- **Endpoint caching**: Cache detected endpoints to avoid re-detection
- **Webhook support**: Real-time job updates via webhooks
- **Database backend**: Store jobs in database instead of JSON

### Long-term
- **Multi-ATS support**: Extend to other ATS platforms
- **API-first approach**: Prefer official APIs when available
- **Distributed scraping**: Scale across multiple machines
- **Monitoring dashboard**: Real-time scraping metrics and alerts
- **Self-healing**: Automatically adapt to site changes

## Dependencies

- `httpx>=0.26` - HTTP client with sync/async support
- `beautifulsoup4>=4.12` - HTML parsing
- `lxml>=5.0` - Fast XML/HTML parser
- `tenacity>=8.2` - Retry logic (available but not yet integrated)

## License

[Specify license here]
