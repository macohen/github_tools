import requests
import csv
import sys
import os
from datetime import datetime, timezone

# Configuration
REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "awslabs")
REPO_NAME = os.getenv("GITHUB_REPO_NAME", "aws-athena-query-federation")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable is required", file=sys.stderr)
    sys.exit(1)

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

def fetch_open_prs():
    prs = []
    page = 1
    while True:
        params = {"state": "open", "per_page": 100, "page": page}
        response = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise requests.HTTPError(f"Failed to fetch PRs: {response.status_code} {response.text}")
        data = response.json()
        if not data:
            break
        prs.extend(data)
        page += 1
    return prs

def get_last_comment_date(pr_number):
    comments_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{pr_number}/comments"
    response = requests.get(comments_url, headers=HEADERS, params={"per_page": 1, "sort": "updated", "direction": "desc"})
    if response.status_code == 200:
        comments = response.json()
        if comments:
            return comments[0]["updated_at"]
    return None

def get_reviewers(pr_number):
    all_reviewers = set()
    
    # Get requested reviewers (pending)
    requested_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/requested_reviewers"
    response = requests.get(requested_url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        all_reviewers.update(user["login"] for user in data.get("users", []))
        all_reviewers.update(team["name"] for team in data.get("teams", []))
    
    # Get actual reviewers (who have reviewed)
    reviews_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/reviews"
    response = requests.get(reviews_url, headers=HEADERS)
    if response.status_code == 200:
        reviews = response.json()
        all_reviewers.update(review["user"]["login"] for review in reviews if review["user"])
    
    return ", ".join(sorted(all_reviewers)) if all_reviewers else "None"

def human_age(created_at):
    now = datetime.now(timezone.utc)
    created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    delta = now - created
    days = delta.days
    hours = delta.seconds // 3600
    return f"{days}d {hours}h"

def get_days_old(created_at):
    now = datetime.now(timezone.utc)
    created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (now - created).days

def main():
    prs = fetch_open_prs()
    rows = []
    unassigned_count = 0
    old_prs = []
    stale_prs = []
    
    for pr in prs:
        pr_url = pr["html_url"]
        pr_title = pr["title"]
        last_modified = pr["updated_at"]
        age = human_age(pr["created_at"])
        last_comment = get_last_comment_date(pr["number"])
        reviewers = get_reviewers(pr["number"])
        
        # Count statistics
        if reviewers == "None":
            unassigned_count += 1
        if get_days_old(pr["created_at"]) >= 23 and get_days_old(pr["created_at"]) <= 30:
            stale_prs.append((pr["created_at"], pr_title, pr_url, reviewers))
        if get_days_old(pr["created_at"]) > 30:
            old_prs.append((pr["created_at"], pr_title, pr_url, reviewers))

        rows.append([
            pr_url,
            pr["created_at"],
            last_modified, 
            last_comment or "No comments",
            age, 
            reviewers
        ])

    # Print summary to stderr so it doesn't interfere with CSV output
    print(f"SUMMARY: {len(prs)} total PRs, {unassigned_count} no reviewers, {len(old_prs)} open >30 days", file=sys.stderr)

    if old_prs:
        print(f"\n {len(old_prs)} PRs open >30 days (oldest first):", file=sys.stderr)
        old_prs.sort()  # Sort by created_at (oldest first)
        for created_at, title, url, reviewers in old_prs:
            days = get_days_old(created_at)
            print(f"  {days} days: {url}; reviewers: {reviewers}", file=sys.stderr)

    if stale_prs:
        print(f"\n {len(stale_prs)} PRs growing old: open >23 days and < 30 days(oldest first):", file=sys.stderr)
        stale_prs.sort()  # Sort by created_at (oldest first)
        for created_at, title, url, reviewers in stale_prs:
            days = get_days_old(created_at)
            print(f"  {days} days: {url}; reviewers: {reviewers}", file=sys.stderr)
    
    headers = ["PR Link", "Title", "CreatedDate", "LastModifiedDate", "LastCommentDate", "Age", "Reviewers"]
    
    writer = csv.writer(sys.stdout)
    writer.writerow(headers)
    writer.writerows(rows)

if __name__ == "__main__":
    main()