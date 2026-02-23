import unittest
import json
import os
import tempfile
import duckdb
from datetime import datetime

# Set test database path BEFORE importing server module
os.environ['DB_PATH'] = ':memory:'  # Default to in-memory for tests

from server import app, get_db, init_db


class TestPRTrackerAPI(unittest.TestCase):
    
    def setUp(self):
        """Set up test database and client"""
        # Reset the global in-memory connection for test isolation
        import server
        server._memory_db_conn = None
        
        # Create a unique test database file with .duckdb extension
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.duckdb')
        os.close(self.db_fd)  # Close immediately, DuckDB will handle the file
        os.environ['DB_PATH'] = ':memory:'  # Use in-memory for tests
        
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Initialize database
        with self.app.app_context():
            init_db()
    
    def tearDown(self):
        """Clean up test database"""
        # Reset the global in-memory connection
        import server
        if server._memory_db_conn:
            server._memory_db_conn.close()
            server._memory_db_conn = None
        
        # Remove the test database file if it exists
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        # Also clean up any .wal files that DuckDB might create
        wal_path = self.db_path + '.wal'
        if os.path.exists(wal_path):
            os.unlink(wal_path)
    
    def test_create_snapshot(self):
        """Test creating a new snapshot"""
        snapshot_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 5,
            "unassigned_count": 2,
            "old_prs_count": 1,
            "prs": [
                {
                    "number": 123,
                    "title": "Test PR",
                    "url": "https://github.com/test/pr/123",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 30,
                    "reviewers": "user1 [APPROVED], user2 [NO ACTION]",
                    "state": "open",
                    "comments": [
                        {"reviewer": "user1", "comment_count": 5},
                        {"reviewer": "user2", "comment_count": 2}
                    ]
                }
            ]
        }
        
        response = self.client.post(
            '/api/snapshots',
            data=json.dumps(snapshot_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIn('snapshot_id', data)
        self.assertEqual(data['snapshot_id'], 1)
    
    def test_get_snapshots(self):
        """Test retrieving snapshots"""
        # Create a snapshot first
        self._create_test_snapshot()
        
        response = self.client.get('/api/snapshots?days=30')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['repo_owner'], 'testowner')
    
    def test_get_snapshot_prs(self):
        """Test retrieving PRs for a specific snapshot"""
        snapshot_id = self._create_test_snapshot()
        
        response = self.client.get(f'/api/snapshots/{snapshot_id}/prs')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['pr_number'], 123)
    
    def test_get_stats(self):
        """Test retrieving statistics"""
        self._create_test_snapshot()
        
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('latest', data)
        self.assertIn('trend', data)
        self.assertIn('reviewers', data)
        
        # Check latest snapshot
        self.assertIsNotNone(data['latest'])
        self.assertEqual(data['latest']['total_prs'], 5)
        
        # Check reviewer stats
        self.assertEqual(len(data['reviewers']), 2)
        self.assertEqual(data['reviewers'][0]['reviewer'], 'user1')
        self.assertEqual(data['reviewers'][0]['count'], 1)
        self.assertEqual(data['reviewers'][0]['comments'], 5)
    
    def test_get_stats_empty_database(self):
        """Test stats endpoint with no data"""
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIsNone(data['latest'])
        self.assertEqual(len(data['trend']), 0)
        self.assertEqual(len(data['reviewers']), 0)
    
    def test_reviewer_comment_aggregation(self):
        """Test that reviewer comments are properly aggregated"""
        # Create snapshot with multiple PRs for same reviewer
        snapshot_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 2,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 1,
                    "title": "PR 1",
                    "url": "https://github.com/test/pr/1",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 10,
                    "reviewers": "user1 [APPROVED]",
                    "state": "open",
                    "comments": [{"reviewer": "user1", "comment_count": 3}]
                },
                {
                    "number": 2,
                    "title": "PR 2",
                    "url": "https://github.com/test/pr/2",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 5,
                    "reviewers": "user1 [NO ACTION]",
                    "state": "open",
                    "comments": [{"reviewer": "user1", "comment_count": 7}]
                }
            ]
        }
        
        self.client.post(
            '/api/snapshots',
            data=json.dumps(snapshot_data),
            content_type='application/json'
        )
        
        response = self.client.get('/api/stats')
        data = json.loads(response.data)
        
        # user1 should have 2 PRs and 10 total comments
        self.assertEqual(len(data['reviewers']), 1)
        self.assertEqual(data['reviewers'][0]['reviewer'], 'user1')
        self.assertEqual(data['reviewers'][0]['count'], 2)
        self.assertEqual(data['reviewers'][0]['comments'], 10)
    
    def test_delete_snapshot(self):
        """Test deleting a snapshot"""
        # Create a snapshot first
        snapshot_data = {
            "repo_owner": "test-owner",
            "repo_name": "test-repo",
            "total_prs": 5,
            "unassigned_count": 1,
            "old_prs_count": 2,
            "prs": [
                {
                    "number": 123,
                    "title": "Test PR",
                    "url": "https://github.com/test/pr/123",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 10,
                    "reviewers": "user1 [APPROVED]",
                    "state": "open",
                    "comments": [
                        {"reviewer": "user1", "comment_count": 5}
                    ]
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot_data),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        snapshot_id = json.loads(response.data)['snapshot_id']
        
        # Delete the snapshot
        response = self.client.delete(f'/api/snapshots/{snapshot_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Verify snapshot is deleted
        response = self.client.get('/api/snapshots')
        snapshots = json.loads(response.data)
        self.assertEqual(len(snapshots), 0)
    
    def test_delete_nonexistent_snapshot(self):
        """Test deleting a snapshot that doesn't exist"""
        response = self.client.delete('/api/snapshots/99999')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_get_snapshot_reviewers(self):
        """Test getting reviewer stats for a specific snapshot"""
        # Create a snapshot with multiple reviewers
        snapshot_data = {
            "repo_owner": "test-owner",
            "repo_name": "test-repo",
            "total_prs": 3,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 1,
                    "title": "PR 1",
                    "url": "https://github.com/test/pr/1",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 10,
                    "reviewers": "alice [APPROVED], bob [NO ACTION]",
                    "state": "open",
                    "comments": [
                        {"reviewer": "alice", "comment_count": 5},
                        {"reviewer": "bob", "comment_count": 2}
                    ]
                },
                {
                    "number": 2,
                    "title": "PR 2",
                    "url": "https://github.com/test/pr/2",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 5,
                    "reviewers": "alice [NO ACTION]",
                    "state": "open",
                    "comments": [
                        {"reviewer": "alice", "comment_count": 3}
                    ]
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot_data),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        snapshot_id = json.loads(response.data)['snapshot_id']
        
        # Get reviewer stats for this snapshot
        response = self.client.get(f'/api/snapshots/{snapshot_id}/reviewers')
        self.assertEqual(response.status_code, 200)
        reviewers = json.loads(response.data)
        
        # Should have 2 reviewers
        self.assertEqual(len(reviewers), 2)
        
        # Alice should have 2 PRs and 8 comments
        alice = next(r for r in reviewers if r['reviewer'] == 'alice')
        self.assertEqual(alice['count'], 2)
        self.assertEqual(alice['comments'], 8)
        
        # Bob should have 1 PR and 2 comments
        bob = next(r for r in reviewers if r['reviewer'] == 'bob')
        self.assertEqual(bob['count'], 1)
        self.assertEqual(bob['comments'], 2)
    
    def test_get_reviewers_nonexistent_snapshot(self):
        """Test getting reviewer stats for a snapshot that doesn't exist"""
        response = self.client.get('/api/snapshots/99999/reviewers')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def _create_test_snapshot(self):
        """Helper method to create a test snapshot"""
        snapshot_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 5,
            "unassigned_count": 2,
            "old_prs_count": 1,
            "prs": [
                {
                    "number": 123,
                    "title": "Test PR",
                    "url": "https://github.com/test/pr/123",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 30,
                    "reviewers": "user1 [APPROVED], user2 [NO ACTION]",
                    "state": "open",
                    "comments": [
                        {"reviewer": "user1", "comment_count": 5},
                        {"reviewer": "user2", "comment_count": 2}
                    ]
                }
            ]
        }
        
        response = self.client.post(
            '/api/snapshots',
            data=json.dumps(snapshot_data),
            content_type='application/json'
        )
        
        return json.loads(response.data)['snapshot_id']


if __name__ == '__main__':
    unittest.main()
