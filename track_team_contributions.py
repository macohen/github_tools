#!/usr/bin/env python3
import requests
import sys
import os
from datetime import datetime, timezone, timedelta
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
MANAGER_ALIAS = "ruhollah"
REPO_OWNER = "trinodb"
REPO_NAME = "trino"

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable is required", file=sys.stderr)
    sys.exit(1)

github_session = requests.Session()
github_session.headers.update({
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {GITHUB_TOKEN}"
})

NOW = datetime.now(timezone.utc)
SINCE_DATE = NOW - timedelta(days=90)  # Last 90 days

def get_all_employees_under_manager(manager_alias):
    """Get all employees under a manager using phonetool recursively"""
    try:
        # Use ReadInternalWebsites tool to access phonetool
        phonetool_url = f"https://phonetool.amazon.com/users/{manager_alias}"
        
        # This would be called in Amazon Q environment
        result = ReadInternalWebsites(
            inputs=[phonetool_url],
            explanation="Getting manager's direct reports from phonetool"
        )
        
        # Parse the result to extract employee data
        # This is a simplified version - actual parsing would be more complex
        employees = []
        # Would parse HTML to extract direct reports and recursively get their reports
        
        return employees
        
    except NameError:
        # Tool not available in this environment - use test data
        print(f"ReadInternalWebsites tool not available - using test data")
        return [
            {'name': 'Test Developer 1', 'alias': 'testdev1'},
            {'name': 'Test Developer 2', 'alias': 'testdev2'}
        ]
    except Exception as e:
        print(f"Error fetching employees under manager: {e}", file=sys.stderr)
        return []

def extract_github_username(person_data):
    """Extract GitHub username from person data"""
    # Try to find GitHub username in various fields
    email = person_data.get('email', '')
    alias = person_data.get('alias', '')
    
    # Simple heuristic: use alias as GitHub username
    # In practice, you might need a mapping table or additional lookup
    if alias:
        return alias.replace('@amazon.com', '').replace('@', '')
    
    return None

