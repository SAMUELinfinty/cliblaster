import unittest
from cliblaster.commands import CommandRouter, CommandResult
from cliblaster.player import Player
from cliblaster.music_queue import Queue
from cliblaster.audio_backend import AudioBackend
from cliblaster.auth import OAuthManager
import unittest.mock as mock

class MockBackend(AudioBackend):
    def load(self, path): pass
    def play(self): pass
    def pause(self): pass
    def resume(self): pass
    def stop(self): pass

class TestCommandRouter(unittest.TestCase):

    def setUp(self):
        self.queue = Queue()
        self.player = Player(backend=MockBackend(), queue=self.queue)
        
        # Avoid file I/O in OAuthManager by mocking os.path.exists
        with mock.patch("os.path.exists", return_value=False):
            self.auth_manager = OAuthManager(client_secret_path="dummy", token_path="dummy")
            
        self.router = CommandRouter(player=self.player, queue=self.queue, auth_manager=self.auth_manager)

        cmd, args = self.router.normalize_input("  HELP  ")
        self.assertEqual(cmd, "help")
        self.assertEqual(args, [])

        cmd, args = self.router.normalize_input("CLEAR")
        self.assertEqual(cmd, "clear")
        self.assertEqual(args, [])

        cmd, args = self.router.normalize_input("   ")
        self.assertEqual(cmd, "")
        self.assertEqual(args, [])

    def test_quit_command(self):
        result = self.router.dispatch("quit")
        self.assertEqual(result, CommandResult(should_quit=True))

        result_upper = self.router.dispatch("  QUIT  ")
        self.assertEqual(result_upper, CommandResult(should_quit=True))

    def test_help_command(self):
        result = self.router.dispatch("help")
        self.assertEqual(result, CommandResult(should_quit=False))

    def test_clear_command(self):
        result = self.router.dispatch("clear")
        self.assertEqual(result, CommandResult(should_quit=False))

    def test_unknown_command(self):
        result = self.router.dispatch("foobar")
        self.assertEqual(result, CommandResult(should_quit=False))


if __name__ == "__main__":
    unittest.main()
