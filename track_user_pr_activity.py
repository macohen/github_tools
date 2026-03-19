#!/usr/bin/env python3
import requests
import sys
import os
import argparse
from datetime import datetime, timezone, timedelta
from io import StringIO

# Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable is required", file=sys.stderr)
    sys.exit(1)

github_session = requests.Session()
github_session.headers.update({
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {GITHUB_TOKEN}"
})

def get_authored_prs(username, repo_owner, repo_name, start_date, end_date):
    """Get PRs authored by user in timeframe using direct API calls"""
    authored_prs = []
    page = 1
    
    # Get all PRs and filter by author and date
    while True:
        params = {
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "per_page": 100,
            "page": page
        }
        
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
        print(f"API call: GET {url}?page={page}&per_page=100", file=sys.stderr)
        response = github_session.get(url, params=params)
        if response.status_code != 200:
            print(f"Error fetching PRs: {response.status_code} - {response.text}", file=sys.stderr)
            break
        
        prs = response.json()
        if not prs:
            break
        
        # Filter PRs by author and date range
        for pr in prs:
            pr_created = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
            
            # Stop if PR is older than our date range (PRs are sorted by created date desc)
            if pr_created < start_date:
                return authored_prs
            
            # Check if PR is in our date range and by the target user
            if (pr_created >= start_date and 
                pr_created <= end_date and 
                pr.get('user', {}).get('login') == username):
                authored_prs.append(pr)
        
        page += 1
        if len(authored_prs) >= 200:  # Reasonable limit
            break
    
    return authored_prs

def get_reviewed_prs(username, repo_owner, repo_name, start_date, end_date):
    """Get PRs reviewed by user in timeframe using direct API calls"""
    reviewed_prs = []
    page = 1
    
    # First get all PRs in the timeframe, then check reviews
    while True:
        params = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": 100,
            "page": page
        }
        
        response = github_session.get(f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls", params=params)
        print(f"API call: GET /repos/{repo_owner}/{repo_name}/pulls?page={page}&per_page=100", file=sys.stderr)
        if response.status_code != 200:
            print(f"Error fetching PRs: {response.status_code} - {response.text}", file=sys.stderr)
            break
        
        prs = response.json()
        if not prs:
            break
        
        # Check each PR for reviews by the user
        for pr in prs:
            pr_updated = datetime.fromisoformat(pr['updated_at'].replace('Z', '+00:00'))
            if pr_updated < start_date:
                return reviewed_prs  # PRs are sorted by updated date, so we can stop
            if pr_updated > end_date:
                continue
            
            # Check if user reviewed this PR
            reviews_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr['number']}/reviews"
            print(f"API call: GET /repos/{repo_owner}/{repo_name}/pulls/{pr['number']}/reviews", file=sys.stderr)
            reviews_response = github_session.get(reviews_url)
            
            if reviews_response.status_code == 200:
                reviews = reviews_response.json()
                user_reviewed = any(review.get('user', {}).get('login') == username for review in reviews)
                
                if user_reviewed:
                    reviewed_prs.append(pr)
        
        page += 1
        if len(reviewed_prs) >= 200:  # Reasonable limit
            break
    
    return reviewed_prs

def generate_report(username, authored_prs, reviewed_prs, start_date, end_date, repo_owner, repo_name):
    """Generate markdown report"""
    output = StringIO()
    
    print(f"# PR Activity Report for @{username}", file=output)
    print(f"**Repository:** {repo_owner}/{repo_name}", file=output)
    print(f"**Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", file=output)
    print(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", file=output)
    print(file=output)
    
    # Summary
    print("## Summary", file=output)
    print(f"- **PRs Authored:** {len(authored_prs)}", file=output)
    print(f"- **PRs Reviewed:** {len(reviewed_prs)}", file=output)
    print(file=output)
    
    # Authored PRs
    if authored_prs:
        print("## PRs Authored", file=output)
        print("| Title | State | Created | Merged |", file=output)
        print("|---|---|---|---|", file=output)
        
        for pr in authored_prs:
            created_date = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
            merged_date = "Not merged"
            if pr.get('merged_at'):
                merged_date = datetime.fromisoformat(pr['merged_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
            
            state_emoji = "🟢" if pr['state'] == 'closed' else "🟡"
            print(f"| {state_emoji} [{pr['title']}]({pr['html_url']}) | {pr['state']} | {created_date} | {merged_date} |", file=output)
        print(file=output)
    
    # Reviewed PRs
    if reviewed_prs:
        print("## PRs Reviewed", file=output)
        print("| Title | Author | State | Updated |", file=output)
        print("|---|---|---|---|", file=output)
        
        for pr in reviewed_prs:
            updated_date = datetime.fromisoformat(pr['updated_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
            author = pr.get('user', {}).get('login', 'Unknown')
            
            state_emoji = "🟢" if pr['state'] == 'closed' else "🟡"
            print(f"| {state_emoji} [{pr['title']}]({pr['html_url']}) | @{author} | {pr['state']} | {updated_date} |", file=output)
        print(file=output)
    
    return output.getvalue()

def main():
    parser = argparse.ArgumentParser(description='Track PRs authored and reviewed by a GitHub user')
    parser.add_argument('username', help='GitHub username to track')
    parser.add_argument('repo_owner', help='Repository owner (e.g., trinodb)')
    parser.add_argument('repo_name', help='Repository name (e.g., trino)')
    parser.add_argument('--days', type=int, default=30, help='Number of days to look back (default: 30)')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Parse dates
    if args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=args.days)
    
    print(f"Fetching PRs for @{args.username} in {args.repo_owner}/{args.repo_name}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Fetch authored PRs
    print("Fetching authored PRs...")
    authored_prs = get_authored_prs(args.username, args.repo_owner, args.repo_name, start_date, end_date)
    
    # Fetch reviewed PRs
    print("Fetching reviewed PRs...")
    reviewed_prs = get_reviewed_prs(args.username, args.repo_owner, args.repo_name, start_date, end_date)
    
    # Generate report
    report = generate_report(args.username, authored_prs, reviewed_prs, start_date, end_date, args.repo_owner, args.repo_name)
    print(report)

if __name__ == "__main__":
    main()