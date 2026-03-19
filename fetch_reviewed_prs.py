#!/usr/bin/env python3
import requests
import os
from collections import defaultdict
from datetime import datetime

def fetch_reviewed_prs(username, year, token):
    headers = {"Authorization": f"token {token}"}
    prs = []
    page = 1
    
    while True:
        url = "https://api.github.com/search/issues"
        params = {
            "q": f"reviewed-by:{username} type:pr created:{year}-01-01..{year}-12-31",
            "per_page": 100,
            "page": page,
            "sort": "created",
            "order": "desc"
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            break
            
        data = response.json()
        if not data.get('items'):
            break
            
        prs.extend(data['items'])
        page += 1
        
        if page > 10:  # Safety limit
            break
    
    return prs

def main():
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("Error: Set GITHUB_TOKEN environment variable")
        return
    
    username = "burhan94"
    year = 2025
    
    prs = fetch_reviewed_prs(username, year, token)
    
    # Count by month
    monthly_counts = defaultdict(int)
    monthly_prs = defaultdict(list)
    
    for pr in prs:
        created_date = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
        month_key = created_date.strftime('%Y-%m')
        monthly_counts[month_key] += 1
        monthly_prs[month_key].append(pr)
    
    print(f"# PRs Reviewed by {username} in {year}\n")
    print("## Monthly Summary\n")
    
    total = 0
    for month in sorted(monthly_counts.keys()):
        count = monthly_counts[month]
        total += count
        print(f"**{month}:** {count} PRs")
    
    print(f"\n**Total:** {total} PRs\n")
    
    print("## Full List by Month\n")
    
    for month in sorted(monthly_prs.keys()):
        print(f"### {month} ({monthly_counts[month]} PRs)\n")
        for pr in monthly_prs[month]:
            print(f"- [{pr['title']}]({pr['html_url']})")
        print()

if __name__ == "__main__":
    main()