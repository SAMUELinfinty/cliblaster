"""
Unit tests for M7 library features.
The real YouTube API is never called; _get() is mocked.
"""
import json
import unittest
from unittest.mock import patch, MagicMock

from cliblaster.youtube import YouTubeClient, YouTubeAPIError
from cliblaster.track import Track
from cliblaster.playlist import Playlist

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_playlist_item(playlist_id="PL123", title="My Playlist",
                        description="desc", item_count=3):
    return {
        "id": playlist_id,
        "snippet": {
            "title": title,
            "description": description,
        },
        "contentDetails": {"itemCount": item_count},
    }

def _make_playlist_items_item(video_id="abc123", title="Cool Song",
                              channel="Cool Channel"):
    return {
        "snippet": {
            "title": title,
            "videoOwnerChannelTitle": channel,
            "resourceId": {"videoId": video_id},
        },
        "contentDetails": {"videoId": video_id},
    }

def _make_video_item(video_id="xyz789", title="Liked Song", channel="Artist"):
    return {
        "id": video_id,
        "snippet": {"title": title, "channelTitle": channel},
    }


# ---------------------------------------------------------------------------
# Auth mock
# ---------------------------------------------------------------------------

def _make_auth():
    auth = MagicMock()
    auth.is_authenticated.return_value = True
    auth.get_access_token.return_value = "fake_token"
    return auth


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetPlaylists(unittest.TestCase):
    def setUp(self):
        self.client = YouTubeClient(auth_manager=_make_auth())

    @patch.object(YouTubeClient, "_get")
    def test_single_page_playlists(self, mock_get):
        mock_get.return_value = {
            "items": [
                _make_playlist_item("PL1", "Coding", "code music", 10),
                _make_playlist_item("PL2", "Night Drive", "", 5),
            ]
        }
        playlists = self.client.get_playlists()
        self.assertEqual(len(playlists), 2)
        self.assertIsInstance(playlists[0], Playlist)
        self.assertEqual(playlists[0].id, "PL1")
        self.assertEqual(playlists[0].title, "Coding")
        self.assertEqual(playlists[0].item_count, 10)
        self.assertEqual(playlists[1].title, "Night Drive")

    @patch.object(YouTubeClient, "_paginate")
    def test_paginated_playlists(self, mock_paginate):
        mock_paginate.return_value = [
            _make_playlist_item("PL1", "Page1"),
            _make_playlist_item("PL2", "Page2"),
        ]
        playlists = self.client.get_playlists()
        self.assertEqual(len(playlists), 2)
        mock_paginate.assert_called_once()

    @patch.object(YouTubeClient, "_get")
    def test_empty_playlists(self, mock_get):
        mock_get.return_value = {"items": []}
        playlists = self.client.get_playlists()
        self.assertEqual(playlists, [])

    def test_requires_auth(self):
        client = YouTubeClient()  # no auth
        with self.assertRaises(YouTubeAPIError) as ctx:
            client.get_playlists()
        self.assertIn("login", str(ctx.exception))


