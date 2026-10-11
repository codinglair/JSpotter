#!/usr/bin/env python3
"""
LinkedIn Jobs Search Pipeline — browser-based, no login required.

Searches LinkedIn Jobs for configured roles in two modes:
  1. Configured local searches
  2. Remote in USA

Extracts job listings via JavaScript, outputs CSV + Markdown.

Usage:
  python3 search_linkedin.py              # search local + remote
  python3 search_linkedin.py --local       # configured local only
  python3 search_linkedin.py --remote      # Remote only
  python3 search_linkedin.py --keywords "senior java engineer"
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from profile_support import add_profile_argument, configured_path, load_profile_config, safe_output_path

# LinkedIn Jobs search URL template
# f_WT=2 = Remote filter, sortBy=DD = Date posted (newest first)
LINKEDIN_SEARCH = "https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}{remote_filter}&sortBy=DD"

# JavaScript to extract job listings from the page
EXTRACT_JS = r"""
JSON.stringify(
  Array.from(document.querySelectorAll('li[data-occludable-job-id]'))
    .map(card => {
      const jobId = card.dataset.occludableJobId;
      const titleLink = card.querySelector('a.job-card-list__title--link');
      const title = (titleLink?.getAttribute('aria-label') || '')
        .replace(/\s+with verification\s*$/i, '')
        .trim();
      const company = card.querySelector('.artdeco-entity-lockup__subtitle')?.textContent?.trim() || '';
      const location = card.querySelector('.artdeco-entity-lockup__caption li span[dir="ltr"]')?.textContent?.trim() || '';
      const url = jobId ? `https://www.linkedin.com/jobs/view/${jobId}/` : '';
      return {title, company, location, url};
    })
    .filter(j => j.title && j.url)
    .filter((job, index, jobs) => jobs.findIndex(candidate => candidate.url === job.url) === index)
)
"""

# JavaScript to dismiss sign-in dialog
DISMISS_JS = """
(() => {
  const btn = document.querySelector('button[aria-label="Dismiss"], button[type="button"]');
  const dialogs = document.querySelectorAll('[role="dialog"]');
  for (const d of dialogs) {
    const dismissBtn = d.querySelector('button');
    if (dismissBtn && (dismissBtn.textContent.includes('Dismiss') || dismissBtn.textContent.includes('×'))) {
      dismissBtn.click();
      return 'dismissed';
    }
  }
  return 'no dialog';
})()
"""

# JavaScript to click "See more jobs" button
SEE_MORE_JS = """
(() => {
  const btn = document.querySelector('button[aria-label="See more jobs"]');
  if (btn) { btn.click(); return 'clicked'; }
  return 'no button';
})()
"""

# JavaScript to get current job count
COUNT_JS = "document.querySelectorAll('li[data-occludable-job-id]').length"

# JavaScript to scroll the job results list
SCROLL_JS = """
(() => {
  const list = document.querySelector('.jobs-search-results-list, .scaffold-layout__list-container, [class*="jobs-search-results"]');
  if (list) { list.scrollTop = list.scrollHeight; return 'scrolled list'; }
  window.scrollTo(0, document.body.scrollHeight);
  return 'scrolled window';
})()
"""


def run_applescript(script):
    """Run an AppleScript command and return output."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip(), result.stderr.strip()


def extract_jobs_from_browser():
    """
    Extract jobs from the currently loaded LinkedIn page in the Hermes browser.
    Uses the browser_console tool via subprocess to call the Hermes API.
    Since we can't call browser tools from Python directly, we use a different approach:
    we'll write results to a temp file via JavaScript and read it.
    
    Actually — this script is designed to be orchestrated BY the Hermes agent.
    The agent will:
    1. Navigate to LinkedIn search URL
    2. Dismiss sign-in dialog
    3. Scroll to load results
    4. Run extract JS
    5. Save results
    
    This script handles the orchestration logic and output formatting.
    The actual browser interaction is done by the agent calling browser tools.
    """
    pass


def load_config(selected_profile=None):
    """Load search config from the selected profile."""
    return load_profile_config(selected_profile)


def build_search_urls(config, keywords, local=True, remote=True, **legacy):
    """Build LinkedIn search URLs from config locations."""
    from urllib.parse import quote
    kw = quote(keywords)
    urls = []

    for loc in config.get("search", {}).get("locations", []):
        name = loc.get("name", "Unknown")
        is_remote = loc.get("remote_only", False)
        location_str = loc.get("linkedin_filter", name)

        if is_remote and not remote:
            continue
        if not is_remote and not local:
            continue

        loc_encoded = quote(location_str)
        remote_filter = "&f_WT=2" if is_remote else ""
        urls.append({
            "mode": "remote" if is_remote else "local",
            "name": name,
            "url": LINKEDIN_SEARCH.format(keywords=kw, location=loc_encoded, remote_filter=remote_filter)
        })

    return urls


def canonical_job_url(url):
    """Return a stable LinkedIn job URL when the URL contains a numeric job ID."""
    value = str(url or "")
    path = re.search(r"linkedin\.com/jobs/view/([^/?#]+)", value, re.IGNORECASE)
    job_id = re.search(r"(\d+)$", path.group(1)) if path else None
    return f"https://www.linkedin.com/jobs/view/{job_id.group(1)}/" if job_id else value.split("?")[0]


def dedupe_jobs(jobs):
    """Remove duplicate jobs by canonical URL."""
    seen = set()
    unique = []
    for j in jobs:
        key = canonical_job_url(j.get("url", ""))
        if key and key not in seen:
            seen.add(key)
            j = dict(j)
            j["url"] = key
            j["title"] = re.sub(r"\s+with verification\s*$", "", str(j.get("title") or ""), flags=re.IGNORECASE)
            unique.append(j)
    return unique


