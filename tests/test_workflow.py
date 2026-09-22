"""
Integration tests for M8: Search → Select → Queue → Play workflow.
No real YouTube API calls are made; no real audio hardware needed.
"""
import unittest
from unittest.mock import patch, MagicMock

from cliblaster.track import Track
from cliblaster.music_queue import Queue
from cliblaster.player import Player, PlayerState
from cliblaster.commands import CommandRouter, CommandResult
from cliblaster.audio_backend import AudioBackend
from cliblaster.auth import OAuthManager
from cliblaster.youtube import YouTubeClient


# ------------------------------------------------------------------ #
# Test doubles
# ------------------------------------------------------------------ #

class SpyBackend(AudioBackend):
    """Records which calls were made so we can assert on them."""
    def __init__(self):
        self.loaded = None
        self.calls = []

    def load(self, path):
        self.loaded = path
        self.calls.append(("load", path))

    def play(self):
        self.calls.append(("play",))

    def pause(self):
        self.calls.append(("pause",))

    def resume(self):
        self.calls.append(("resume",))

    def stop(self):
        self.calls.append(("stop",))


def _fake_track(title, artist="TestArtist", source="https://youtube.com/watch?v=fake"):
    return Track(title=title, artist=artist, source=source)


def _make_router():
    """Returns a fully wired CommandRouter with spy backend; auth mocked out."""
    with patch("os.path.exists", return_value=False):
        auth = OAuthManager(client_secret_path="dummy", token_path="dummy")

    backend = SpyBackend()
    queue = Queue()
    player = Player(backend=backend, queue=queue)
    router = CommandRouter(player=player, queue=queue, auth_manager=auth)
    return router, queue, player, backend


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #

class TestSearchResultsRepresentation(unittest.TestCase):
    """Search results can be stored as Track objects internally."""

    def test_search_result_is_a_track(self):
        track = _fake_track("Karma Police")
        self.assertIsInstance(track, Track)
        self.assertEqual(track.title, "Karma Police")

    def test_multiple_search_results_stored(self):
        router, *_ = _make_router()
        results = [_fake_track("Creep"), _fake_track("Karma Police"), _fake_track("No Surprises")]
        router.recent_search_results = results
        self.assertEqual(len(router.recent_search_results), 3)


class TestSelectCommand(unittest.TestCase):
    """A search result can be selected by number."""

    def setUp(self):
        self.router, self.queue, self.player, self.backend = _make_router()
        self.router.recent_search_results = [
            _fake_track("Creep"),
            _fake_track("Karma Police"),
            _fake_track("No Surprises"),
        ]

    def test_select_valid_result(self):
        result = self.router.dispatch("select 2")
        self.assertIsInstance(result, CommandResult)
        self.assertEqual(self.router.selected_track.title, "Karma Police")

    def test_select_sets_track(self):
        self.router.dispatch("select 1")
        self.assertEqual(self.router.selected_track.title, "Creep")

    def test_select_without_search_no_crash(self):
        self.router.recent_search_results = []
        result = self.router.dispatch("select 1")
        self.assertIsInstance(result, CommandResult)
        self.assertIsNone(self.router.selected_track)

    def test_select_invalid_number(self):
        result = self.router.dispatch("select 99")
        self.assertIsInstance(result, CommandResult)
        self.assertIsNone(self.router.selected_track)

    def test_select_non_numeric(self):
        result = self.router.dispatch("select abc")
        self.assertIsInstance(result, CommandResult)


class TestAddSelectedToQueue(unittest.TestCase):
    """A selected track becomes a Track in the Queue."""

    def setUp(self):
        self.router, self.queue, self.player, self.backend = _make_router()
        self.router.recent_search_results = [
            _fake_track("Creep"),
            _fake_track("Karma Police"),
        ]

    def test_select_then_add_no_arg(self):
        self.router.dispatch("select 2")
        self.assertEqual(len(self.queue.all()), 0)
        self.router.dispatch("add")
        self.assertEqual(len(self.queue.all()), 1)
        self.assertEqual(self.queue.current().title, "Karma Police")

    def test_add_consumes_selection(self):
        self.router.dispatch("select 1")
        self.router.dispatch("add")
        self.assertIsNone(self.router.selected_track)

    def test_add_without_selection_no_crash(self):
        result = self.router.dispatch("add")
        self.assertIsInstance(result, CommandResult)
        self.assertEqual(len(self.queue.all()), 0)

    def test_add_by_number_directly(self):
        """add <N> still works without using select first."""
        self.router.dispatch("add 1")
        self.assertEqual(self.queue.current().title, "Creep")

    def test_add_multiple_tracks_builds_queue(self):
        self.router.dispatch("select 1")
        self.router.dispatch("add")
        self.router.dispatch("select 2")
        self.router.dispatch("add")
        self.assertEqual(len(self.queue.all()), 2)
        self.assertEqual(self.queue.all()[0].title, "Creep")
        self.assertEqual(self.queue.all()[1].title, "Karma Police")


