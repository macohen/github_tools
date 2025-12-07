import requests
import sys
import os
from datetime import datetime, timezone, timedelta
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

# Configuration
REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "awslabs")
REPO_NAME = os.getenv("GITHUB_REPO_NAME", "aws-athena-query-federation")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
QUIP_TOKEN = os.getenv("QUIP_ACCESS_TOKEN")
QUIP_DOC_ID = os.getenv("QUIP_DOC_ID")
QUIP_BASE_URL = os.getenv("QUIP_BASE_URL", "https://platform.quip.com")

if not GITHUB_TOKEN:
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
            "format": "markdown",
            "member_ids": "tpDFO7wadBk5"
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

def main():
    report_date = NOW.strftime('%Y-%m-%d')
    open_prs = fetch_prs("open")
    
    # Batch fetch all reviewers concurrently
    pr_numbers = [pr["number"] for pr in open_prs]
    all_reviewers = get_reviewers_batch(pr_numbers)

    # Process PRs with pre-fetched reviewer data
    unassigned_count = 0
    older_than_30_days = 0
    processed_prs = []

    for pr in open_prs:
        reviewers = all_reviewers.get(pr["number"], set())
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
            "title": pr["title"],
            "html_url": pr["html_url"],
            "created_at": pr["created_at"],
            "ready": ready_to_merge,
            "approval_count": approval_count,
            "reviewers": reviewers,
            "age": human_age(pr["created_at"])
        })

    # Sort by approval count (desc) then by age (oldest first)
    processed_prs.sort(key=lambda x: (-x["approval_count"], x["created_at"]))

    # Generate output
    output = StringIO()
    print(f"**All Open PRs as of {report_date}", file=output)
    print(file=output)
    print(f"**{len(processed_prs)} total PRs, {unassigned_count} no reviewers, {older_than_30_days} open >30 days**\n", file=output)
    print("| PR | Age | Reviewers | Ready to Merge |", file=output)
    print("|---|---|---|---|", file=output)

    for pr in processed_prs:
        reviewer_list = " ".join(f"{r[0]} [{r[1]}]" for r in pr["reviewers"])
        print(f"| [{pr['title']}]({pr['html_url']}) | {pr['age']} | {reviewer_list} | {pr['ready']} |", file=output)

    markdown_content = output.getvalue()
    publish_to_quip(markdown_content, f"PR Summary: {REPO_OWNER}/{REPO_NAME}")

if __name__ == "__main__":
    main()