def filter_by_keywords(jobs, keywords, config):
    """Keep complete listings matching configured title rules."""
    search = config.get("search", {})
    include = [str(term).lower() for term in search.get("title_include", search.get("title_filter_terms", []))]
    exclude = [str(term).lower() for term in search.get("title_exclude", [])]
    filtered = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        title_lower = str(j.get("title") or "").strip().lower()
        url = str(j.get("url") or "").strip()
        if not title_lower or not url:
            continue
        if include and not any(term in title_lower for term in include):
            continue
        if any(term in title_lower for term in exclude):
            continue
        if title_lower:
            filtered.append(j)
    return filtered


def save_csv(jobs, date_str, output_dir, overwrite=False):
    """Save jobs to CSV."""
    filename = safe_output_path(output_dir / f"linkedin_jobs_{date_str}.csv", overwrite)
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date_found", "search_mode", "company", "title", "location", "url"
        ])
        writer.writeheader()
        for j in jobs:
            writer.writerow({
                "date_found": date_str,
                "search_mode": j.get("search_mode", ""),
                "company": j.get("company", ""),
                "title": j.get("title", ""),
                "location": j.get("location", ""),
                "url": j.get("url", ""),
            })
    return filename


def save_markdown(jobs, date_str, output_dir, overwrite=False):
    """Save jobs to markdown summary grouped by company."""
    filename = safe_output_path(output_dir / f"linkedin_jobs_{date_str}.md", overwrite)
    with open(filename, "w") as f:
        f.write(f"# LinkedIn Job Search Results — {date_str}\n\n")
        f.write(f"**{len(jobs)} jobs found**\n\n")
        
        # Split by mode
        boston_jobs = [j for j in jobs if j.get("search_mode") in ("local", "boston")]
        remote_jobs = [j for j in jobs if j.get("search_mode") == "remote"]
        
        for mode_name, mode_jobs in [("Local", boston_jobs), ("Remote", remote_jobs)]:
            if not mode_jobs:
                continue
            f.write(f"---\n\n## {mode_name} ({len(mode_jobs)} jobs)\n\n")
            
            # Group by company
            by_company = {}
            for j in mode_jobs:
                company = j.get("company", "Unknown")
                by_company.setdefault(company, []).append(j)
            
            for company in sorted(by_company.keys()):
                company_jobs = by_company[company]
                f.write(f"### {company}\n\n")
                for j in company_jobs:
                    f.write(f"- **{j['title']}**\n")
                    f.write(f"  - Location: {j.get('location', 'N/A')}\n")
                    f.write(f"  - URL: {j['url']}\n\n")
    
    return filename


def save_raw_json(jobs, date_str, output_dir, overwrite=False):
    """Save raw JSON for downstream processing (scoring, etc)."""
    filename = safe_output_path(output_dir / f"linkedin_jobs_{date_str}.json", overwrite)
    with open(filename, "w") as f:
        json.dump(jobs, f, indent=2)
    return filename


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Jobs Search Pipeline")
    add_profile_argument(parser)
    parser.add_argument("--keywords", help="Override configured search keywords")
    parser.add_argument("--local", action="store_true", help="Search configured local locations")
    parser.add_argument("--boston", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--remote", action="store_true", help="Search Remote USA")
    parser.add_argument("--input", help="Read pre-extracted jobs from JSON file instead of browser")
    parser.add_argument("--overwrite", action="store_true", help="Replace same-day filtered outputs")
    args = parser.parse_args()
    selected_dir, config = load_config(args.profile_dir)
    search_config = config.get("search", {})
    keywords = args.keywords or search_config.get("keywords")
    if not keywords:
        parser.error("search.keywords is required in the selected profile")
    output_dir = configured_path(selected_dir, config, "output", "output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # If neither flag set, search both
    explicit_local = args.local or args.boston
    search_local = explicit_local or (not explicit_local and not args.remote)
    search_remote = args.remote or (not explicit_local and not args.remote)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if args.input:
    # Read pre-extracted jobs from JSON file (from browser extraction)
        with open(args.input) as f:
            jobs = json.load(f)
        print(f"Loaded {len(jobs)} jobs from {args.input}")
    else:
        # Print search URLs for the agent to navigate to
        urls = build_search_urls(config, keywords, local=search_local, remote=search_remote)
        print("SEARCH_URLS:")
        for u in urls:
            print(f"  {u['mode']}: {u['url']}")
        print()
        print("EXTRACT_JS:")
        print(EXTRACT_JS)
        print()
        print("INSTRUCTIONS:")
        print("1. Navigate to each search URL")
        print("2. Dismiss sign-in dialog if it appears")
        print("3. Scroll down 3-4 times to load more results")
        print("4. Run EXTRACT_JS to get job listings")
        print("5. Save results to output/linkedin_extract.json")
        print("6. Re-run: python3 search_linkedin.py --input output/linkedin_extract.json")
        return
    
    # Process extracted jobs
    jobs = dedupe_jobs(jobs)
    jobs = filter_by_keywords(jobs, keywords, config)
    jobs = jobs[:int(search_config.get("max_results_per_search", len(jobs) or 0))]
    
    print(f"After dedup + filter: {len(jobs)} jobs")
    
    csv_path = save_csv(jobs, date_str, output_dir, args.overwrite)
    md_path = save_markdown(jobs, date_str, output_dir, args.overwrite)
    json_path = save_raw_json(jobs, date_str, output_dir, args.overwrite)
    
    print(f"\nSaved:")
    print(f"  CSV:  {csv_path}")
    print(f"  MD:   {md_path}")
    print(f"  JSON: {json_path}")


if __name__ == "__main__":
    main()
