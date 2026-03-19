#!/usr/bin/env python3
"""
Import historical PR snapshots for specific dates.
Fetches PRs that were open at each specified date and stores them in the database.
Prevents duplicate snapshots for the same date.
"""

import os
import sys
import requests
import duckdb
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("GITHUB_REPO", "awslabs/aws-athena-query-federation")
API_URL = os.environ.get("API_URL", "http://localhost:5001/api")
DB_PATH = os.environ.get("DB_PATH", "backend/local/pr_tracker.duckdb")

if not GITHUB_TOKEN:
    logger.error("GITHUB_TOKEN environment variable is required")
    sys.exit(1)


def check_snapshot_exists(date_str: str) -> bool:
    """Check if a snapshot already exists for the given date."""
    try:
        conn = duckdb.connect(DB_PATH)
        
        # Check if snapshot exists for this date (within same day)
        # Use explicit CAST to ensure proper type conversion
        result = conn.execute("""
            SELECT COUNT(*) FROM pr_snapshots 
            WHERE DATE(snapshot_date) = CAST(? AS DATE)
        """, [date_str]).fetchone()
        
        count = result[0]
        logger.debug(f"check_snapshot_exists('{date_str}'): count={count}")
        conn.close()
        
        return count > 0
    except Exception as e:
        logger.error(f"Error checking snapshot existence: {e}")
        return False


def fetch_prs_at_date(repo: str, target_date: datetime) -> List[Dict[str, Any]]:
    """
    Fetch PRs that were open at the target date.
    This searches for PRs created before the target date and either:
    - Still open, OR
    - Closed/merged after the target date
    """
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Format date for GitHub API (ISO 8601)
    date_str = target_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Search for PRs created before target date
    search_query = f"repo:{repo} is:pr created:<{date_str}"
    
    logger.info(f"Searching for PRs open at {date_str}")
    
    all_prs = []
    page = 1
    per_page = 100
    
    while True:
        url = f"https://api.github.com/search/issues"
        params = {
            "q": search_query,
            "per_page": per_page,
            "page": page,
            "sort": "created",
            "order": "desc"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        items = data.get("items", [])
        
        if not items:
            break
        
        # Filter PRs that were open at target date
        for pr in items:
            created_at = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            
            # Check if PR was closed/merged
            if pr["state"] == "closed":
                closed_at = datetime.strptime(pr["closed_at"], "%Y-%m-%dT%H:%M:%SZ")
                # Only include if closed after target date
                if closed_at <= target_date:
                    continue
            
            # PR was open at target date
            all_prs.append(pr)
        
        logger.info(f"Fetched page {page}, found {len(items)} PRs, {len(all_prs)} were open at target date")
        
        # Check if there are more pages
        if len(items) < per_page:
            break
        
        page += 1
    
    logger.info(f"Total PRs open at {date_str}: {len(all_prs)}")
    return all_prs


def fetch_pr_comments(repo: str, pr_number: int) -> int:
    """Fetch total comment count for a PR (review comments + issue comments)."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get review comments
    review_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments"
    review_response = requests.get(review_url, headers=headers, params={"per_page": 100})
    review_comments = len(review_response.json()) if review_response.status_code == 200 else 0
    
    # Get issue comments
    issue_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    issue_response = requests.get(issue_url, headers=headers, params={"per_page": 100})
    issue_comments = len(issue_response.json()) if issue_response.status_code == 200 else 0
    
    return review_comments + issue_comments


def process_prs(prs: List[Dict[str, Any]], target_date: datetime) -> Dict[str, Any]:
    """Process PRs and prepare snapshot data."""
    old_threshold_days = 7
    old_threshold = target_date - timedelta(days=old_threshold_days)
    
    pr_data = []
    unassigned_count = 0
    old_count = 0
    reviewer_comments = {}
    
    for pr in prs:
        created_at = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        age_days = (target_date - created_at).days
        
        # Get reviewers
        reviewers = []
        if pr.get("requested_reviewers"):
            reviewers = [r["login"] for r in pr["requested_reviewers"]]
        
        # Count unassigned and old PRs
        if not reviewers:
            unassigned_count += 1
        
        if created_at < old_threshold:
            old_count += 1
        
        # Fetch comment counts per reviewer
        pr_number = pr["number"]
        total_comments = fetch_pr_comments(REPO, pr_number)
        
        pr_info = {
            "number": pr_number,
            "title": pr["title"],
            "author": pr["user"]["login"],
            "created_at": pr["created_at"],
            "age_days": age_days,
            "reviewers": reviewers,
            "url": pr["html_url"],
            "comments": []
        }
        
        # Distribute comments among reviewers (simplified - actual distribution would need API calls)
        if reviewers and total_comments > 0:
            comments_per_reviewer = total_comments // len(reviewers)
            for reviewer in reviewers:
                pr_info["comments"].append({
                    "reviewer": reviewer,
                    "comment_count": comments_per_reviewer
                })
                
                if reviewer not in reviewer_comments:
                    reviewer_comments[reviewer] = 0
                reviewer_comments[reviewer] += comments_per_reviewer
        
        pr_data.append(pr_info)
    
    return {
        "repo": REPO,
        "timestamp": target_date.strftime("%Y-%m-%d %H:%M:%S"),
        "total_prs": len(prs),
        "unassigned_prs": unassigned_count,
        "old_prs": old_count,
        "prs": pr_data
    }


def store_snapshot(snapshot_data: Dict[str, Any]) -> bool:
    """Store snapshot directly in database."""
    try:
        conn = duckdb.connect(DB_PATH)
        
        # Insert snapshot with RETURNING to get ID
        result = conn.execute(
            """INSERT INTO pr_snapshots (repo_owner, repo_name, total_prs, unassigned_count, old_prs_count, snapshot_date)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
            [
                REPO.split('/')[0],  # repo_owner
                REPO.split('/')[1],  # repo_name
                snapshot_data["total_prs"],
                snapshot_data["unassigned_prs"],
                snapshot_data["old_prs"],
                snapshot_data["timestamp"]
            ]
        )
        
        snapshot_id = result.fetchone()[0]
        logger.info(f"Created snapshot with ID: {snapshot_id}")
        
        # Insert PRs
        for pr in snapshot_data["prs"]:
            result = conn.execute(
                """INSERT INTO prs (snapshot_id, pr_number, title, url, created_at, age_days, reviewers, state)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id""",
                [
                    snapshot_id,
                    pr["number"],
                    pr["title"],
                    pr["url"],
                    pr["created_at"],
                    pr["age_days"],
                    ",".join(pr["reviewers"]),
                    "open"  # Historical PRs were open at that time
                ]
            )
            
            pr_id = result.fetchone()[0]
            
            # Insert comments
            for comment in pr["comments"]:
                conn.execute(
                    """INSERT INTO pr_comments (pr_id, reviewer, comment_count)
                       VALUES ($1, $2, $3)""",
                    [pr_id, comment["reviewer"], comment["comment_count"]]
                )
        
        conn.close()
        
        logger.info(f"Successfully stored snapshot for {snapshot_data['timestamp']}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing snapshot: {e}")
        return False


