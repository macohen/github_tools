#!/usr/bin/env python3
"""
pr_count_on_date.py

Fetch PRs for a repository and compute how many pull requests were open on a given date
and had been open for more than N days on that date.

Usage:
  - Set environment variable GITHUB_TOKEN to a personal access token (recommended to avoid rate limits).
  - Run:
      python pr_count_on_date.py --repo awslabs/aws-athena-query-federation \
        --date 2025-08-01 --days 30 --list-prs

What the script does:
  1. Uses the GitHub Search API to list PRs created on or before the given date.
     (Search is limited to 1000 results by GitHub; for very large repos you may need to
     refine the query by date ranges.)
  2. Pages through results and fetches each PR's details (created_at, closed_at).
  3. Determines whether the PR was open on the target date:
       - created_at <= target_date AND (closed_at is None OR closed_at > target_date)
  4. If the PR was open on the target date, checks whether (target_date - created_at) > threshold_days.
  5. Prints the exact count and (optionally) a table of matching PRs.

Notes:
  - The script paginates through search results and will fetch PR details individually (one extra API
    request per PR) to obtain closed_at timestamps when necessary.
  - Provide a GITHUB_TOKEN to avoid low unauthenticated rate limits.
  - If you hit GitHub API search size limitations (1000 results), consider narrowing the date range
    or using additional queries (by created date ranges) and aggregating results.

Author: GitHub Copilot conversational helper
"""

import os
import sys
import time
import argparse
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

GITHUB_API = "https://api.github.com"

def iso_to_dt(s: str) -> datetime:
    # Parse ISO 8601 timestamp returned by GitHub (e.g. "2025-08-01T12:34:56Z")
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def search_prs(repo: str, target_date: datetime, token: Optional[str]) -> List[Dict]:
    """
    Search for PRs created on or before the target_date.
    Returns list of search "items" (issue objects containing PR refs).
    Uses pagination.
    """
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }

    per_page = 100
    page = 1
    items = []

    # Format date for query: YYYY-MM-DD
    date_str = target_date.date().isoformat()
    # We search for PRs created <= target_date. We'll fetch details to check closed_at.
    q = f"is:pr repo:{repo} created:<={date_str}"

    print(f"Searching GitHub for: {q}")
    while True:
        params = {"q": q, "per_page": per_page, "page": page}
        resp = requests.get(f"{GITHUB_API}/search/issues", headers=headers, params=params)
        if resp.status_code != 200:
            raise SystemExit(f"GitHub search failed: {resp.status_code} {resp.text}")
        data = resp.json()
        page_items = data.get("items", [])
        items.extend(page_items)

        # GitHub search API returns total_count but caps at 1000 for results. We still paginate until no items.
        if len(page_items) < per_page:
            break
        page += 1
        time.sleep(0.1)  # be kind to the API

    print(f"Found {len(items)} PRs created on or before {date_str} (search result count)")
    return items

def get_pr_details(owner: str, repo_name: str, pr_number: int, token: Optional[str]) -> Dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"{GITHUB_API}/repos/{owner}/{repo_name}/pulls/{pr_number}"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise SystemExit(f"Failed to fetch PR {pr_number}: {resp.status_code} {resp.text}")
    return resp.json()

def was_open_on_date(created_at: datetime, closed_at: Optional[datetime], target_date: datetime) -> bool:
    """
    Return True if PR was open at any time on target_date (i.e., at the instant of target_date).
    We consider 'open on date' to mean the PR existed and had not been closed by that instant.
    """
    if created_at <= target_date and (closed_at is None or closed_at > target_date):
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Count PRs that were open on a given date for more than N days.")
    parser.add_argument("--repo", required=True, help="Repository in owner/repo format (e.g. awslabs/aws-athena-query-federation)")
    parser.add_argument("--date", required=True, help="Target date (YYYY-MM-DD) to check PRs were open on (e.g. 2025-08-01)")
    parser.add_argument("--days", type=int, default=30, help="Threshold number of days (default 30)")
    parser.add_argument("--list-prs", action="store_true", help="Also list matching PRs")
    parser.add_argument("--token", help="GitHub token (or set GITHUB_TOKEN env var)")
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN")
    try:
        target_date = datetime.fromisoformat(args.date).replace(tzinfo=timezone.utc)
    except Exception as e:
        print(f"Failed to parse date '{args.date}': {e}")
        sys.exit(1)

    owner_repo = args.repo.split("/")
    if len(owner_repo) != 2:
        print("Repo must be in owner/repo format")
        sys.exit(1)
    owner, repo_name = owner_repo

    try:
        search_items = search_prs(args.repo, target_date, token)
    except SystemExit as e:
        print(f"Search failed: {e}")
        sys.exit(1)

    threshold = timedelta(days=args.days)
    matches = []

    print("Fetching PR details and evaluating open-on-date and age...")
    for idx, item in enumerate(search_items, start=1):
        # item is an issue-like object from search; its "number" is the PR number
        pr_number = item["number"]
        try:
            pr = get_pr_details(owner, repo_name, pr_number, token)
        except SystemExit as e:
            print(f"Warning: failed to fetch PR {pr_number}: {e}")
            continue

        created_at = iso_to_dt(pr["created_at"])
        closed_at = iso_to_dt(pr["closed_at"]) if pr.get("closed_at") else None

        if was_open_on_date(created_at, closed_at, target_date):
            age_on_target = target_date - created_at
            if age_on_target > threshold:
                matches.append({
                    "number": pr_number,
                    "title": pr.get("title", "")[:200],
                    "html_url": pr.get("html_url"),
                    "created_at": pr["created_at"],
                    "closed_at": pr.get("closed_at") or "",
                    "author": pr["user"]["login"] if pr.get("user") else "",
                    "age_days_on_target": age_on_target.days
                })
        # be polite to API
        time.sleep(0.05)

    total = len(matches)
    print()
    print(f"PRs that were open on {args.date} and had been open for more than {args.days} days: {total}")
    if args.list_prs and total:
        print()
        print("Matching PRs:")
        for m in matches:
            print(f"- #{m['number']} {m['title']} (created: {m['created_at']}, closed: {m['closed_at'] or 'still open'}, author: {m['author']}, age_days_on_target: {m['age_days_on_target']})")
    elif total == 0:
        print("No PRs matched the criteria.")

if __name__ == "__main__":
    main()