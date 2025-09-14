ETHICS and Responsible Scraping Guidelines

Purpose
This document lists high-level principles and mandatory checks before performing any scraping or mass ingestion of web content.

Principles
- Respect robots.txt and site-specific terms of service.
- Minimize harm: avoid overloading sites, avoid collecting or exposing PII.
- Be transparent: identify the collector via a clear User-Agent and provide contact info.
- Respect copyright and licensing: do not ingest or redistribute content in violation of stated licenses.
- Human oversight: require manual review for any automated ingestion affecting people or services.

Mandatory pre-scrape checks
- Whitelist/blacklist configuration present and reviewed.
- Legal review for target sites where commercial reuse might occur.
- Define retention and deletion policies for scraped data (PII removal timelines).
- Sandbox/isolated environment for any downstream execution of scraped code or running user content.
- Rate limiting and backoff configured per-domain.
- Recording of provenance (URL, timestamp, snapshot hash) for all ingested items.
- Incident response plan and an “emergency stop” mechanism.

Operational rules
- Do not execute arbitrary code snippets uncovered during scraping without explicit sandboxing and approval.
- Strip or redact PII by default; flag ambiguous cases for human review.
- Limit scraping volume for any single domain and provide contact details for site owners in case of issues.
- Keep logs for audit and reproducibility; rotate and protect logs to avoid leaking sensitive information.

Approval & escalation
- Any new scraper or major change requires at least one peer review and a short security/ethics signoff.
- For any legal, ethics, or takedown request, follow the repository’s CONTACT/SECURITY procedure and the emergency stop.
