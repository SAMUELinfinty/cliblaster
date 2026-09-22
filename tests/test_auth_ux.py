"""
Unit tests for Milestone 10: Google Login UX and Authentication Flow.
All tests use mocks — no real network calls, Google login, or hardware required.
"""

import os
import json
import time
import unittest
from unittest.mock import MagicMock, patch

from cliblaster.auth import OAuthManager, AuthError
from cliblaster.music_queue import Queue
from cliblaster.player import Player, PlayerState
from cliblaster.audio_backend import AudioBackend
from cliblaster.commands import CommandRouter
from cliblaster.tui import CLIBLASTERApp, LoginScreen, MainScreen, HeaderWidget


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


class TestGoogleLoginUX(unittest.TestCase):

    def setUp(self):
        self.backend = MockAudioBackend()
        self.queue = Queue()
        self.player = Player(backend=self.backend, queue=self.queue)
        self.auth_manager = MagicMock(spec=OAuthManager)
        self.auth_manager.client_id = "mock_client_id"
        self.auth_manager.client_secret = "mock_client_secret"
        self.router = CommandRouter(player=self.player, queue=self.queue, auth_manager=self.auth_manager)

    def test_scenario_1_unauthenticated_shows_login_screen(self):
        """Scenario 1: User is not authenticated -> Initial screen is LoginScreen."""
        self.auth_manager.is_authenticated.return_value = False
        app = CLIBLASTERApp(router=self.router, player=self.player, queue=self.queue, auth_manager=self.auth_manager)

        with patch.object(app, "push_screen") as mock_push:
            app.on_mount()
            mock_push.assert_called_once()
            args, _ = mock_push.call_args
            self.assertIsInstance(args[0], LoginScreen)

    def test_scenario_2_successful_authentication(self):
        """Scenario 2: User authenticates successfully -> OAuth login succeeds."""
        self.auth_manager.is_authenticated.return_value = True
        self.auth_manager.login.return_value = None

        header = HeaderWidget(auth_manager=self.auth_manager)
        rendered = header.render()
        self.assertIn("✓ Logged in", rendered)

    def test_scenario_3_already_authenticated_skips_login_screen(self):
        """Scenario 3: User already has valid credentials -> Goes straight to MainScreen."""
        self.auth_manager.is_authenticated.return_value = True
        app = CLIBLASTERApp(router=self.router, player=self.player, queue=self.queue, auth_manager=self.auth_manager)

        with patch.object(app, "push_screen") as mock_push:
            app.on_mount()
            mock_push.assert_called_once()
            args, _ = mock_push.call_args
            self.assertIsInstance(args[0], MainScreen)

    def test_scenario_4_expired_token_automatically_refreshed(self):
        """Scenario 4: Expired credentials automatically refresh."""
        manager = OAuthManager(client_secret_path="non_existent.json", token_path="non_existent.json")
        manager.access_token = "old_token"
        manager.refresh_token = "valid_refresh_token"
        manager.expires_at = time.time() - 100  # expired

        with patch.object(manager, "_refresh_access_token", return_value=True) as mock_refresh:
            result = manager.is_authenticated()
            mock_refresh.assert_called_once()
            self.assertTrue(result)

    def test_scenario_5_unrefreshable_token_sends_user_to_login(self):
        """Scenario 5: Credentials cannot be refreshed -> returns False so app prompts for login."""
        manager = OAuthManager(client_secret_path="non_existent.json", token_path="non_existent.json")
        manager.access_token = "revoked_token"
        manager.refresh_token = "invalid_refresh_token"
        manager.expires_at = time.time() - 100  # expired

        with patch.object(manager, "_refresh_access_token", return_value=False) as mock_refresh:
            result = manager.is_authenticated()
            mock_refresh.assert_called_once()
            self.assertFalse(result)

    def test_scenario_6_user_logout_clears_credentials(self):
        """Scenario 6: User logs out -> Credentials cleared and pushed to LoginScreen."""
        self.auth_manager.is_authenticated.return_value = False
        app = CLIBLASTERApp(router=self.router, player=self.player, queue=self.queue, auth_manager=self.auth_manager)

        with patch.object(app, "push_screen") as mock_push:
            app.action_logout_user()
            self.auth_manager.logout.assert_called_once()
            mock_push.assert_called_once()
            args, _ = mock_push.call_args
            self.assertIsInstance(args[0], LoginScreen)


if __name__ == "__main__":
    unittest.main()
