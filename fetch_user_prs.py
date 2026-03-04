#!/usr/bin/env python3
import requests
import argparse
import os
from datetime import datetime

def get_complexity(pr):
    """Estimate complexity based on additions + deletions"""
    total_changes = pr.get('additions', 0) + pr.get('deletions', 0)
    if total_changes < 10:
        return "Low"
    elif total_changes < 30:
        return "Medium"
    else:
        return "High"

def fetch_user_reviewed_prs(username, since_date, token):
    headers = {"Authorization": f"token {token}"}
    url = f"https://api.github.com/search/issues"
    params = {
        "q": f"reviewed-by:{username} type:pr created:>={since_date}",
        "per_page": 100
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('total_count', 0)
    return 0

def fetch_user_prs(username, since_date, token):
    headers = {"Authorization": f"token {token}"}
    prs = []
    page = 1
    
    while True:
        url = f"https://api.github.com/search/issues"
        params = {
            "q": f"author:{username} type:pr created:>={since_date}",
            "per_page": 100,
            "page": page
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            break
            
        data = response.json()
        if not data.get('items'):
            break
            
        for item in data['items']:
            # Get detailed PR info for complexity
            pr_url = item['pull_request']['url']
            pr_response = requests.get(pr_url, headers=headers)
            if pr_response.status_code == 200:
                pr_data = pr_response.json()
                prs.append({
                    'url': item['html_url'],
                    'state': item['state'],
                    'comments': item['comments'],
                    'complexity': get_complexity(pr_data)
                })
        
        page += 1
        if page > 10:  # Safety limit
            break
    
    return prs

def main():
    parser = argparse.ArgumentParser(description='Fetch PRs for a user')
    parser.add_argument('username', help='GitHub username or comma-separated list')
    parser.add_argument('--since', required=True, help='Date in YYYY-MM-DD format')
    parser.add_argument('--token', default=os.getenv('GITHUB_TOKEN'), help='GitHub token')
    
    args = parser.parse_args()
    
    if not args.token:
        print("Error: GitHub token required (set GITHUB_TOKEN env var or use --token)")
        return
    
    usernames = [u.strip() for u in args.username.split(',')]
    
    for username in usernames:
        prs = fetch_user_prs(username, args.since, args.token)
        reviewed_count = fetch_user_reviewed_prs(username, args.since, args.token)
        
        print(f"\n## {username}\n")
        print(f"**PRs Reviewed:** {reviewed_count}\n")
        print("| URL | State | Comments | Complexity |")
        print("|-----|-------|----------|------------|")
        
        for pr in prs:
            print(f"| [{pr['url']}]({pr['url']}) | {pr['state']} | {pr['comments']} | {pr['complexity']} |")


if __name__ == "__main__":
    main()