"""
Test data generators for property-based testing.
Provides hypothesis strategies for generating PRs, snapshots, and reviewer strings.

Feature: pr-trend-enhancement
"""

from datetime import datetime, timedelta
from hypothesis import strategies as st


# Reviewer status values
REVIEWER_STATUSES = ["APPROVED", "NO ACTION", "CHANGES_REQUESTED", "COMMENTED"]


@st.composite
def reviewer_string(draw, min_reviewers=0, max_reviewers=5):
    """
    Generate a valid reviewer string in the format:
    "username1 [STATUS], username2 [STATUS], ..."
    
    Args:
        min_reviewers: Minimum number of reviewers (default 0)
        max_reviewers: Maximum number of reviewers (default 5)
    
    Returns:
        str: Reviewer string or None/"None" for no reviewers
    
    Examples:
        - None (no reviewers)
        - "None" (no reviewers)
        - "alice [APPROVED]"
        - "alice [APPROVED], bob [NO ACTION], charlie [APPROVED]"
    """
    num_reviewers = draw(st.integers(min_value=min_reviewers, max_value=max_reviewers))
    
    if num_reviewers == 0:
        # Return None or "None" for no reviewers
        return draw(st.sampled_from([None, "None"]))
    
    reviewers = []
    for _ in range(num_reviewers):
        username = draw(st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=3,
            max_size=15
        ))
        status = draw(st.sampled_from(REVIEWER_STATUSES))
        reviewers.append(f"{username} [{status}]")
    
    return ", ".join(reviewers)


@st.composite
def pr_record(draw, snapshot_id=None, fixed_created_at=None):
    """
    Generate a PR record with realistic data.
    
    Args:
        snapshot_id: Optional fixed snapshot_id (otherwise random)
        fixed_created_at: Optional fixed created_at datetime
    
    Returns:
        dict: PR record with all required fields
    """
    if fixed_created_at is None:
        # Generate created_at within last 180 days
        days_ago = draw(st.integers(min_value=0, max_value=180))
        created_at = datetime.now() - timedelta(days=days_ago)
    else:
        created_at = fixed_created_at
    
    # Generate updated_at (same or after created_at)
    days_since_created = draw(st.integers(min_value=0, max_value=30))
    updated_at = created_at + timedelta(days=days_since_created)
    
    # Calculate age_days from created_at to now
    age_days = (datetime.now() - created_at).days
    
    return {
        "id": draw(st.integers(min_value=1, max_value=1000000)),
        "snapshot_id": snapshot_id if snapshot_id is not None else draw(st.integers(min_value=1, max_value=10000)),
        "pr_number": draw(st.integers(min_value=1, max_value=10000)),
        "title": draw(st.text(min_size=10, max_size=100)),
        "url": f"https://github.com/owner/repo/pull/{draw(st.integers(min_value=1, max_value=10000))}",
        "created_at": created_at,
        "updated_at": updated_at,
        "age_days": age_days,
        "reviewers": draw(reviewer_string()),
        "state": draw(st.sampled_from(["open", "closed"])),
    }


@st.composite
def snapshot_record(draw, fixed_date=None):
    """
    Generate a snapshot record with realistic data.
    
    Args:
        fixed_date: Optional fixed snapshot_date datetime
    
    Returns:
        dict: Snapshot record with all required fields
    """
    if fixed_date is None:
        # Generate snapshot_date within last 90 days
        days_ago = draw(st.integers(min_value=0, max_value=90))
        snapshot_date = datetime.now() - timedelta(days=days_ago)
    else:
        snapshot_date = fixed_date
    
    return {
        "id": draw(st.integers(min_value=1, max_value=10000)),
        "snapshot_date": snapshot_date,
        "repo_owner": draw(st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=3,
            max_size=20
        )),
        "repo_name": draw(st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=3,
            max_size=30
        )),
        "total_prs": draw(st.integers(min_value=0, max_value=100)),
        "unassigned_count": draw(st.integers(min_value=0, max_value=50)),
        "old_prs_count": draw(st.integers(min_value=0, max_value=50)),
    }


@st.composite
def pr_set_for_snapshot(draw, snapshot_id, snapshot_date, min_prs=0, max_prs=60):
    """
    Generate a set of PRs for a specific snapshot.
    
    Args:
        snapshot_id: The snapshot ID these PRs belong to
        snapshot_date: The snapshot date (PRs created_at should be <= this)
        min_prs: Minimum number of PRs (default 0)
        max_prs: Maximum number of PRs (default 60)
    
    Returns:
        list: List of PR records
    """
    num_prs = draw(st.integers(min_value=min_prs, max_value=max_prs))
    prs = []
    
    for _ in range(num_prs):
        # Ensure PR created_at is before or equal to snapshot_date
        days_before_snapshot = draw(st.integers(min_value=0, max_value=180))
        created_at = snapshot_date - timedelta(days=days_before_snapshot)
        
        pr = draw(pr_record(snapshot_id=snapshot_id, fixed_created_at=created_at))
        prs.append(pr)
    
    return prs


# Convenience strategies for common use cases
reviewer_strings = reviewer_string()
pr_records = pr_record()
snapshot_records = snapshot_record()

# Strategies for specific scenarios
reviewer_with_approvals = reviewer_string(min_reviewers=1, max_reviewers=5)
reviewer_no_reviewers = st.sampled_from([None, "None"])
open_prs = pr_record().filter(lambda pr: pr["state"] == "open")