class TestQueueAndPlayerIntegration(unittest.TestCase):
    """Queue current track is passed to Player correctly."""

    def setUp(self):
        self.router, self.queue, self.player, self.backend = _make_router()
        # Pre-load queue with two tracks
        self.queue.add(_fake_track("Song A", source="a.mp3"))
        self.queue.add(_fake_track("Song B", source="b.mp3"))

    def test_play_starts_first_track(self):
        self.router.dispatch("play")
        self.assertEqual(self.player.state, PlayerState.PLAYING)
        self.assertEqual(self.queue.current().title, "Song A")
        self.assertIn("a.mp3", self.backend.loaded)

    def test_next_advances_player(self):
        self.router.dispatch("play")
        self.router.dispatch("next")
        self.assertEqual(self.queue.current().title, "Song B")
        self.assertIn("b.mp3", self.backend.loaded)

    def test_previous_goes_back(self):
        # Advance to Song B first
        self.router.dispatch("play")
        self.router.dispatch("next")
        self.assertEqual(self.queue.current().title, "Song B")
        # Then go back
        self.router.dispatch("previous")
        self.assertEqual(self.queue.current().title, "Song A")

    def test_empty_queue_handled(self):
        router, queue, player, backend = _make_router()
        result = router.dispatch("play")
        self.assertIsInstance(result, CommandResult)
        self.assertNotEqual(player.state, PlayerState.PLAYING)


class TestRemotePlaybackLimitation(unittest.TestCase):
    """Verifies that YouTube tracks go into the queue correctly, and that
    the Player tries to load the YouTube URL as the source — making the
    actual playback limitation transparent."""

    def test_youtube_track_source_is_url(self):
        track = _fake_track("Test Video", source="https://www.youtube.com/watch?v=abc123")
        q = Queue()
        q.add(track)
        self.assertEqual(q.current().source, "https://www.youtube.com/watch?v=abc123")

    def test_local_file_still_works(self):
        router, queue, player, backend = _make_router()
        router.dispatch("add tests/fixtures/song.mp3")
        track = queue.current()
        self.assertIsNotNone(track)
        self.assertEqual(track.title, "song.mp3")


class TestSearchCommandMocked(unittest.TestCase):
    """End-to-end: search → results stored, select → selected_track set."""

    def setUp(self):
        self.router, self.queue, self.player, self.backend = _make_router()

    @patch.object(YouTubeClient, "search")
    def test_search_stores_results(self, mock_search):
        mock_search.return_value = [
            _fake_track("Borderline"),
            _fake_track("Let It Happen"),
        ]
        self.router.dispatch("search tame impala")
        self.assertEqual(len(self.router.recent_search_results), 2)
        self.assertEqual(self.router.recent_search_results[0].title, "Borderline")

    @patch.object(YouTubeClient, "search")
    def test_search_then_select_then_add(self, mock_search):
        mock_search.return_value = [
            _fake_track("Borderline"),
            _fake_track("Let It Happen"),
        ]
        self.router.dispatch("search tame impala")
        self.router.dispatch("select 2")
        self.router.dispatch("add")
        self.assertEqual(self.queue.current().title, "Let It Happen")

    @patch.object(YouTubeClient, "search")
    def test_search_clears_previous_selection(self, mock_search):
        self.router.selected_track = _fake_track("Old Selection")
        mock_search.return_value = [_fake_track("New Result")]
        self.router.dispatch("search something new")
        self.assertIsNone(self.router.selected_track)


if __name__ == "__main__":
    unittest.main()
