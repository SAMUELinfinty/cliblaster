import unittest
from cliblaster.player import Player, PlayerState
from cliblaster.commands import CommandRouter
from cliblaster.audio_backend import AudioBackend
from cliblaster.track import Track
from cliblaster.music_queue import Queue


class MockAudioBackend(AudioBackend):
    def __init__(self):
        self.loaded_path = None
        self.is_playing = False
        self.is_paused = False
        
    def load(self, path: str) -> None:
        if path == "non_existent.mp3":
            raise FileNotFoundError("Mock file not found")
        self.loaded_path = path
        
    def play(self) -> None:
        self.is_playing = True
        self.is_paused = False
        
    def pause(self) -> None:
        self.is_paused = True
        self.is_playing = False
        
    def resume(self) -> None:
        self.is_playing = True
        self.is_paused = False
        
    def stop(self) -> None:
        self.is_playing = False
        self.is_paused = False


class TestPlayerState(unittest.TestCase):

    def setUp(self):
        self.backend = MockAudioBackend()
        self.queue = Queue()
        self.player = Player(backend=self.backend, queue=self.queue)
        self.track = Track(title="Test Song", artist="Test Artist", source="test.mp3")

    def test_initial_state(self):
        """1. New Player starts in STOPPED state and has empty queue."""
        self.assertEqual(self.player.state, PlayerState.STOPPED)
        self.assertIsNone(self.queue.current())

    def test_play_changes_state_to_playing(self):
        """2. play() changes state to PLAYING."""
        self.queue.add(self.track)
        self.player.play()
        self.assertEqual(self.player.state, PlayerState.PLAYING)
        self.assertTrue(self.backend.is_playing)

    def test_pause_changes_playing_to_paused(self):
        """3. pause() changes PLAYING -> PAUSED."""
        self.queue.add(self.track)
        self.player.play()
        self.player.pause()
        self.assertEqual(self.player.state, PlayerState.PAUSED)
        self.assertTrue(self.backend.is_paused)

    def test_resume_changes_paused_to_playing(self):
        """4. resume() changes PAUSED -> PLAYING."""
        self.queue.add(self.track)
        self.player.play()
        self.player.pause()
        self.player.resume()
        self.assertEqual(self.player.state, PlayerState.PLAYING)
        self.assertTrue(self.backend.is_playing)

    def test_stop_changes_playing_to_stopped(self):
        """5. stop() changes PLAYING -> STOPPED."""
        self.queue.add(self.track)
        self.player.play()
        self.player.stop()
        self.assertEqual(self.player.state, PlayerState.STOPPED)
        self.assertFalse(self.backend.is_playing)

    def test_stop_changes_paused_to_stopped(self):
        """6. stop() changes PAUSED -> STOPPED."""
        self.queue.add(self.track)
        self.player.play()
        self.player.pause()
        self.player.stop()
        self.assertEqual(self.player.state, PlayerState.STOPPED)
        self.assertFalse(self.backend.is_playing)

    def test_invalid_transitions_handled_sensibly(self):
        """7. Invalid operations do not corrupt state."""
        self.player.pause()
        self.assertEqual(self.player.state, PlayerState.STOPPED)
        self.player.resume()
        self.assertEqual(self.player.state, PlayerState.STOPPED)
        self.queue.add(self.track)
        self.player.play()
        self.player.resume()
        self.assertEqual(self.player.state, PlayerState.PLAYING)
        self.player.pause()
        self.player.pause()
        self.assertEqual(self.player.state, PlayerState.PAUSED)
        self.player.stop()
        self.player.stop()
        self.assertEqual(self.player.state, PlayerState.STOPPED)

    def test_cli_commands_call_player_methods(self):
        """Test that CLI commands update the Player state correctly via CommandRouter."""
        from cliblaster.auth import OAuthManager
        import unittest.mock as mock
        with mock.patch("os.path.exists", return_value=False):
            auth_manager = OAuthManager(client_secret_path="dummy", token_path="dummy")
        router = CommandRouter(player=self.player, queue=self.queue, auth_manager=auth_manager)
        router.dispatch("add SongA.mp3")
        router.dispatch("play")
        self.assertEqual(self.player.state, PlayerState.PLAYING)
        self.assertEqual(self.queue.current().title, "SongA.mp3")
        router.dispatch("pause")
        self.assertEqual(self.player.state, PlayerState.PAUSED)
        router.dispatch("resume")
        self.assertEqual(self.player.state, PlayerState.PLAYING)
        router.dispatch("stop")
        self.assertEqual(self.player.state, PlayerState.STOPPED)

    def test_error_handling_file_not_found(self):
        """Test that loading a non-existent file handles cleanly."""
        bad_track = Track(title="bad", artist="none", source="non_existent.mp3")
        self.queue.add(bad_track)
        self.player.play()
        self.assertEqual(self.player.state, PlayerState.STOPPED)


if __name__ == "__main__":
    unittest.main()