def generate_weekly_dates(start_date: str, end_date: str = None) -> List[datetime]:
    """
    Generate list of dates for weekly snapshots.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (defaults to today)
    
    Returns:
        List of datetime objects for each week
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    
    dates = []
    current = start
    
    while current <= end:
        dates.append(current)
        current += timedelta(days=7)
    
    return dates


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_historical_snapshots.py <start_date> [end_date]")
        print("  start_date: YYYY-MM-DD format (e.g., 2025-12-22)")
        print("  end_date: YYYY-MM-DD format (optional, defaults to today)")
        print("\nExample: python import_historical_snapshots.py 2025-12-22")
        print("Example: python import_historical_snapshots.py 2025-12-22 2026-01-31")
        sys.exit(1)
    
    start_date = sys.argv[1]
    end_date = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Validate date format
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        logger.error("Invalid date format. Use YYYY-MM-DD")
        sys.exit(1)
    
    # Generate weekly dates
    dates = generate_weekly_dates(start_date, end_date)
    logger.info(f"Will import {len(dates)} weekly snapshots from {start_date} to {end_date or 'today'}")
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for target_date in dates:
        date_str = target_date.strftime("%Y-%m-%d")
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing snapshot for {date_str}")
        logger.info(f"{'='*60}")
        
        # Check if snapshot already exists
        if check_snapshot_exists(date_str):
            logger.info(f"Snapshot for {date_str} already exists, skipping")
            skip_count += 1
            continue
        
        # Fetch PRs that were open at this date
        prs = fetch_prs_at_date(REPO, target_date)
        
        if not prs:
            logger.warning(f"No PRs found for {date_str}")
            continue
        
        # Process and store snapshot
        snapshot_data = process_prs(prs, target_date)
        
        if store_snapshot(snapshot_data):
            success_count += 1
            logger.info(f"✓ Successfully imported snapshot for {date_str}")
        else:
            fail_count += 1
            logger.error(f"✗ Failed to import snapshot for {date_str}")
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Import Summary")
    logger.info(f"{'='*60}")
    logger.info(f"Total dates processed: {len(dates)}")
    logger.info(f"Successfully imported: {success_count}")
    logger.info(f"Skipped (already exist): {skip_count}")
    logger.info(f"Failed: {fail_count}")


if __name__ == "__main__":
    main()
