"""
Property-based tests for import_historical_snapshots.py

This test file contains bug condition exploration tests and preservation tests
for the check_snapshot_exists() function.
"""

import pytest
import duckdb
import os
import tempfile
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, HealthCheck
import import_historical_snapshots


# Strategy for generating valid date strings in YYYY-MM-DD format
date_strategy = st.dates(
    min_value=datetime(2020, 1, 1).date(),
    max_value=datetime(2030, 12, 31).date()
).map(lambda d: d.strftime("%Y-%m-%d"))


class TestCheckSnapshotExists:
    """Tests for the check_snapshot_exists() function"""
    
    def setup_empty_db(self):
        """Create a temporary empty database for testing"""
        # Create a temporary database file path (don't create the file yet)
        fd, db_path = tempfile.mkstemp(suffix='.duckdb')
        os.close(fd)
        os.unlink(db_path)  # Remove the empty file so DuckDB can create it properly
        
        # Store original DB_PATH
        self.original_db_path = import_historical_snapshots.DB_PATH
        
        # Set the module to use our test database
        import_historical_snapshots.DB_PATH = db_path
        
        # Create the schema
        conn = duckdb.connect(db_path)
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS pr_snapshots_seq START 1
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pr_snapshots (
                id INTEGER PRIMARY KEY DEFAULT nextval('pr_snapshots_seq'),
                snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                repo_owner VARCHAR NOT NULL,
                repo_name VARCHAR NOT NULL,
                total_prs INTEGER,
                unassigned_count INTEGER,
                old_prs_count INTEGER
            )
        """)
        conn.close()
        
        return db_path
    
    def teardown_db(self, db_path):
        """Cleanup test database"""
        import_historical_snapshots.DB_PATH = self.original_db_path
        try:
            os.unlink(db_path)
        except:
            pass
    
    @given(date_str=date_strategy)
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_1_empty_database_returns_false(self, date_str):
        """
        Property 1: Fault Condition - Empty Database Incorrectly Returns True
        
        **Validates: Requirements 2.1, 2.2**
        
        CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
        
        For any date string in "YYYY-MM-DD" format where the pr_snapshots table 
        contains no records, check_snapshot_exists() should return False.
        
        Bug Condition: isBugCondition(input) where 
            input.db_state.pr_snapshots.count == 0 
            AND check_snapshot_exists(input.date_str) == True
        
        Expected Behavior: check_snapshot_exists() returns False when no matching 
        snapshot exists.
        
        This test encodes the expected behavior and will validate the fix when it 
        passes after implementation.
        """
        # Setup empty database for each example
        db_path = self.setup_empty_db()
        
        try:
            # Verify database is empty
            conn = duckdb.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM pr_snapshots").fetchone()[0]
            conn.close()
            assert count == 0, "Database should be empty for this test"
            
            # Test the function - should return False for empty database
            result = import_historical_snapshots.check_snapshot_exists(date_str)
            
            # EXPECTED TO FAIL ON UNFIXED CODE
            # The bug causes this to return True even when database is empty
            assert result == False, (
                f"check_snapshot_exists('{date_str}') returned True on empty database. "
                f"Expected False. This is the bug condition."
            )
        finally:
            # Cleanup
            self.teardown_db(db_path)
    
    def test_empty_database_specific_dates(self):
        """
        Additional test with specific date examples to document the bug.
        
        This test uses concrete examples to demonstrate the bug behavior.
        """
        # Setup empty database
        db_path = self.setup_empty_db()
        
        try:
            # Verify database is empty
            conn = duckdb.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM pr_snapshots").fetchone()[0]
            conn.close()
            assert count == 0, "Database should be empty"
            
            # Test specific dates that should all return False
            test_dates = [
                "2025-01-15",
                "2024-12-25",
                "2023-06-30",
                "2025-02-28",
                "2024-02-29",  # Leap year
            ]
            
            for date_str in test_dates:
                result = import_historical_snapshots.check_snapshot_exists(date_str)
                assert result == False, (
                    f"check_snapshot_exists('{date_str}') returned True on empty database. "
                    f"Expected False. Counterexample found: empty database with date '{date_str}'"
                )
        finally:
            # Cleanup
            self.teardown_db(db_path)
    
    def insert_snapshot(self, db_path, date_str, repo_owner="awslabs", repo_name="test-repo"):
        """Helper method to insert a snapshot for a specific date"""
        conn = duckdb.connect(db_path)
        conn.execute("""
            INSERT INTO pr_snapshots (snapshot_date, repo_owner, repo_name, total_prs, unassigned_count, old_prs_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [date_str, repo_owner, repo_name, 10, 2, 3])
        conn.close()
    
    @given(date_str=date_strategy)
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_existing_snapshot_detected(self, date_str):
        """
        Property 2: Preservation - Existing Duplicates Still Detected
        
        **Validates: Requirements 3.1**
        
        For any date string where a snapshot record already exists in the pr_snapshots 
        table with a matching snapshot_date (same calendar day), check_snapshot_exists() 
        should return True, preserving the existing duplicate detection behavior.
        
        This test observes the behavior on UNFIXED code and ensures it is preserved 
        after the fix.
        
        EXPECTED OUTCOME: Test PASSES on unfixed code (confirms baseline behavior).
        """
        # Setup database with a snapshot for the test date
        db_path = self.setup_empty_db()
        
        try:
            # Insert a snapshot for this date
            self.insert_snapshot(db_path, date_str)
            
            # Verify snapshot was inserted
            conn = duckdb.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM pr_snapshots").fetchone()[0]
            conn.close()
            assert count == 1, "Database should have exactly one snapshot"
            
            # Test the function - should return True when snapshot exists
            result = import_historical_snapshots.check_snapshot_exists(date_str)
            
            # This should PASS on unfixed code (preservation of existing behavior)
            assert result == True, (
                f"check_snapshot_exists('{date_str}') returned False when snapshot exists. "
                f"Expected True. This is the preservation behavior we must maintain."
            )
        finally:
            # Cleanup
            self.teardown_db(db_path)
    
    def test_preservation_exact_date_match(self):
        """
        Test exact date match preservation.
        
        When a snapshot exists for a specific date, check_snapshot_exists() 
        should return True for that exact date.
        """
        db_path = self.setup_empty_db()
        
        try:
            # Insert snapshot for specific date
            test_date = "2025-01-15"
            self.insert_snapshot(db_path, test_date)
            
            # Should return True for exact match
            result = import_historical_snapshots.check_snapshot_exists(test_date)
            assert result == True, (
                f"check_snapshot_exists('{test_date}') should return True when "
                f"snapshot exists for that date"
            )
        finally:
            self.teardown_db(db_path)
    
    def test_preservation_different_date_no_match(self):
        """
        Test that different dates don't match.
        
        When a snapshot exists for date A, check_snapshot_exists() should 
        return False for date B (where B != A).
        """
        db_path = self.setup_empty_db()
        
        try:
            # Insert snapshot for 2025-01-15
            self.insert_snapshot(db_path, "2025-01-15")
            
            # Should return False for different dates
            different_dates = [
                "2025-01-14",  # Day before
                "2025-01-16",  # Day after
                "2025-01-20",  # Different day same month
                "2025-02-15",  # Different month same day
                "2024-01-15",  # Different year same month/day
            ]
            
            for date_str in different_dates:
                result = import_historical_snapshots.check_snapshot_exists(date_str)
                assert result == False, (
                    f"check_snapshot_exists('{date_str}') should return False when "
                    f"only snapshot for 2025-01-15 exists, but got True"
                )
        finally:
            self.teardown_db(db_path)
    
    def test_preservation_multiple_snapshots(self):
        """
        Test with multiple snapshots in database.
        
        When multiple snapshots exist for different dates, check_snapshot_exists() 
        should correctly identify which dates have snapshots.
        """
        db_path = self.setup_empty_db()
        
        try:
            # Insert snapshots for multiple dates
            snapshot_dates = [
                "2025-01-01",
                "2025-01-08",
                "2025-01-15",
                "2025-01-22",
            ]
            
            for date_str in snapshot_dates:
                self.insert_snapshot(db_path, date_str)
            
            # Verify all snapshot dates return True
            for date_str in snapshot_dates:
                result = import_historical_snapshots.check_snapshot_exists(date_str)
                assert result == True, (
                    f"check_snapshot_exists('{date_str}') should return True when "
                    f"snapshot exists for that date"
                )
            
            # Verify dates without snapshots return False
            non_snapshot_dates = [
                "2025-01-05",  # Between first two
                "2025-01-10",  # Between second and third
                "2025-01-30",  # After all
                "2024-12-25",  # Before all
            ]
            
            for date_str in non_snapshot_dates:
                result = import_historical_snapshots.check_snapshot_exists(date_str)
                assert result == False, (
                    f"check_snapshot_exists('{date_str}') should return False when "
                    f"no snapshot exists for that date, but got True"
                )
        finally:
            self.teardown_db(db_path)
    
    def test_preservation_timestamp_precision(self):
        """
        Test that date-only check matches regardless of timestamp precision.
        
        When a snapshot exists with a specific timestamp (e.g., 2025-01-15 14:30:00),
        check_snapshot_exists() should return True for the date string "2025-01-15"
        (date-only check should match).
        """
        db_path = self.setup_empty_db()
        
        try:
            # Insert snapshot with specific timestamp
            conn = duckdb.connect(db_path)
            conn.execute("""
                INSERT INTO pr_snapshots (snapshot_date, repo_owner, repo_name, total_prs, unassigned_count, old_prs_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ["2025-01-15 14:30:00", "awslabs", "test-repo", 10, 2, 3])
            conn.close()
            
            # Should return True for date-only string
            result = import_historical_snapshots.check_snapshot_exists("2025-01-15")
            assert result == True, (
                "check_snapshot_exists('2025-01-15') should return True when "
                "snapshot exists with timestamp 2025-01-15 14:30:00"
            )
            
            # Test with different times on same day
            conn = duckdb.connect(db_path)
            conn.execute("""
                INSERT INTO pr_snapshots (snapshot_date, repo_owner, repo_name, total_prs, unassigned_count, old_prs_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ["2025-01-20 08:00:00", "awslabs", "test-repo", 5, 1, 2])
            conn.execute("""
                INSERT INTO pr_snapshots (snapshot_date, repo_owner, repo_name, total_prs, unassigned_count, old_prs_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ["2025-01-20 23:59:59", "awslabs", "test-repo", 8, 3, 1])
            conn.close()
            
            # Should return True for date with multiple timestamps
            result = import_historical_snapshots.check_snapshot_exists("2025-01-20")
            assert result == True, (
                "check_snapshot_exists('2025-01-20') should return True when "
                "multiple snapshots exist for that date with different timestamps"
            )
        finally:
            self.teardown_db(db_path)
