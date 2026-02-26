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
    
    def test_compare_snapshots_new_prs(self):
        """Test comparing snapshots to identify new PRs"""
        # Create first snapshot with 2 PRs
        snapshot1_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 2,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 100,
                    "title": "Existing PR 1",
                    "url": "https://github.com/test/pr/100",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 10,
                    "reviewers": "user1 [APPROVED]",
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 101,
                    "title": "Existing PR 2",
                    "url": "https://github.com/test/pr/101",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 5,
                    "reviewers": None,
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot1_data),
                                   content_type='application/json')
        snapshot1_id = json.loads(response.data)['snapshot_id']
        
        # Create second snapshot with 3 PRs (1 new)
        snapshot2_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 3,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 100,
                    "title": "Existing PR 1",
                    "url": "https://github.com/test/pr/100",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 11,
                    "reviewers": "user1 [APPROVED]",
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 101,
                    "title": "Existing PR 2",
                    "url": "https://github.com/test/pr/101",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 6,
                    "reviewers": None,
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 102,
                    "title": "New PR",
                    "url": "https://github.com/test/pr/102",
                    "created_at": "2024-01-03T00:00:00Z",
                    "updated_at": "2024-01-03T00:00:00Z",
                    "age_days": 1,
                    "reviewers": "user2 [APPROVED], user3 [APPROVED]",
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot2_data),
                                   content_type='application/json')
        snapshot2_id = json.loads(response.data)['snapshot_id']
        
        # Compare snapshots
        response = self.client.get(f'/api/snapshots/compare?snapshot1={snapshot1_id}&snapshot2={snapshot2_id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Verify structure
        self.assertIn('new_prs', data)
        self.assertIn('closed_prs', data)
        self.assertIn('status_changed', data)
        self.assertIn('unchanged', data)
        self.assertIn('summary', data)
        
        # Verify new PRs
        self.assertEqual(len(data['new_prs']), 1)
        self.assertEqual(data['new_prs'][0]['pr_number'], 102)
        self.assertEqual(data['new_prs'][0]['title'], 'New PR')
        self.assertEqual(data['new_prs'][0]['color'], 'green')  # 2 approvals
        self.assertEqual(data['new_prs'][0]['approval_count'], 2)
        
        # Verify summary
        self.assertEqual(data['summary']['new_count'], 1)
        self.assertEqual(data['summary']['closed_count'], 0)
    
    def test_compare_snapshots_closed_prs(self):
        """Test comparing snapshots to identify closed PRs"""
        # Create first snapshot with 3 PRs
        snapshot1_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 3,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 100,
                    "title": "PR to be closed",
                    "url": "https://github.com/test/pr/100",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 10,
                    "reviewers": "user1 [APPROVED]",
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 101,
                    "title": "Remaining PR",
                    "url": "https://github.com/test/pr/101",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 5,
                    "reviewers": None,
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot1_data),
                                   content_type='application/json')
        snapshot1_id = json.loads(response.data)['snapshot_id']
        
        # Create second snapshot with only 1 PR (PR 100 was closed)
        snapshot2_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 1,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 101,
                    "title": "Remaining PR",
                    "url": "https://github.com/test/pr/101",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 6,
                    "reviewers": None,
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot2_data),
                                   content_type='application/json')
        snapshot2_id = json.loads(response.data)['snapshot_id']
        
        # Compare snapshots
        response = self.client.get(f'/api/snapshots/compare?snapshot1={snapshot1_id}&snapshot2={snapshot2_id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Verify closed PRs
        self.assertEqual(len(data['closed_prs']), 1)
        self.assertEqual(data['closed_prs'][0]['pr_number'], 100)
        self.assertEqual(data['closed_prs'][0]['title'], 'PR to be closed')
        self.assertEqual(data['closed_prs'][0]['color'], 'yellow')  # 1 approval
        
        # Verify summary
        self.assertEqual(data['summary']['new_count'], 0)
        self.assertEqual(data['summary']['closed_count'], 1)
    
    def test_compare_snapshots_status_changed(self):
        """Test comparing snapshots to identify PRs with changed approval status"""
        # Create first snapshot
        snapshot1_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 2,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 100,
                    "title": "PR gaining approval",
                    "url": "https://github.com/test/pr/100",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 10,
                    "reviewers": None,  # Red - no approvals
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 101,
                    "title": "PR getting second approval",
                    "url": "https://github.com/test/pr/101",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 5,
                    "reviewers": "user1 [APPROVED]",  # Yellow - 1 approval
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot1_data),
                                   content_type='application/json')
        snapshot1_id = json.loads(response.data)['snapshot_id']
        
        # Create second snapshot with changed approval status
        snapshot2_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 2,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 100,
                    "title": "PR gaining approval",
                    "url": "https://github.com/test/pr/100",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-03T00:00:00Z",
                    "age_days": 11,
                    "reviewers": "user1 [APPROVED]",  # Yellow - 1 approval now
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 101,
                    "title": "PR getting second approval",
                    "url": "https://github.com/test/pr/101",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-03T00:00:00Z",
                    "age_days": 6,
                    "reviewers": "user1 [APPROVED], user2 [APPROVED]",  # Green - 2 approvals now
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot2_data),
                                   content_type='application/json')
        snapshot2_id = json.loads(response.data)['snapshot_id']
        
        # Compare snapshots
        response = self.client.get(f'/api/snapshots/compare?snapshot1={snapshot1_id}&snapshot2={snapshot2_id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Verify status changed PRs
        self.assertEqual(len(data['status_changed']), 2)
        
        # Check PR 100: red -> yellow
        pr100 = next(pr for pr in data['status_changed'] if pr['pr_number'] == 100)
        self.assertEqual(pr100['color_before'], 'red')
        self.assertEqual(pr100['color_after'], 'yellow')
        self.assertEqual(pr100['approval_count_before'], 0)
        self.assertEqual(pr100['approval_count_after'], 1)
        
        # Check PR 101: yellow -> green
        pr101 = next(pr for pr in data['status_changed'] if pr['pr_number'] == 101)
        self.assertEqual(pr101['color_before'], 'yellow')
        self.assertEqual(pr101['color_after'], 'green')
        self.assertEqual(pr101['approval_count_before'], 1)
        self.assertEqual(pr101['approval_count_after'], 2)
        
        # Verify summary
        self.assertEqual(data['summary']['status_changed_count'], 2)
    
    def test_compare_snapshots_unchanged(self):
        """Test that unchanged PRs are correctly identified"""
        # Create two snapshots with same PR status
        snapshot1_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 1,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 100,
                    "title": "Unchanged PR",
                    "url": "https://github.com/test/pr/100",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 10,
                    "reviewers": "user1 [APPROVED], user2 [APPROVED]",
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot1_data),
                                   content_type='application/json')
        snapshot1_id = json.loads(response.data)['snapshot_id']
        
        snapshot2_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 1,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": [
                {
                    "number": 100,
                    "title": "Unchanged PR",
                    "url": "https://github.com/test/pr/100",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 11,
                    "reviewers": "user1 [APPROVED], user2 [APPROVED]",  # Still green
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot2_data),
                                   content_type='application/json')
        snapshot2_id = json.loads(response.data)['snapshot_id']
        
        # Compare snapshots
        response = self.client.get(f'/api/snapshots/compare?snapshot1={snapshot1_id}&snapshot2={snapshot2_id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Verify unchanged PRs
        self.assertEqual(len(data['unchanged']), 1)
        self.assertEqual(data['unchanged'][0]['pr_number'], 100)
        self.assertEqual(data['unchanged'][0]['color'], 'green')
        
        # Verify summary
        self.assertEqual(data['summary']['unchanged_count'], 1)
        self.assertEqual(data['summary']['new_count'], 0)
        self.assertEqual(data['summary']['closed_count'], 0)
        self.assertEqual(data['summary']['status_changed_count'], 0)
    
    def test_compare_snapshots_missing_parameters(self):
        """Test error handling when parameters are missing"""
        # Missing both parameters
        response = self.client.get('/api/snapshots/compare')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        
        # Missing snapshot2
        response = self.client.get('/api/snapshots/compare?snapshot1=1')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_compare_snapshots_metadata(self):
        """Test that comparison includes snapshot metadata"""
        # Create two snapshots
        snapshot1_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 1,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": []
        }
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot1_data),
                                   content_type='application/json')
        snapshot1_id = json.loads(response.data)['snapshot_id']
        
        response = self.client.post('/api/snapshots',
                                   data=json.dumps(snapshot1_data),
                                   content_type='application/json')
        snapshot2_id = json.loads(response.data)['snapshot_id']
        
        # Compare snapshots
        response = self.client.get(f'/api/snapshots/compare?snapshot1={snapshot1_id}&snapshot2={snapshot2_id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Verify metadata
        self.assertIn('snapshot1', data)
        self.assertIn('snapshot2', data)
        self.assertEqual(data['snapshot1']['id'], snapshot1_id)
        self.assertEqual(data['snapshot2']['id'], snapshot2_id)
        self.assertIn('date', data['snapshot1'])
        self.assertIn('repo', data['snapshot1'])
        self.assertEqual(data['snapshot1']['repo'], 'testowner/testrepo')
    
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


class TestAPIResponseStructure(unittest.TestCase):
    """
    Unit tests for API response structure
    **Validates: Requirements 5.1, 5.2, 5.4**
    
    Tests that the API response includes all required fields,
    maintains backward compatibility, and handles edge cases correctly.
    """
    
    def setUp(self):
        """Set up test database and client"""
        # Reset the global in-memory connection for test isolation
        import server
        server._memory_db_conn = None
        
        # Create a unique test database file
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.duckdb')
        os.close(self.db_fd)
        os.environ['DB_PATH'] = ':memory:'
        
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Initialize database
        with self.app.app_context():
            init_db()
    
    def tearDown(self):
        """Clean up test database"""
        import server
        if server._memory_db_conn:
            server._memory_db_conn.close()
            server._memory_db_conn = None
        
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        wal_path = self.db_path + '.wal'
        if os.path.exists(wal_path):
            os.unlink(wal_path)
    
    def test_response_includes_all_required_fields(self):
        """Test that API response includes all required fields for trend data"""
        # Create a snapshot with PRs
        snapshot_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 3,
            "unassigned_count": 0,
            "old_prs_count": 1,
            "prs": [
                {
                    "number": 1,
                    "title": "PR 1",
                    "url": "https://github.com/test/pr/1",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 35,
                    "reviewers": "user1 [APPROVED], user2 [APPROVED]",
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 2,
                    "title": "PR 2",
                    "url": "https://github.com/test/pr/2",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 10,
                    "reviewers": "user3 [NO ACTION]",
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 3,
                    "title": "PR 3",
                    "url": "https://github.com/test/pr/3",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 5,
                    "reviewers": None,
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        self.client.post(
            '/api/snapshots',
            data=json.dumps(snapshot_data),
            content_type='application/json'
        )
        
        # Get stats
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Verify trend array exists and has data
        self.assertIn('trend', data)
        self.assertGreater(len(data['trend']), 0)
        
        # Check that each trend entry has all required fields
        trend_entry = data['trend'][0]
        required_fields = [
            'snapshot_date',
            'total_prs',
            'under_review_count',
            'two_approvals_count',
            'old_prs_count'
        ]
        
        for field in required_fields:
            self.assertIn(field, trend_entry, f"Missing required field: {field}")
        
        # Verify the values are correct
        self.assertEqual(trend_entry['total_prs'], 3)
        self.assertEqual(trend_entry['under_review_count'], 2)  # PR 1 and PR 2 have reviewers
        self.assertEqual(trend_entry['two_approvals_count'], 1)  # Only PR 1 has 2 approvals
        self.assertEqual(trend_entry['old_prs_count'], 1)  # Only PR 1 is > 30 days old
    
    def test_backward_compatibility_existing_fields_present(self):
        """Test that existing fields are still present for backward compatibility"""
        # Create a snapshot
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
                    "comments": []
                }
            ]
        }
        
        self.client.post(
            '/api/snapshots',
            data=json.dumps(snapshot_data),
            content_type='application/json'
        )
        
        # Get stats
        response = self.client.get('/api/stats')
        data = json.loads(response.data)
        
        # Verify existing fields are still present
        self.assertIn('latest', data)
        self.assertIn('trend', data)
        self.assertIn('reviewers', data)
        
        # Verify trend entries still have total_prs and old_prs_count
        trend_entry = data['trend'][0]
        self.assertIn('total_prs', trend_entry)
        self.assertIn('old_prs_count', trend_entry)
    
    def test_empty_database_returns_empty_trend_array(self):
        """Test that empty database returns empty trend array"""
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Verify response structure
        self.assertIn('latest', data)
        self.assertIn('trend', data)
        self.assertIn('reviewers', data)
        
        # Verify empty arrays
        self.assertIsNone(data['latest'])
        self.assertEqual(len(data['trend']), 0)
        self.assertEqual(len(data['reviewers']), 0)
    
    def test_snapshots_with_no_prs_default_to_zero(self):
        """Test that snapshots with no PRs have all fields default to 0"""
        # Create a snapshot with no PRs
        snapshot_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "total_prs": 0,
            "unassigned_count": 0,
            "old_prs_count": 0,
            "prs": []
        }
        
        self.client.post(
            '/api/snapshots',
            data=json.dumps(snapshot_data),
            content_type='application/json'
        )
        
        # Get stats
        response = self.client.get('/api/stats')
        data = json.loads(response.data)
        
        # Verify trend entry has all fields set to 0
        self.assertGreater(len(data['trend']), 0)
        trend_entry = data['trend'][0]
        
        self.assertEqual(trend_entry['total_prs'], 0)
        self.assertEqual(trend_entry['under_review_count'], 0)
        self.assertEqual(trend_entry['two_approvals_count'], 0)
        self.assertEqual(trend_entry['old_prs_count'], 0)
    
    def test_error_handling_database_connection_failure(self):
        """Test error handling when database connection fails"""
        # This test verifies that the API returns proper error responses
        # We can't easily simulate a database failure in the current setup,
        # but we can verify the error response structure for invalid requests
        
        # Test with invalid threshold parameter
        response = self.client.get('/api/stats?threshold=-5')
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('positive integer', data['error'])
    
    def test_response_with_custom_threshold(self):
        """Test that API response correctly uses custom threshold parameter"""
        # Create snapshots with PRs of various ages
        snapshot_data = {
            "repo_owner": "testowner",
            "repo_name": "testrepo",
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
                    "age_days": 50,
                    "reviewers": "user1 [APPROVED]",
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 2,
                    "title": "PR 2",
                    "url": "https://github.com/test/pr/2",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 35,
                    "reviewers": "user2 [APPROVED]",
                    "state": "open",
                    "comments": []
                },
                {
                    "number": 3,
                    "title": "PR 3",
                    "url": "https://github.com/test/pr/3",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "age_days": 20,
                    "reviewers": "user3 [APPROVED]",
                    "state": "open",
                    "comments": []
                }
            ]
        }
        
        self.client.post(
            '/api/snapshots',
            data=json.dumps(snapshot_data),
            content_type='application/json'
        )
        
        # Test with threshold=30 (default)
        response = self.client.get('/api/stats?threshold=30')
        data = json.loads(response.data)
        trend_entry = data['trend'][0]
        self.assertEqual(trend_entry['old_prs_count'], 2)  # PRs with age > 30
        
        # Test with threshold=40
        response = self.client.get('/api/stats?threshold=40')
        data = json.loads(response.data)
        trend_entry = data['trend'][0]
        self.assertEqual(trend_entry['old_prs_count'], 1)  # Only PR with age > 40
        
        # Test with threshold=60
        response = self.client.get('/api/stats?threshold=60')
        data = json.loads(response.data)
        trend_entry = data['trend'][0]
        self.assertEqual(trend_entry['old_prs_count'], 0)  # No PRs with age > 60
