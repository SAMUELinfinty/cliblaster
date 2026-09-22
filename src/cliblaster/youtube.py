import os
import json
import html
import urllib.request
import urllib.parse
from urllib.error import URLError, HTTPError
from typing import Dict, List, Optional

from cliblaster.track import Track
from cliblaster.playlist import Playlist

_API_BASE = "https://www.googleapis.com/youtube/v3"
_MAX_PAGES = 10          # safety cap to avoid runaway pagination
_PAGE_SIZE = 50          # maximum allowed by the YouTube API


class YouTubeAPIError(Exception):
    """Custom exception for YouTube API related errors."""
    pass


class YouTubeClient:
    """
    Client for interacting with the YouTube Data API v3.

    Supports two authentication modes:
      - API key  → public/search requests (no user account needed)
      - OAuth    → authenticated requests (user's playlists, liked videos …)

    A simple in-memory cache avoids re-fetching the same resource within
    a single CLIBLASTER session.
    """

    def __init__(self, api_key: str = None, auth_manager=None) -> None:
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.auth_manager = auth_manager
        # session-level cache: endpoint+params → parsed response
        self._cache: Dict[str, object] = {}

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get(self, endpoint: str, params: dict) -> dict:
        """
        Make an authenticated or API-key GET request to the given endpoint.
        Results are cached for the lifetime of the process.
        """
        use_oauth = bool(self.auth_manager and self.auth_manager.is_authenticated())

        if use_oauth:
            # OAuth requests don't need the API key in the query string;
            # the bearer token in the Authorization header is sufficient.
            pass
        elif self.api_key:
            params["key"] = self.api_key
        else:
            raise YouTubeAPIError(
                "Missing YouTube API Key or OAuth credentials. "
                "Please set YOUTUBE_API_KEY or run 'login'."
            )

        url = f"{_API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"

        # Cache hit
        if url in self._cache:
            return self._cache[url]

        headers = {"User-Agent": "CLIBLASTER/1.0"}
        if use_oauth:
            headers["Authorization"] = f"Bearer {self.auth_manager.get_access_token()}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                pass
            if e.code == 401:
                raise YouTubeAPIError(
                    "YouTube API: Not authorized (401). Try 'login' again."
                )
            elif e.code == 403:
                # Could be quota OR scope issue
                if "quotaExceeded" in body or "rateLimitExceeded" in body:
                    raise YouTubeAPIError("YouTube API quota exceeded (403).")
                raise YouTubeAPIError(
                    "YouTube API: Forbidden (403). "
                    "You may need to add the required OAuth scope and re-login."
                )
            elif e.code == 400:
                raise YouTubeAPIError(f"YouTube API: Bad request (400). {body}")
            else:
                raise YouTubeAPIError(f"YouTube API: HTTP {e.code} — {e.reason}")
        except URLError as e:
            raise YouTubeAPIError(
                f"Unable to connect to YouTube. Check your internet connection. ({e.reason})"
            )
        except json.JSONDecodeError:
            raise YouTubeAPIError("YouTube API returned malformed JSON.")

        self._cache[url] = data
        return data

    def _require_auth(self) -> None:
        """Raises YouTubeAPIError if OAuth is not available."""
        if not (self.auth_manager and self.auth_manager.is_authenticated()):
            raise YouTubeAPIError(
                "YouTube account not connected.\n\nRun:\n  login"
            )

    def _paginate(self, endpoint: str, base_params: dict) -> List[dict]:
        """
        Collects all items across paginated API responses, up to _MAX_PAGES.
        Returns a flat list of raw item dicts from every page.
        """
        items: List[dict] = []
        page_token: Optional[str] = None

        for _ in range(_MAX_PAGES):
            params = dict(base_params)
            if page_token:
                params["pageToken"] = page_token

            data = self._get(endpoint, params)
            items.extend(data.get("items", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return items

    # ------------------------------------------------------------------ #
    # Public API — Search (from M5)
    # ------------------------------------------------------------------ #

    def search(self, query: str, max_results: int = 5) -> List[Track]:
        """Searches YouTube and returns a list of Tracks."""
        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
        }

        data = self._get("search", params)

        tracks = []
        for item in data.get("items", []):
            try:
                title = html.unescape(item["snippet"]["title"])
                artist = html.unescape(item["snippet"]["channelTitle"])
                video_id = item["id"]["videoId"]
                source = f"https://www.youtube.com/watch?v={video_id}"
                tracks.append(Track(title=title, artist=artist, source=source))
            except KeyError:
                continue

        return tracks

    # ------------------------------------------------------------------ #
    # Public API — Library (M7)
    # ------------------------------------------------------------------ #

    def get_playlists(self) -> List[Playlist]:
        """
        Returns all playlists owned by the authenticated user.

        Uses: playlists.list  (mine=true, part=snippet,contentDetails)
        Quota cost: ~1 unit per page.
        """
        self._require_auth()

        raw_items = self._paginate("playlists", {
            "part": "snippet,contentDetails",
            "mine": "true",
            "maxResults": _PAGE_SIZE,
        })

        playlists = []
        for item in raw_items:
            try:
                playlist_id = item["id"]
                title = html.unescape(item["snippet"]["title"])
                description = html.unescape(item["snippet"].get("description", ""))
                item_count = item["contentDetails"].get("itemCount", 0)
                playlists.append(Playlist(
                    id=playlist_id,
                    title=title,
                    description=description,
                    item_count=item_count,
                ))
            except KeyError:
                continue

        return playlists

    def get_playlist_items(self, playlist_id: str) -> List[Track]:
        """
        Returns all tracks inside a playlist.

        Uses: playlistItems.list  (part=snippet,contentDetails)
        Quota cost: ~1 unit per page.
        Skips deleted/private videos (they have kind 'youtube#video' but no usable videoId).
        """
        self._require_auth()

        raw_items = self._paginate("playlistItems", {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": _PAGE_SIZE,
        })

        tracks = []
        for item in raw_items:
            try:
                snippet = item["snippet"]
                video_id = snippet["resourceId"]["videoId"]

                # Deleted / private videos still appear but with placeholder title
                title_raw = snippet["title"]
                if title_raw in ("Deleted video", "Private video"):
                    continue

                title = html.unescape(title_raw)
                artist = html.unescape(snippet.get("videoOwnerChannelTitle", "Unknown"))
                source = f"https://www.youtube.com/watch?v={video_id}"
                tracks.append(Track(title=title, artist=artist, source=source))
            except KeyError:
                continue

        return tracks

    def get_liked_videos(self, max_results: int = 50) -> List[Track]:
        """
        Returns the authenticated user's liked videos.

        NOTE: This returns YouTube *liked videos*, not the YouTube Music
        "Liked Music" playlist.  YouTube Music's internal library is NOT
        exposed through the official YouTube Data API v3.  What you see
        here are videos you have clicked the Like (👍) button on while
        signed in to YouTube.

        Uses: videos.list  (myRating=like, part=snippet)
        Quota cost: ~1 unit per page.  Limited to max_results (max 50 per call).
        """
        self._require_auth()

        # The videos.list with myRating supports pagination too, but
        # we limit to max_results because "liked videos" can be thousands long.
        params = {
            "part": "snippet",
            "myRating": "like",
            "maxResults": min(max_results, _PAGE_SIZE),
        }

        data = self._get("videos", params)

        tracks = []
        for item in data.get("items", []):
            try:
                video_id = item["id"]
                title = html.unescape(item["snippet"]["title"])
                artist = html.unescape(item["snippet"].get("channelTitle", "Unknown"))
                source = f"https://www.youtube.com/watch?v={video_id}"
                tracks.append(Track(title=title, artist=artist, source=source))
            except KeyError:
                continue

        return tracks
