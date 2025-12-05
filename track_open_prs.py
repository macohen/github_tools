import requests
import sys
import os
import csv
from datetime import datetime, timezone, timedelta
from io import StringIO

# Configuration
REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "awslabs")
REPO_NAME = os.getenv("GITHUB_REPO_NAME", "aws-athena-query-federation")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
QUIP_TOKEN = os.getenv("QUIP_ACCESS_TOKEN")
QUIP_DOC_ID = os.getenv("QUIP_DOC_ID")  # Optional: reuse existing doc
QUIP_BASE_URL = os.getenv("QUIP_BASE_URL", "https://platform.quip.com")  # Default Quip base URL")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable is required", file=sys.stderr)
    sys.exit(1)

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

def fetch_prs(state="open", since_date=None):
    prs = []
    page = 1
    print(f"Fetching {state} PRs...")
    params = {"state": state, "per_page": 200}
    if state == "closed":
        if since_date is None:
            since_date = datetime.now(timezone.utc) - timedelta(days=7)
        since_str = since_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        params.update({"sort": "updated", "direction": "desc"})
    
    while True:
        params["page"] = page
        response = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise requests.HTTPError(f"Failed to fetch PRs: {response.status_code} {response.text}")
        data = response.json()
        if not data:
            break
        
        if state == "closed":
            for pr in data:
                if pr["closed_at"] and pr["closed_at"] >= since_str:
                    prs.append(pr)
                else:
                    return prs
        else:
            prs.extend(data)
        
        page += 1
        print(f"Fetched {len(prs)} {state} PRs...")
    return prs

def fetch_open_prs():
    return fetch_prs("open")

def fetch_closed_prs(since_date=None):
    return fetch_prs("closed", since_date)

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
        all_reviewers.update(f"{review["user"]["login"]} {review["state"]}" for review in reviews if review["user"])
    
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

def publish_to_quip(markdown_content, title="PR Summary"):
    """Publish markdown content to Quip"""
    if not QUIP_TOKEN:
        print("Error: QUIP_TOKEN environment variable is required for Quip publishing", file=sys.stderr)
        sys.exit(1)
    else:
        print(QUIP_TOKEN)
    
    quip_headers = {
        "Authorization": f"Bearer {QUIP_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # If QUIP_DOC_ID is set, update existing doc, otherwise create new
    if QUIP_DOC_ID:
        url = f"{QUIP_BASE_URL}/1/threads/edit-document"
        data = {
            "thread_id": QUIP_DOC_ID,
            "content": markdown_content,
            "format": "markdown",
            "location": 0  # APPEND
        }
        response = requests.post(url, headers=quip_headers, data=data)
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

def main():
    output_csv = "--csv" in sys.argv
    output_quip = "--quip" in sys.argv
    
    open_prs = fetch_open_prs()
    closed_prs = fetch_closed_prs()

    unassigned_count = 0
    old_prs = []
    
    # Process open PRs
    for pr in open_prs:
        reviewers = get_reviewers(pr["number"])
        
        if reviewers == "None":
            unassigned_count += 1
        if get_days_old(pr["created_at"]) > 30:
            old_prs.append((pr["created_at"], pr["title"], pr["html_url"], reviewers))

    if output_csv:
        # CSV output
        print(f"SUMMARY: {len(open_prs)} total PRs, {unassigned_count} no reviewers, {len(old_prs)} open >30 days", file=sys.stderr)
        
        headers = ["PR Link", "Title", "CreatedDate", "LastModifiedDate", "LastCommentDate", "Age", "Reviewers"]
        writer = csv.writer(sys.stdout)
        writer.writerow(headers)
        
        for pr in open_prs:
            age = human_age(pr["created_at"])
            last_comment = get_last_comment_date(pr["number"])
            reviewers = get_reviewers(pr["number"])
            writer.writerow([
                pr["html_url"],
                pr["title"],
                pr["created_at"],
                pr["updated_at"],
                last_comment or "No comments",
                age,
                reviewers
            ])
    else:
        # Markdown output
        output = StringIO() if output_quip else sys.stdout
        print(file=output)
        print(f"# PR Summary {datetime.now().strftime('%Y-%m-%d')}", file=output)
        print(f"**{len(open_prs)} total PRs, {unassigned_count} no reviewers, {len(old_prs)} open >30 days**\n", file=output)
        
        print("## All Open PRs", file=output)
        print("| PR | Age | Reviewers |", file=output)
        print("|---|---|---|", file=output)
        for pr in open_prs:
            age = human_age(pr["created_at"])
            reviewers = get_reviewers(pr["number"])
            print(f"| [{pr['title']}]({pr['html_url']}) | {age} | {reviewers} |", file=output)

        print(file=output)

        if closed_prs:
            print("\n## Recently Closed PRs", file=output)
            print("| PR | Days to Close | Reviewers |", file=output)
            print("|---|---|---|", file=output)
            for pr in closed_prs:
                days_to_close = get_days_old(pr["created_at"])
                reviewers = get_reviewers(pr["number"])
                print(f"| [{pr['title']}]({pr['html_url']}) | {days_to_close} | {reviewers} |", file=output)

        print(file=output)

        if old_prs:
            print("\n## Old (>30 days) PRs", file=output)
            print("| Age | Title | Reviewers [State] |", file=output)
            print("| --- | --- | --- |", file=output)
            old_prs.sort()
            for created_at, title, url, reviewers in old_prs:
                days = get_days_old(created_at)
                print(f"| {days} | [{title}]({url}) | {reviewers}", file=output)
        
        if output_quip:
            markdown_content = output.getvalue()
            publish_to_quip(markdown_content, f"PR Summary - {REPO_OWNER}/{REPO_NAME}")
        else:
            # Already printed to stdout
            pass

if __name__ == "__main__":
    main()