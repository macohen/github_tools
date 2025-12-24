# save as compute_pr_average_age.py
# Requires: pip install requests python-dateutil
import os, requests, math
from dateutil import parser
from datetime import datetime, timezone

from dateutil.parser import isoparse

OWNER = "awslabs"
REPO = "aws-athena-query-federation"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # set this in your environment

# Interval: set start_date (inclusive) and end_date (exclusive or inclusive as you prefer)
class Interval:
    def __init__(self, start_date, end_date):
        self.start_date = parser.isoparse(start_date)
        self.end_date = parser.isoparse(end_date)


intervals = [
    Interval("2025-07-01T00:00:00Z", "2025-09-01T00:00:00Z"),
    Interval("2025-09-01T00:00:00Z", "2025-11-01T00:00:00Z"),
    Interval("2025-11-01T00:00:00Z", "2025-11-30T00:00:00Z"),
    Interval("2025-12-01T00:00:00Z", "2025-12-24T00:00:00Z")
]

headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
per_page = 100
page = 1
prs = []

while True:
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"
    params = {"state": "all", "per_page": per_page, "page": page, "sort": "created", "direction": "asc"}
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    batch = r.json()
    if not batch:
        break
    prs.extend(batch)
    page += 1

def was_open_during_interval(pr):
    created = parser.isoparse(pr["created_at"])
    closed = pr["closed_at"]
    closed_dt = parser.isoparse(closed) if closed else None
    # PR open at any point in [start_dt, end_dt)
    # condition: created < end_dt and (closed is None or closed > start_dt)
    return (created < end_dt) and (closed_dt is None or closed_dt > start_dt)

for interval in intervals:
    start_dt = interval.start_date
    end_dt = interval.end_date
    interval_end = interval.end_date.isoformat()
    ages_days = []
    for pr in prs:
        if was_open_during_interval(pr):
            created = parser.isoparse(pr["created_at"])
            age_td = end_dt - created
            age_days = age_td.total_seconds() / 86400.0
            ages_days.append(age_days)

    if not ages_days:
        print("No PRs matched the interval criteria.")
    else:
        avg_days = sum(ages_days) / len(ages_days)
        median = sorted(ages_days)[len(ages_days)//2]
        print(f"PRs considered: {len(ages_days)}")
        print(f"Average age (days) as of {interval_end}: {avg_days:.2f}")
        print(f"Median age (days): {median:.2f}")



# PRs considered: 150
# Average age (days) as of 2025-09-01T00:00:00Z: 70.99
# Median age (days): 40.18

# PRs considered: 143
# Average age (days) as of 2025-11-01T00:00:00Z: 57.30
# Median age (days): 32.69