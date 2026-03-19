import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import sys
import io
from track_open_crs import human_age, get_days_old, format_reviewers, fetch_open_crs, main

class TestTrackOpenCRs(unittest.TestCase):

    def test_human_age_valid_date(self):
        # Test with a date 2 days and 3 hours ago
        past_date = "2024-01-01T10:00:00Z"
        with patch('track_open_crs.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 3, 13, 0, 0, tzinfo=timezone.utc)
            mock_datetime.fromisoformat = datetime.fromisoformat
            result = human_age(past_date)
            self.assertEqual(result, "2d 3h")

    def test_human_age_invalid_date(self):
        result = human_age("invalid-date")
        self.assertEqual(result, "Unknown")

    def test_human_age_none(self):
        result = human_age(None)
        self.assertEqual(result, "Unknown")

    def test_get_days_old_valid_date(self):
        past_date = "2024-01-01T10:00:00Z"
        with patch('track_open_crs.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 3, 13, 0, 0, tzinfo=timezone.utc)
            mock_datetime.fromisoformat = datetime.fromisoformat
            result = get_days_old(past_date)
            self.assertEqual(result, 2)

    def test_get_days_old_invalid_date(self):
        result = get_days_old("invalid-date")
        self.assertEqual(result, 0)

    def test_format_reviewers_list(self):
        reviewers = ["alice", "bob", "charlie"]
        result = format_reviewers(reviewers)
        self.assertEqual(result, "alice, bob, charlie")

    def test_format_reviewers_empty(self):
        result = format_reviewers([])
        self.assertEqual(result, "None")

    def test_format_reviewers_none(self):
        result = format_reviewers(None)
        self.assertEqual(result, "None")

    @patch('track_open_crs.search_internal_code')
    def test_fetch_open_crs_success(self, mock_search):
        mock_search.return_value = {
            'results': [
                {
                    'id': 'cr1',
                    'title': 'Test CR',
                    'author': 'alice',
                    'created_at': '2024-01-01T10:00:00Z',
                    'updated_at': '2024-01-02T10:00:00Z',
                    'reviewers': ['bob'],
                    'url': 'http://example.com/cr1',
                    'package': 'test-package'
                }
            ]
        }
        
        result = fetch_open_crs("test-package")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'cr1')
        self.assertEqual(result[0]['title'], 'Test CR')

    @patch('track_open_crs.search_internal_code')
    def test_fetch_open_crs_error(self, mock_search):
        mock_search.side_effect = Exception("API Error")
        
        with patch('sys.stderr', new_callable=io.StringIO):
            result = fetch_open_crs()
            self.assertEqual(result, [])

    @patch('track_open_crs.fetch_open_crs')
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_main_with_crs(self, mock_stderr, mock_stdout, mock_fetch):
        mock_fetch.return_value = [
            {
                'url': 'http://example.com/cr1',
                'title': 'Test CR',
                'created_at': '2024-01-01T10:00:00Z',
                'updated_at': '2024-01-02T10:00:00Z',
                'reviewers': ['bob'],
                'author': 'alice',
                'package': 'test-package'
            }
        ]
        
        with patch('track_open_crs.human_age', return_value="1d 0h"):
            with patch('track_open_crs.get_days_old', return_value=1):
                main()
        
        output = mock_stdout.getvalue()
        self.assertIn("CR Link,Title,CreatedDate", output)
        self.assertIn("http://example.com/cr1", output)
        
        stderr_output = mock_stderr.getvalue()
        self.assertIn("SUMMARY: 1 total CRs", stderr_output)

if __name__ == '__main__':
    unittest.main()