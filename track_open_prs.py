import requests
import sys
import os
import argparse
import logging
from datetime import datetime, timezone, timedelta
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('track_open_prs.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "awslabs")
REPO_NAME = os.getenv("GITHUB_REPO_NAME", "aws-athena-query-federation")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
QUIP_TOKEN = os.getenv("QUIP_API_TOKEN")
QUIP_DOC_ID = os.getenv("QUIP_DOC_ID")
QUIP_BASE_URL = os.getenv("QUIP_BASE_URL", "https://platform.quip.com")
API_URL = os.getenv("API_URL", "http://localhost:5000/api")

logger.info(f"Configuration: REPO={REPO_OWNER}/{REPO_NAME}, API_URL={API_URL}")

if not GITHUB_TOKEN:
    logger.error("GITHUB_TOKEN environment variable is required")
    print("Error: GITHUB_TOKEN environment variable is required", file=sys.stderr)
    sys.exit(1)

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
github_session = requests.Session()
github_session.headers.update({
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {GITHUB_TOKEN}"
})

# Cache current time to avoid repeated calls
NOW = datetime.now(timezone.utc)

def fetch_prs(state="open", since_date=None):
    prs = []
    page = 1
    logger.info(f"Fetching {state} PRs from {REPO_OWNER}/{REPO_NAME}...")
    print(f"Fetching {state} PRs...")
    
    params = {"state": state, "per_page": 100}
    
    if state == "closed":
        if since_date is None:
            since_date = NOW - timedelta(days=7)
        params.update({
            "sort": "updated", 
            "direction": "desc",
            "since": since_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        })
        since_timestamp = since_date.timestamp()
    
    while True:
        params["page"] = page
        response = github_session.get(GITHUB_API_URL, params=params)
        if response.status_code != 200:
            raise requests.HTTPError(f"Failed to fetch PRs: {response.status_code} {response.text}")
        
        data = response.json()
        if not data:
            break
        
        if state == "closed":
            for pr in data:
                if pr["closed_at"]:
                    closed_timestamp = datetime.fromisoformat(pr["closed_at"].replace('Z', '+00:00')).timestamp()
                    if closed_timestamp >= since_timestamp:
                        prs.append(pr)
                    else:
                        return prs
        else:
            prs.extend(data)
        
        page += 1

    logger.info(f"Fetched {len(prs)} {state} PRs")
    print(f"Fetched {len(prs)} {state} PRs...")
    return prs

@lru_cache(maxsize=256)
def get_reviewers(pr_number):
    all_reviewers = set()
    
    # Batch both requests
    urls = [
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/requested_reviewers",
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/reviews"
    ]

    responses = []
    for url in urls:
        response = github_session.get(url)
        if response.status_code == 200:
            responses.append(response.json())
        else:
            responses.append({})
    
    # Process requested reviewers
    if responses[0]:
        all_reviewers.update((user["login"], "NO ACTION") for user in responses[0].get("users", []))

    # Process actual reviewers
    if responses[1]:
        all_reviewers.update((review["user"]["login"], review["state"])
                           for review in responses[1] if review.get("user"))

    return all_reviewers

@lru_cache(maxsize=256)
def get_comment_counts(pr_number):
    """Get comment counts per reviewer for a PR"""
    comment_counts = {}
    
    # Get review comments (code comments)
    review_comments_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/comments"
    response = github_session.get(review_comments_url)
    if response.status_code == 200:
        for comment in response.json():
            user = comment.get("user", {}).get("login")
            if user:
                comment_counts[user] = comment_counts.get(user, 0) + 1
    
    # Get issue comments (general PR comments)
    issue_comments_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{pr_number}/comments"
    response = github_session.get(issue_comments_url)
    if response.status_code == 200:
        for comment in response.json():
            user = comment.get("user", {}).get("login")
            if user:
                comment_counts[user] = comment_counts.get(user, 0) + 1
    
    return comment_counts

def get_reviewers_batch(pr_numbers):
    """Fetch reviewers for multiple PRs concurrently"""
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_pr = {executor.submit(get_reviewers, pr_num): pr_num for pr_num in pr_numbers}
        results = {}
        for future in as_completed(future_to_pr):
            pr_num = future_to_pr[future]
            try:
                results[pr_num] = future.result()
            except Exception as e:
                print(f"Error fetching reviewers for PR {pr_num}: {e}", file=sys.stderr)
                results[pr_num] = set()
        return results

def get_comment_counts_batch(pr_numbers):
    """Fetch comment counts for multiple PRs concurrently"""
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_pr = {executor.submit(get_comment_counts, pr_num): pr_num for pr_num in pr_numbers}
        results = {}
        for future in as_completed(future_to_pr):
            pr_num = future_to_pr[future]
            try:
                results[pr_num] = future.result()
            except Exception as e:
                print(f"Error fetching comments for PR {pr_num}: {e}", file=sys.stderr)
                results[pr_num] = {}
        return results

@lru_cache(maxsize=1000)
def parse_date_cached(date_str):
    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))

