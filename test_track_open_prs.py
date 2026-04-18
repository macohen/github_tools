import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import track_open_prs


class TestTrackOpenPRs(unittest.TestCase):
    
    def test_get_days_old(self):
        """Test calculating days old from a date string"""
        # Mock NOW to a fixed date
        with patch('track_open_prs.NOW', datetime(2024, 2, 1, tzinfo=timezone.utc)):
            created_at = "2024-01-01T00:00:00Z"
            days = track_open_prs.get_days_old(created_at)
            self.assertEqual(days, 31)
    
    def test_human_age(self):
        """Test human-readable age formatting"""
        with patch('track_open_prs.NOW', datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)):
            created_at = "2024-01-30T08:00:00Z"
            age = track_open_prs.human_age(created_at)
            self.assertEqual(age, "2d 4h")
    
    @patch('track_open_prs.github_session')
    def test_get_reviewers(self, mock_session):
        """Test fetching reviewers for a PR"""
        # Mock requested reviewers response
        mock_requested = MagicMock()
        mock_requested.status_code = 200
        mock_requested.json.return_value = {
            "users": [{"login": "user1"}, {"login": "user2"}]
        }
        
        # Mock reviews response
        mock_reviews = MagicMock()
        mock_reviews.status_code = 200
        mock_reviews.json.return_value = [
            {"user": {"login": "user3"}, "state": "APPROVED"},
            {"user": {"login": "user1"}, "state": "CHANGES_REQUESTED"}
        ]
        
        mock_session.get.side_effect = [mock_requested, mock_reviews]
        
        # Clear cache before test
        track_open_prs.get_reviewers.cache_clear()
        
        reviewers = track_open_prs.get_reviewers(123)
        
        # Should have 3 unique reviewers
        self.assertEqual(len(reviewers), 3)
        self.assertIn(("user1", "CHANGES_REQUESTED"), reviewers)
        self.assertIn(("user2", "NO ACTION"), reviewers)
        self.assertIn(("user3", "APPROVED"), reviewers)
    
    @patch('track_open_prs.github_session')
    def test_get_comment_counts(self, mock_session):
        """Test fetching comment counts for a PR"""
        # Mock review comments response
        mock_review_comments = MagicMock()
        mock_review_comments.status_code = 200
        mock_review_comments.json.return_value = [
            {"user": {"login": "user1"}},
            {"user": {"login": "user1"}},
            {"user": {"login": "user2"}}
        ]
        
        # Mock issue comments response
        mock_issue_comments = MagicMock()
        mock_issue_comments.status_code = 200
        mock_issue_comments.json.return_value = [
            {"user": {"login": "user1"}},
            {"user": {"login": "user3"}}
        ]
        
        mock_session.get.side_effect = [mock_review_comments, mock_issue_comments]
        
        # Clear cache before test
        track_open_prs.get_comment_counts.cache_clear()
        
        comment_counts = track_open_prs.get_comment_counts(123)
        
        # user1 should have 3 comments, user2 and user3 should have 1 each
        self.assertEqual(comment_counts["user1"], 3)
        self.assertEqual(comment_counts["user2"], 1)
        self.assertEqual(comment_counts["user3"], 1)
    
    @patch('track_open_prs.github_session')
    def test_fetch_prs_open(self, mock_session):
        """Test fetching open PRs"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "number": 1,
                "title": "Test PR 1",
                "html_url": "https://github.com/test/pr/1",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "draft": False
            },
            {
                "number": 2,
                "title": "Test PR 2",
                "html_url": "https://github.com/test/pr/2",
                "created_at": "2024-01-05T00:00:00Z",
                "updated_at": "2024-01-06T00:00:00Z",
                "draft": False
            }
        ]
        
        # Second call returns empty to stop pagination
        mock_empty = MagicMock()
        mock_empty.status_code = 200
        mock_empty.json.return_value = []
        
        mock_session.get.side_effect = [mock_response, mock_empty]
        
        prs = track_open_prs.fetch_prs("open")
        
        self.assertEqual(len(prs), 2)
        self.assertEqual(prs[0]["number"], 1)
        self.assertEqual(prs[1]["number"], 2)
    
    @patch('track_open_prs.requests.post')
    def test_store_snapshot(self, mock_post):
        """Test storing snapshot via API"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"snapshot_id": 1}
        mock_post.return_value = mock_response
        
        processed_prs = [
            {
                "number": 123,
                "title": "Test PR",
                "html_url": "https://github.com/test/pr/123",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "age_days": 30,
                "reviewers": {("user1", "APPROVED")},
                "comment_counts": {"user1": 5}
            }
        ]
        
        track_open_prs.store_snapshot(processed_prs, 1, 0, 0)
        
        # Verify API was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check the data sent to API
        data = call_args[1]['json']
        self.assertEqual(data['total_prs'], 1)
        self.assertEqual(data['unassigned_count'], 0)
        self.assertEqual(data['old_prs_count'], 0)
        self.assertEqual(len(data['prs']), 1)
        self.assertEqual(data['prs'][0]['number'], 123)
        self.assertEqual(len(data['prs'][0]['comments']), 1)
    
    @patch('track_open_prs.requests.post')
    def test_publish_to_quip(self, mock_post):
        """Test publishing to Quip"""
        with patch.dict('os.environ', {'QUIP_TOKEN': 'test-token'}):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "thread": {"link": "https://quip.com/doc/123"}
            }
            mock_post.return_value = mock_response
            
            url = track_open_prs.publish_to_quip("# Test Content", "Test Title")
            
            self.assertEqual(url, "https://quip.com/doc/123")
            mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