class TestGetPlaylistItems(unittest.TestCase):
    def setUp(self):
        self.client = YouTubeClient(auth_manager=_make_auth())

    @patch.object(YouTubeClient, "_get")
    def test_parses_tracks(self, mock_get):
        mock_get.return_value = {
            "items": [
                _make_playlist_items_item("v1", "Track 1", "Artist A"),
                _make_playlist_items_item("v2", "Track 2", "Artist B"),
            ]
        }
        tracks = self.client.get_playlist_items("PL123")
        self.assertEqual(len(tracks), 2)
        self.assertIsInstance(tracks[0], Track)
        self.assertEqual(tracks[0].title, "Track 1")
        self.assertEqual(tracks[0].artist, "Artist A")
        self.assertEqual(tracks[0].source, "https://www.youtube.com/watch?v=v1")

    @patch.object(YouTubeClient, "_get")
    def test_skips_deleted_private_videos(self, mock_get):
        deleted = _make_playlist_items_item("d1", "Deleted video", "")
        private = _make_playlist_items_item("p1", "Private video", "")
        good = _make_playlist_items_item("g1", "Good Song", "Artist")
        mock_get.return_value = {"items": [deleted, private, good]}
        tracks = self.client.get_playlist_items("PL123")
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].title, "Good Song")

    @patch.object(YouTubeClient, "_get")
    def test_empty_playlist(self, mock_get):
        mock_get.return_value = {"items": []}
        tracks = self.client.get_playlist_items("PLEMPTY")
        self.assertEqual(tracks, [])

    @patch.object(YouTubeClient, "_get")
    def test_malformed_item_skipped(self, mock_get):
        # item with missing snippet fields
        mock_get.return_value = {"items": [{"snippet": {}}]}
        tracks = self.client.get_playlist_items("PL123")
        self.assertEqual(tracks, [])

    def test_requires_auth(self):
        client = YouTubeClient()
        with self.assertRaises(YouTubeAPIError):
            client.get_playlist_items("PL123")


class TestGetLikedVideos(unittest.TestCase):
    def setUp(self):
        self.client = YouTubeClient(auth_manager=_make_auth())

    @patch.object(YouTubeClient, "_get")
    def test_parses_liked_tracks(self, mock_get):
        mock_get.return_value = {
            "items": [
                _make_video_item("v1", "Liked 1", "Channel A"),
                _make_video_item("v2", "Liked 2", "Channel B"),
            ]
        }
        tracks = self.client.get_liked_videos()
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0].title, "Liked 1")
        self.assertEqual(tracks[0].artist, "Channel A")
        self.assertEqual(tracks[0].source, "https://www.youtube.com/watch?v=v1")

    @patch.object(YouTubeClient, "_get")
    def test_empty_liked(self, mock_get):
        mock_get.return_value = {"items": []}
        tracks = self.client.get_liked_videos()
        self.assertEqual(tracks, [])

    def test_requires_auth(self):
        client = YouTubeClient()
        with self.assertRaises(YouTubeAPIError):
            client.get_liked_videos()


class TestCaching(unittest.TestCase):
    def setUp(self):
        self.client = YouTubeClient(auth_manager=_make_auth())

    @patch("urllib.request.urlopen")
    def test_cache_is_hit_on_second_call(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"items": []}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        self.client._get("playlists", {"part": "snippet", "mine": "true"})
        self.client._get("playlists", {"part": "snippet", "mine": "true"})

        # urlopen should only have been called once — second call was cached
        self.assertEqual(mock_urlopen.call_count, 1)


class TestQueueIntegration(unittest.TestCase):
    """Verify that playlist tracks can be added to the Queue."""

    def test_playlist_track_added_to_queue(self):
        from cliblaster.music_queue import Queue
        queue = Queue()
        track = Track(title="Karma Police", artist="Radiohead",
                      source="https://www.youtube.com/watch?v=fake")
        queue.add(track)
        self.assertEqual(queue.current().title, "Karma Police")

    def test_invalid_playlist_selection_no_crash(self):
        from cliblaster.commands import CommandRouter, CommandResult
        from cliblaster.music_queue import Queue
        from cliblaster.player import Player
        from cliblaster.audio_backend import AudioBackend
        from cliblaster.auth import OAuthManager
        import unittest.mock as mock

        class MockBackend(AudioBackend):
            def load(self, p): pass
            def play(self): pass
            def pause(self): pass
            def resume(self): pass
            def stop(self): pass

        with mock.patch("os.path.exists", return_value=False):
            auth = OAuthManager(client_secret_path="dummy", token_path="dummy")

        q = Queue()
        player = Player(backend=MockBackend(), queue=q)
        router = CommandRouter(player=player, queue=q, auth_manager=auth)

        # no playlists loaded → should not crash
        result = router.dispatch("playlist 1")
        self.assertIsInstance(result, CommandResult)
        self.assertFalse(result.should_quit)


if __name__ == "__main__":
    unittest.main()