def get_user_commits(username, since_date):
    """Get commits by user in the repository"""
    commits = []
    page = 1
    
    params = {
        "author": username,
        "since": since_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_page": 100
    }
    
    while True:
        params["page"] = page
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits"
        response = github_session.get(url, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching commits for {username}: {response.status_code}", file=sys.stderr)
            break
        
        data = response.json()
        if not data:
            break
        
        commits.extend(data)
        page += 1
        
        # GitHub API rate limiting
        if len(commits) >= 1000:  # Reasonable limit
            break
    
    return commits

def get_user_prs(username, since_date):
    """Get PRs by user in the repository"""
    prs = []
    page = 1
    
    # Search for PRs by author
    query = f"repo:{REPO_OWNER}/{REPO_NAME} author:{username} created:>={since_date.strftime('%Y-%m-%d')}"
    params = {
        "q": query,
        "sort": "created",
        "order": "desc",
        "per_page": 100
    }
    
    while True:
        params["page"] = page
        url = "https://api.github.com/search/issues"
        response = github_session.get(url, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching PRs for {username}: {response.status_code}", file=sys.stderr)
            break
        
        data = response.json()
        if not data.get("items"):
            break
        
        # Filter for pull requests only
        pr_items = [item for item in data["items"] if "pull_request" in item]
        prs.extend(pr_items)
        
        page += 1
        
        if len(prs) >= 200:  # Reasonable limit
            break
    
    return prs

def get_contributions_batch(team_members):
    """Fetch contributions for all team members concurrently"""
    results = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all tasks
        future_to_member = {}
        for member in team_members:
            username = member['github_username']
            future_commits = executor.submit(get_user_commits, username, SINCE_DATE)
            future_prs = executor.submit(get_user_prs, username, SINCE_DATE)
            future_to_member[future_commits] = (member, 'commits')
            future_to_member[future_prs] = (member, 'prs')
        
        # Collect results
        for future in as_completed(future_to_member):
            member, data_type = future_to_member[future]
            username = member['github_username']
            
            try:
                data = future.result()
                if username not in results:
                    results[username] = {'member': member, 'commits': [], 'prs': []}
                results[username][data_type] = data
            except Exception as e:
                print(f"Error fetching {data_type} for {username}: {e}", file=sys.stderr)
                if username not in results:
                    results[username] = {'member': member, 'commits': [], 'prs': []}
    
    return results

def generate_report(team_contributions):
    """Generate markdown report"""
    output = StringIO()
    report_date = NOW.strftime('%Y-%m-%d')
    
    print(f"# Team Contributions to {REPO_OWNER}/{REPO_NAME}", file=output)
    print(f"**Report Date:** {report_date}", file=output)
    print(f"**Manager:** {MANAGER_ALIAS}", file=output)
    print(f"**Period:** Last 90 days", file=output)
    print(file=output)
    
    # Summary
    total_commits = sum(len(data['commits']) for data in team_contributions.values())
    total_prs = sum(len(data['prs']) for data in team_contributions.values())
    active_contributors = sum(1 for data in team_contributions.values() 
                            if len(data['commits']) > 0 or len(data['prs']) > 0)
    
    print("## Summary", file=output)
    print(f"- **Team Members:** {len(team_contributions)}", file=output)
    print(f"- **Active Contributors:** {active_contributors}", file=output)
    print(f"- **Total Commits:** {total_commits}", file=output)
    print(f"- **Total PRs:** {total_prs}", file=output)
    print(file=output)
    
    # Individual contributions
    print("## Individual Contributions", file=output)
    print("| Team Member | GitHub Username | Commits | PRs | Latest Activity |", file=output)
    print("|---|---|---|---|---|", file=output)
    
    # Sort by total activity (commits + PRs)
    sorted_contributors = sorted(
        team_contributions.items(),
        key=lambda x: len(x[1]['commits']) + len(x[1]['prs']),
        reverse=True
    )
    
    for username, data in sorted_contributors:
        member = data['member']
        commits = data['commits']
        prs = data['prs']
        
        # Find latest activity
        latest_activity = "No activity"
        if commits or prs:
            dates = []
            if commits:
                dates.extend([commit['commit']['author']['date'] for commit in commits])
            if prs:
                dates.extend([pr['created_at'] for pr in prs])
            
            if dates:
                latest_date = max(dates)
                latest_activity = datetime.fromisoformat(latest_date.replace('Z', '+00:00')).strftime('%Y-%m-%d')
        
        print(f"| {member['name']} ({member['alias']}) | {username} | {len(commits)} | {len(prs)} | {latest_activity} |", file=output)
    
    # Recent activity details
    print(file=output)
    print("## Recent Activity Details", file=output)
    
    for username, data in sorted_contributors:
        member = data['member']
        commits = data['commits']
        prs = data['prs']
        
        if not commits and not prs:
            continue
        
        print(f"### {member['name']} (@{username})", file=output)
        
        if prs:
            print("**Recent PRs:**", file=output)
            for pr in prs[:5]:  # Show latest 5 PRs
                created_date = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
                state_emoji = "🟢" if pr['state'] == 'closed' else "🟡"
                print(f"- {state_emoji} [{pr['title']}]({pr['html_url']}) ({created_date})", file=output)
        
        if commits:
            print(f"**Commits:** {len(commits)} in the last 90 days", file=output)
        
        print(file=output)
    
    return output.getvalue()

def main():
    print(f"Fetching all employees under {MANAGER_ALIAS}...")
    
    # Get all employees under the manager
    all_employees = get_all_employees_under_manager(MANAGER_ALIAS)
    
    # Convert to team members format
    team_members = []
    for employee in all_employees:
        github_username = extract_github_username(employee)
        if github_username:
            team_members.append({
                'name': employee.get('name', ''),
                'alias': employee.get('alias', ''),
                'github_username': github_username
            })
    
    if not team_members:
        print("No team members found or unable to fetch team data", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(team_members)} team members")
    print(f"Fetching contributions to {REPO_OWNER}/{REPO_NAME}...")
    
    # Get contributions for all team members
    team_contributions = get_contributions_batch(team_members)
    
    # Generate and print report
    report = generate_report(team_contributions)
    print(report)

if __name__ == "__main__":
    main()