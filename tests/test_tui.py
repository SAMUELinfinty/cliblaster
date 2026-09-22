"""
Unit tests for Milestone 9: Terminal User Interface (TUI).
Tests presentation layer rendering and user action routing without real hardware or network calls.
"""

import unittest
from unittest.mock import MagicMock, patch

from cliblaster.track import Track
from cliblaster.music_queue import Queue
from cliblaster.player import Player, PlayerState
from cliblaster.audio_backend import AudioBackend
from cliblaster.auth import OAuthManager
from cliblaster.commands import CommandRouter
from cliblaster.tui import (
    CLIBLASTERApp,
    HeaderWidget,
    SearchResultsWidget,
    NowPlayingWidget,
    QueueWidget,
    MainScreen,
)


class MockAudioBackend(AudioBackend):
    def load(self, source: str) -> None:
        pass
    def play(self) -> None:
        pass
    def pause(self) -> None:
        pass
    def resume(self) -> None:
        pass
    def stop(self) -> None:
        pass


class TestTUIComponents(unittest.TestCase):

    def setUp(self):
        self.backend = MockAudioBackend()
        self.queue = Queue()
        self.player = Player(backend=self.backend, queue=self.queue)
        self.auth_manager = MagicMock(spec=OAuthManager)
        self.auth_manager.is_authenticated.return_value = True
        self.router = CommandRouter(player=self.player, queue=self.queue, auth_manager=self.auth_manager)
        self.app = CLIBLASTERApp(router=self.router, player=self.player, queue=self.queue, auth_manager=self.auth_manager)

    def test_header_widget_authenticated(self):
        """Header displays connected status when authenticated."""
        header = HeaderWidget(auth_manager=self.auth_manager)
        rendered = header.render()
        self.assertIn("CLIBLASTER 🎵", rendered)
        self.assertIn("✓ Logged in", rendered)

    def test_header_widget_not_authenticated(self):
        """Header displays not connected status when unauthenticated."""
        self.auth_manager.is_authenticated.return_value = False
        header = HeaderWidget(auth_manager=self.auth_manager)
        rendered = header.render()
        self.assertIn("✗ Not logged in", rendered)

    def test_now_playing_widget_empty(self):
        """Now playing shows empty message when no track is queued."""
        now_playing = NowPlayingWidget(player=self.player, queue=self.queue)
        rendered = now_playing.render()
        self.assertIn("NOW PLAYING", rendered)
        self.assertIn("Nothing is currently playing", rendered)

    def test_now_playing_widget_with_track(self):
        """Now playing reflects current track and player state."""
        track = Track(title="Creep", artist="Radiohead", source="https://youtube.com/watch?v=123")
        self.queue.add(track)
        self.player.state = PlayerState.PLAYING

        now_playing = NowPlayingWidget(player=self.player, queue=self.queue)
        rendered = now_playing.render()
        self.assertIn("▶ Creep", rendered)
        self.assertIn("Radiohead", rendered)

    def test_queue_widget_display(self):
        """Queue widget displays all tracks in queue with current track indicator."""
        t1 = Track(title="Song 1", artist="Artist 1", source="https://youtube.com/watch?v=1")
        t2 = Track(title="Song 2", artist="Artist 2", source="https://youtube.com/watch?v=2")
        self.queue.add(t1)
        self.queue.add(t2)

        queue_widget = QueueWidget(queue=self.queue)
        rendered = queue_widget.render()
        self.assertIn("QUEUE", rendered)
        self.assertIn("▶ 1. Song 1", rendered)
        self.assertIn("2. Song 2", rendered)

    def test_search_results_widget(self):
        """Search results widget renders search results and navigation selection."""
        search_widget = SearchResultsWidget()
        t1 = Track(title="SearchResult 1", artist="Artist A", source="https://youtube.com/watch?v=a")
        t2 = Track(title="SearchResult 2", artist="Artist B", source="https://youtube.com/watch?v=b")

        search_widget.set_results([t1, t2])
        rendered = search_widget.render()
        self.assertIn("SearchResult 1", rendered)
        self.assertIn("SearchResult 2", rendered)
        self.assertEqual(search_widget.get_selected(), t1)

        search_widget.move_selection(1)
        self.assertEqual(search_widget.get_selected(), t2)

    def test_add_selected_result_to_queue(self):
        """Adding a search result updates the queue and player state."""
        t1 = Track(title="Karma Police", artist="Radiohead", source="https://youtube.com/watch?v=kp")
        self.router.recent_search_results = [t1]
        main_screen = MainScreen()
        main_screen._app = self.app

        with patch.object(main_screen, "query_one") as mock_query:
            mock_results_widget = SearchResultsWidget()
            mock_results_widget.set_results([t1])
            mock_now_playing = MagicMock()
            mock_queue_widget = MagicMock()
            mock_status = MagicMock()
            mock_header = MagicMock()

            def query_side_effect(selector, *args):
                if selector == "#search_results":
                    return mock_results_widget
                if selector == "#now_playing":
                    return mock_now_playing
                if selector == "#queue_widget":
                    return mock_queue_widget
                if selector == "#status_banner":
                    return mock_status
                if selector == "#main_header":
                    return mock_header
                return MagicMock()

            mock_query.side_effect = query_side_effect

            main_screen.action_add_selected()
            self.assertEqual(len(self.queue.all()), 1)
            self.assertEqual(self.queue.current().title, "Karma Police")

    def test_space_key_toggles_pause_resume(self):
        """Space action triggers play/pause toggle."""
        t1 = Track(title="No Surprises", artist="Radiohead", source="https://youtube.com/watch?v=ns")
        self.queue.add(t1)

        self.app.action_toggle_pause()
        self.assertEqual(self.player.state, PlayerState.PLAYING)

        self.app.action_toggle_pause()
        self.assertEqual(self.player.state, PlayerState.PAUSED)

        self.app.action_toggle_pause()
        self.assertEqual(self.player.state, PlayerState.PLAYING)

    def test_n_key_triggers_next(self):
        """N action triggers next track."""
        t1 = Track(title="Track 1", artist="Artist 1", source="https://youtube.com/watch?v=t1")
        t2 = Track(title="Track 2", artist="Artist 2", source="https://youtube.com/watch?v=t2")
        self.queue.add(t1)
        self.queue.add(t2)

        self.assertEqual(self.queue.current().title, "Track 1")
        self.app.action_next_track()
        self.assertEqual(self.queue.current().title, "Track 2")

    def test_b_key_triggers_previous(self):
        """B action triggers previous track."""
        t1 = Track(title="Track 1", artist="Artist 1", source="https://youtube.com/watch?v=t1")
        t2 = Track(title="Track 2", artist="Artist 2", source="https://youtube.com/watch?v=t2")
        self.queue.add(t1)
        self.queue.add(t2)
        self.queue.next()

        self.assertEqual(self.queue.current().title, "Track 2")
        self.app.action_previous_track()
        self.assertEqual(self.queue.current().title, "Track 1")

    def test_q_key_exits_app(self):
        """Q action exits application cleanly."""
        with patch.object(self.app, "exit") as mock_exit:
            self.app.action_quit_app()
            mock_exit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