def human_age(created_at):
    created = parse_date_cached(created_at)
    delta = NOW - created
    days = delta.days
    hours = delta.seconds // 3600
    return f"{days}d {hours}h"

def get_days_old(created_at):
    created = parse_date_cached(created_at)
    return (NOW - created).days

def publish_to_quip(markdown_content, title="PR Summary"):
    if not QUIP_TOKEN:
        print("Error: QUIP_TOKEN environment variable is required for Quip publishing", file=sys.stderr)
        sys.exit(1)
    
    quip_headers = {
        "Authorization": f"Bearer {QUIP_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    if QUIP_DOC_ID:
        url = f"{QUIP_BASE_URL}/1/threads/edit-document"
        data = {
            "thread_id": QUIP_DOC_ID,
            "content": markdown_content,
            "format": "markdown",
            "location": 0
        }
    else:
        url = f"{QUIP_BASE_URL}/1/threads/new-document"
        data = {
            "title": title,
            "content": markdown_content,
            "format": "markdown"
        }

    response = requests.post(url, headers=quip_headers, data=data)
    
    if response.status_code in [200, 201]:
        result = response.json()
        doc_url = result.get("thread", {}).get("link") or result.get("html")
        print(f"✓ Published to Quip: {doc_url}", file=sys.stderr)
        return doc_url
    else:
        print(f"Error publishing to Quip: {response.status_code} {response.text}", file=sys.stderr)
        sys.exit(1)

def store_snapshot(processed_prs, total_prs, unassigned_count, old_prs_count):
    """Store PR snapshot in database via API"""
    logger.info(f"Preparing to store snapshot: {total_prs} PRs, {unassigned_count} unassigned, {old_prs_count} old")
    
    pr_data = []
    for pr in processed_prs:
        reviewer_str = ", ".join(f"{r[0]} [{r[1]}]" for r in pr["reviewers"]) if pr["reviewers"] else "None"
        
        # Prepare comment data
        comments = []
        for reviewer, count in pr.get("comment_counts", {}).items():
            comments.append({
                "reviewer": reviewer,
                "comment_count": count
            })
        
        pr_data.append({
            "number": pr["number"],
            "title": pr["title"],
            "url": pr["html_url"],
            "created_at": pr["created_at"],
            "updated_at": pr["updated_at"],
            "age_days": pr["age_days"],
            "reviewers": reviewer_str,
            "state": "open",
            "comments": comments
        })
    
    snapshot = {
        "repo_owner": REPO_OWNER,
        "repo_name": REPO_NAME,
        "total_prs": total_prs,
        "unassigned_count": unassigned_count,
        "old_prs_count": old_prs_count,
        "prs": pr_data
    }
    
    logger.info(f"Sending snapshot to API: {API_URL}/snapshots")
    print(f"Storing snapshot: {total_prs} PRs, {unassigned_count} unassigned, {old_prs_count} old")
    
    try:
        response = requests.post(f"{API_URL}/snapshots", json=snapshot)
        
        if response.status_code == 201:
            result = response.json()
            logger.info(f"Snapshot stored successfully with ID: {result['snapshot_id']}")
            print(f"✓ Snapshot stored with ID: {result['snapshot_id']}")
        else:
            logger.error(f"Failed to store snapshot: {response.status_code} {response.text}")
            print(f"Error storing snapshot: {response.status_code} {response.text}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        logger.error(f"Exception while storing snapshot: {str(e)}", exc_info=True)
        print(f"Error storing snapshot: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Track open pull requests')
    parser.add_argument('--skip-publish', action='store_true', help='Skip publishing to Quip')
    parser.add_argument('--store', action='store_true', help='Store snapshot in database via API')
    args = parser.parse_args()
    
    report_date = NOW.strftime('%Y-%m-%d')
    open_prs = fetch_prs("open")
    
    # Batch fetch all reviewers and comments concurrently
    pr_numbers = [pr["number"] for pr in open_prs]
    all_reviewers = get_reviewers_batch(pr_numbers)
    all_comments = get_comment_counts_batch(pr_numbers)

    # Process PRs with pre-fetched reviewer data
    unassigned_count = 0
    older_than_30_days = 0
    processed_prs = []

    for pr in open_prs:
        if pr.get("draft"):
            continue
        reviewers = all_reviewers.get(pr["number"], set())
        comment_counts = all_comments.get(pr["number"], {})
        approval_count = sum(1 for _, state in reviewers if state == "APPROVED")

        ready_to_merge = "🔴"
        if approval_count == 1:
            ready_to_merge = "🟡"
        elif approval_count >= 2:
            ready_to_merge = "🟢"

        days_old = get_days_old(pr["created_at"])
        if days_old > 30:
            older_than_30_days += 1
        if not reviewers:
            unassigned_count += 1

        processed_prs.append({
            "number": pr["number"],
            "title": pr["title"],
            "html_url": pr["html_url"],
            "created_at": pr["created_at"],
            "updated_at": pr["updated_at"],
            "ready": ready_to_merge,
            "approval_count": approval_count,
            "reviewers": reviewers,
            "comment_counts": comment_counts,
            "age": human_age(pr["created_at"]),
            "age_days": days_old
        })

    # Sort by approval count (desc) then by age (oldest first)
    processed_prs.sort(key=lambda x: (-x["approval_count"], x["created_at"]))

    # Store in database if requested
    if args.store:
        store_snapshot(processed_prs, len(processed_prs), unassigned_count, older_than_30_days)
        return

    # Generate output
    output = StringIO()
    print(f"**All Open PRs as of {report_date}", file=output)
    print(file=output)
    print("🔴= 2 approvals needed to merge", file=output)
    print("🟡= 1 approvals needed to merge", file=output)
    print("🟢= Ready To Merge!!!", file=output)

    print(f"**{len(processed_prs)} total PRs, {unassigned_count} no reviewers, {older_than_30_days} open >30 days**\n", file=output)
    print("| PR | Age | Reviewers | Ready to Merge |", file=output)
    print("|---|---|---|---|", file=output)

    for pr in processed_prs:
        reviewer_list = " ".join(f"{r[0]} [{r[1]}]" for r in pr["reviewers"])
        print(f"| [{pr['title']}]({pr['html_url']}) | {pr['age']} | {reviewer_list} | {pr['ready']} |", file=output)

    markdown_content = output.getvalue()
    if not args.skip_publish:
        publish_to_quip(markdown_content, f"PR Summary: {REPO_OWNER}/{REPO_NAME}")
    else:
        print(markdown_content)

if __name__ == "__main__":
    main()