import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import time

from cliblaster.auth import OAuthManager, AuthError

class TestAuthManager(unittest.TestCase):
    def setUp(self):
        # We don't want it to actually load files in setUp, so we patch os.path.exists
        with patch("os.path.exists", return_value=False):
            self.auth = OAuthManager(client_secret_path="dummy_secret.json", token_path="dummy_token.json")
            self.auth.client_id = "test_client"
            self.auth.client_secret = "test_secret"

    def test_initial_state(self):
        self.assertFalse(self.auth.is_authenticated())
        with self.assertRaises(AuthError):
            self.auth.get_access_token()

    @patch("time.time", return_value=1000)
    def test_valid_token(self, mock_time):
        self.auth.access_token = "valid_token"
        self.auth.expires_at = 2000
        self.assertTrue(self.auth.is_authenticated())
        self.assertEqual(self.auth.get_access_token(), "valid_token")

    @patch("time.time", return_value=3000)
    @patch.object(OAuthManager, "_refresh_access_token")
    def test_expired_token_triggers_refresh(self, mock_refresh, mock_time):
        self.auth.access_token = "expired_token"
        self.auth.expires_at = 2000
        mock_refresh.return_value = True
        
        self.assertTrue(self.auth.is_authenticated())
        mock_refresh.assert_called_once()

    @patch("time.time", return_value=3000)
    @patch.object(OAuthManager, "_refresh_access_token")
    def test_refresh_failure(self, mock_refresh, mock_time):
        self.auth.access_token = "expired_token"
        self.auth.expires_at = 2000
        mock_refresh.return_value = False
        
        self.assertFalse(self.auth.is_authenticated())

    def test_logout(self):
        self.auth.access_token = "token"
        self.auth.refresh_token = "refresh"
        self.auth.expires_at = 2000
        
        with patch("os.path.exists", return_value=True):
            with patch("os.remove") as mock_remove:
                self.auth.logout()
                self.assertIsNone(self.auth.access_token)
                self.assertIsNone(self.auth.refresh_token)
                self.assertEqual(self.auth.expires_at, 0)
                mock_remove.assert_called_once_with("dummy_token.json")

    @patch("urllib.request.urlopen")
    @patch("time.time", return_value=1000)
    def test_refresh_success(self, mock_time, mock_urlopen):
        self.auth.refresh_token = "valid_refresh"
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "access_token": "new_token",
            "expires_in": 3600
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with patch("builtins.open", mock_open()):
            result = self.auth._refresh_access_token()
            self.assertTrue(result)
            self.assertEqual(self.auth.access_token, "new_token")
            self.assertEqual(self.auth.expires_at, 4600)

if __name__ == "__main__":
    unittest.main()
