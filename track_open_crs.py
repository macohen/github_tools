import sys
import csv
from datetime import datetime, timezone
from search_internal_code import search_internal_code

def fetch_open_crs(package_filter=None):
    """Fetch open CRs using internal code search"""
    try:
        # Search for open CRs - adjust query as needed for your use case
        query = "state:open type:cr"
        if package_filter:
            query += f" package:{package_filter}"
            
        result = search_internal_code(
            query=query,
            explanation="Fetching open code reviews for tracking"
        )
        
        # Parse results - structure depends on actual API response
        crs = []
        if 'results' in result:
            for cr in result['results']:
                crs.append({
                    'id': cr.get('id'),
                    'title': cr.get('title', 'No title'),
                    'author': cr.get('author'),
                    'created_at': cr.get('created_at'),
                    'updated_at': cr.get('updated_at'),
                    'reviewers': cr.get('reviewers', []),
                    'url': cr.get('url'),
                    'package': cr.get('package')
                })
        return crs
    except Exception as e:
        print(f"Error fetching CRs: {e}", file=sys.stderr)
        return []

def human_age(created_at):
    """Convert timestamp to human readable age"""
    if not created_at:
        return "Unknown"
    
    try:
        now = datetime.now(timezone.utc)
        if isinstance(created_at, str):
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created = created_at
        
        delta = now - created
        days = delta.days
        hours = delta.seconds // 3600
        return f"{days}d {hours}h"
    except:
        return "Unknown"

def get_days_old(created_at):
    """Get number of days since creation"""
    if not created_at:
        return 0
    
    try:
        now = datetime.now(timezone.utc)
        if isinstance(created_at, str):
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created = created_at
        return (now - created).days
    except:
        return 0

def format_reviewers(reviewers):
    """Format reviewers list"""
    if not reviewers:
        return "None"
    if isinstance(reviewers, list):
        return ", ".join(reviewers)
    return str(reviewers)

def main():
    package_filter = sys.argv[1] if len(sys.argv) > 1 else None
    
    crs = fetch_open_crs(package_filter)
    rows = []
    unassigned_count = 0
    old_crs = []
    
    for cr in crs:
        cr_url = cr.get('url', 'No URL')
        cr_title = cr.get('title', 'No title')
        created_at = cr.get('created_at')
        updated_at = cr.get('updated_at')
        age = human_age(created_at)
        reviewers = format_reviewers(cr.get('reviewers'))
        author = cr.get('author', 'Unknown')
        package = cr.get('package', 'Unknown')
        
        # Count statistics
        if reviewers == "None":
            unassigned_count += 1
        if get_days_old(created_at) > 30:
            old_crs.append((created_at, cr_title, cr_url, reviewers))
        
        rows.append([
            cr_url,
            cr_title,
            created_at or "Unknown",
            updated_at or "Unknown",
            age,
            author,
            reviewers,
            package
        ])

    # Print summary to stderr
    print(f"SUMMARY: {len(crs)} total CRs, {unassigned_count} unassigned, {len(old_crs)} open >30 days", file=sys.stderr)
    
    if old_crs:
        print(f"\n{len(old_crs)} CRs open >30 days (oldest first):", file=sys.stderr)
        old_crs.sort()
        for created_at, title, url, reviewers in old_crs:
            days = get_days_old(created_at)
            print(f"  {days} days: {url}; reviewers: {reviewers}", file=sys.stderr)
    
    headers = ["CR Link", "Title", "CreatedDate", "LastModifiedDate", "Age", "Author", "Reviewers", "Package"]
    
    writer = csv.writer(sys.stdout)
    writer.writerow(headers)
    writer.writerows(rows)

if __name__ == "__main__":
    main()