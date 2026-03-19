"""
Verification tests for test data generators.
Ensures generators produce valid data for property-based testing.

Feature: pr-trend-enhancement
"""

import pytest
from hypothesis import given
from test_generators import (
    reviewer_string,
    pr_record,
    snapshot_record,
    pr_set_for_snapshot,
    REVIEWER_STATUSES,
)
from datetime import datetime


@pytest.mark.property
@given(reviewer_string())
def test_reviewer_string_generator(reviewers):
    """Verify reviewer_string generator produces valid formats."""
    if reviewers is None or reviewers == "None":
        # No reviewers case
        assert reviewers in [None, "None"]
    else:
        # Has reviewers - should be comma-separated with statuses
        assert isinstance(reviewers, str)
        assert len(reviewers) > 0
        
        # Check format: "username [STATUS], username2 [STATUS]"
        reviewer_entries = reviewers.split(", ")
        for entry in reviewer_entries:
            assert "[" in entry and "]" in entry
            # Extract status
            status_start = entry.rfind("[")
            status_end = entry.rfind("]")
            status = entry[status_start + 1 : status_end]
            assert status in REVIEWER_STATUSES


@pytest.mark.property
@given(pr_record())
def test_pr_record_generator(pr):
    """Verify pr_record generator produces valid PR data."""
    # Check required fields exist
    assert "id" in pr
    assert "snapshot_id" in pr
    assert "pr_number" in pr
    assert "title" in pr
    assert "url" in pr
    assert "created_at" in pr
    assert "updated_at" in pr
    assert "age_days" in pr
    assert "reviewers" in pr
    assert "state" in pr
    
    # Check field types and constraints
    assert isinstance(pr["id"], int) and pr["id"] > 0
    assert isinstance(pr["snapshot_id"], int) and pr["snapshot_id"] > 0
    assert isinstance(pr["pr_number"], int) and pr["pr_number"] > 0
    assert isinstance(pr["title"], str) and len(pr["title"]) >= 10
    assert isinstance(pr["url"], str) and pr["url"].startswith("https://")
    assert isinstance(pr["created_at"], datetime)
    assert isinstance(pr["updated_at"], datetime)
    assert isinstance(pr["age_days"], int) and pr["age_days"] >= 0
    assert pr["state"] in ["open", "closed"]
    
    # Check date consistency: updated_at >= created_at
    assert pr["updated_at"] >= pr["created_at"]


@pytest.mark.property
@given(snapshot_record())
def test_snapshot_record_generator(snapshot):
    """Verify snapshot_record generator produces valid snapshot data."""
    # Check required fields exist
    assert "id" in snapshot
    assert "snapshot_date" in snapshot
    assert "repo_owner" in snapshot
    assert "repo_name" in snapshot
    assert "total_prs" in snapshot
    assert "unassigned_count" in snapshot
    assert "old_prs_count" in snapshot
    
    # Check field types and constraints
    assert isinstance(snapshot["id"], int) and snapshot["id"] > 0
    assert isinstance(snapshot["snapshot_date"], datetime)
    assert isinstance(snapshot["repo_owner"], str) and len(snapshot["repo_owner"]) >= 3
    assert isinstance(snapshot["repo_name"], str) and len(snapshot["repo_name"]) >= 3
    assert isinstance(snapshot["total_prs"], int) and snapshot["total_prs"] >= 0
    assert isinstance(snapshot["unassigned_count"], int) and snapshot["unassigned_count"] >= 0
    assert isinstance(snapshot["old_prs_count"], int) and snapshot["old_prs_count"] >= 0


@pytest.mark.property
def test_pr_set_for_snapshot_generator():
    """Verify pr_set_for_snapshot generator produces valid PR sets."""
    # Just verify the generator can be called and returns a strategy
    # The actual testing will be done in integration tests
    from datetime import datetime
    
    snapshot_id = 1
    snapshot_date = datetime.now()
    
    # Verify the generator returns a strategy
    strategy = pr_set_for_snapshot(
        snapshot_id=snapshot_id,
        snapshot_date=snapshot_date,
        min_prs=0,
        max_prs=10,
    )
    
    # Verify it's a valid hypothesis strategy
    assert hasattr(strategy, 'example')
    
    # Generate one example to verify it works
    # (This is acceptable for a simple verification test)
    prs = strategy.example()
    assert isinstance(prs, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "property"])
