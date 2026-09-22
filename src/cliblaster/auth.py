import os
import json
import urllib.request
import urllib.parse
from urllib.error import URLError, HTTPError
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

class AuthError(Exception):
    pass

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles the redirect from Google OAuth and extracts the authorization code."""
    # Class-level variable to store the captured code because HTTP handlers are instantiated per request
    auth_code = None
    
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if 'code' in params:
            OAuthCallbackHandler.auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authentication successful!</h1><p>You can close this tab and return to CLIBLASTER.</p></body></html>")
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authentication failed!</h1><p>No authorization code found.</p></body></html>")

    def log_message(self, format, *args):
        # Suppress server logging
        pass

class OAuthManager:
    """Manages Google OAuth 2.0 flow, credential storage, and token refreshing."""
    
    # Scopes needed for read-only YouTube access (like search and playlists)
    SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
    
    def __init__(self, client_secret_path="client_secret.json", token_path="token.json"):
        self.client_secret_path = client_secret_path
        self.token_path = token_path
        self.client_id = None
        self.client_secret = None
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0
        
        self._load_client_secret()
        self._load_token()

    def _load_client_secret(self):
        """Loads the OAuth client configuration from Google Cloud."""
        if os.path.exists(self.client_secret_path):
            try:
                with open(self.client_secret_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    installed = data.get("installed", {})
                    self.client_id = installed.get("client_id")
                    self.client_secret = installed.get("client_secret")
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_token(self):
        """Loads saved user credentials from previous sessions."""
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    self.expires_at = data.get("expires_at", 0)
            except json.JSONDecodeError:
                pass

    def _save_token(self):
        """Saves user credentials securely to local storage."""
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at
        }
        with open(self.token_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def is_authenticated(self) -> bool:
        """Returns True if the user is authenticated and token is valid/refreshed."""
        if not self.access_token:
            return False
            
        # Check if expired
        if time.time() > self.expires_at - 60:  # refresh 1 minute early
            return self._refresh_access_token()
            
        return True

    def get_access_token(self) -> str:
        """Returns the current valid access token."""
        if self.is_authenticated():
            return self.access_token
        raise AuthError("Not authenticated.")

    def login(self):
        """Initiates the OAuth 2.0 local server flow."""
        if not self.client_id or not self.client_secret:
            raise AuthError(f"Missing OAuth client configuration. Please ensure {self.client_secret_path} is correctly configured.")

        # Start a local server to capture the redirect
        ports_to_try = [8080, 8081, 8085, 8088, 8090, 8999, 9090, 9999]
        server = None
        bound_port = None
        for p in ports_to_try:
            try:
                server = HTTPServer(('127.0.0.1', p), OAuthCallbackHandler)
                bound_port = p
                break
            except OSError:
                continue

        if not server or not bound_port:
            raise AuthError("Unable to bind to local HTTP port for OAuth callback. Ports 8080-9999 are blocked or in use.")

        redirect_uri = f"http://127.0.0.1:{bound_port}"
        OAuthCallbackHandler.auth_code = None

        # Open browser
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={self.client_id}&"
            f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
            f"response_type=code&"
            f"scope={urllib.parse.quote(' '.join(self.SCOPES))}&"
            f"access_type=offline&"
            f"prompt=consent"
        )
        
        print("\nOpening browser for authentication...")
        if not webbrowser.open(auth_url):
            print("Could not open browser. Please navigate to this URL manually:\n")
            print(auth_url)
            print()
            
        # Wait for the callback (blocks until request is received)
        server.handle_request()
        
        code = OAuthCallbackHandler.auth_code
        if not code:
            raise AuthError("Authorization failed or user cancelled.")
            
        # Exchange code for token
        self._exchange_code_for_token(code, redirect_uri)

    def _exchange_code_for_token(self, code: str, redirect_uri: str):
        data = urllib.parse.urlencode({
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }).encode('utf-8')
        
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                self.access_token = res_data['access_token']
                self.refresh_token = res_data.get('refresh_token', self.refresh_token)
                self.expires_at = time.time() + res_data['expires_in']
                self._save_token()
        except HTTPError as e:
            raise AuthError(f"Failed to exchange token. HTTP Error {e.code}: {e.read().decode('utf-8')}")
        except URLError as e:
            raise AuthError(f"Network error exchanging token: {e.reason}")

    def _refresh_access_token(self) -> bool:
        """Attempts to refresh the access token using the refresh token."""
        if not self.refresh_token:
            return False
            
        data = urllib.parse.urlencode({
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }).encode('utf-8')
        
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                self.access_token = res_data['access_token']
                self.expires_at = time.time() + res_data['expires_in']
                self._save_token()
                return True
        except HTTPError:
            # Refresh failed (e.g. token revoked)
            self.logout()
            return False
        except URLError:
            # Network error - don't log out, just say not authenticated for now
            return False

    def logout(self):
        """Removes local token credentials. Does not revoke on Google's side."""
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0
        if os.path.exists(self.token_path):
            os.remove(self.token_path)
