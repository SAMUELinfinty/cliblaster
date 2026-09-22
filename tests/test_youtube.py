import unittest
from unittest.mock import patch, MagicMock
import json
from urllib.error import HTTPError, URLError

from cliblaster.youtube import YouTubeClient, YouTubeAPIError
from cliblaster.track import Track

class TestYouTubeClient(unittest.TestCase):

    def setUp(self):
        self.client = YouTubeClient(api_key="TEST_API_KEY")

    def test_missing_api_key(self):
        client_no_key = YouTubeClient(api_key="")
        with self.assertRaises(YouTubeAPIError):
            client_no_key.search("test")

    def test_empty_search_query(self):
        with self.assertRaises(ValueError):
            self.client.search("   ")

    @patch('urllib.request.urlopen')
    def test_successful_search(self, mock_urlopen):
        # Create a mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "items": [
                {
                    "id": {"videoId": "dQw4w9WgXcQ"},
                    "snippet": {
                        "title": "Rick Astley - Never Gonna Give You Up",
                        "channelTitle": "Rick Astley"
                    }
                },
                {
                    "id": {"videoId": "123456"},
                    "snippet": {
                        "title": "Some other video",
                        "channelTitle": "Some Channel"
                    }
                }
            ]
        }).encode('utf-8')
        # configure context manager for urlopen
        mock_urlopen.return_value.__enter__.return_value = mock_response

        results = self.client.search("rick astley")
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], Track)
        self.assertEqual(results[0].title, "Rick Astley - Never Gonna Give You Up")
        self.assertEqual(results[0].artist, "Rick Astley")
        self.assertEqual(results[0].source, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch('urllib.request.urlopen')
    def test_empty_search_results(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"items": []}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        results = self.client.search("asdfasdfasdf")
        self.assertEqual(len(results), 0)

    @patch('urllib.request.urlopen')
    def test_api_quota_error(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://mock",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None
        )

        with self.assertRaises(YouTubeAPIError) as context:
            self.client.search("test")
        self.assertIn("403", str(context.exception))

    @patch('urllib.request.urlopen')
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("Network unreachable")

        with self.assertRaises(YouTubeAPIError) as context:
            self.client.search("test")
        self.assertIn("connect to YouTube", str(context.exception))

    @patch('urllib.request.urlopen')
    def test_malformed_json_response(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"NOT JSON"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(YouTubeAPIError) as context:
            self.client.search("test")
        self.assertIn("malformed JSON", str(context.exception))

if __name__ == "__main__":
    unittest.main()
