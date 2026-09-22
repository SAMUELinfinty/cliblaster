from dataclasses import dataclass
import os
from typing import Callable, Dict, List, Tuple, Optional

from cliblaster.player import Player
from cliblaster.music_queue import Queue
from cliblaster.track import Track
from cliblaster.youtube import YouTubeClient, YouTubeAPIError
from cliblaster.auth import OAuthManager, AuthError


@dataclass
class CommandResult:
    """Represents the outcome of executing a command."""
    should_quit: bool = False


class CommandRouter:
    """Routes normalized input strings to registered handler functions."""

    def __init__(self, player: Player, queue: Queue, auth_manager: OAuthManager) -> None:
        self.player = player
        self.queue = queue
        self.auth_manager = auth_manager
        self.youtube = YouTubeClient(auth_manager=auth_manager)
        self.recent_search_results: List[Track] = []
        self.selected_track: Optional[Track] = None          # M8: explicitly selected track
        # Tracks displayed by the most recent 'playlist N' command
        self._open_playlists: List = []          # List[Playlist] from last 'playlists'
        self._open_playlist_tracks: List[Track] = []  # tracks from last 'playlist N'

        # Map command name -> handler function
        self._handlers: Dict[str, Callable[[List[str]], CommandResult]] = {
            "help": self._handle_help,
            "clear": self._handle_clear,
            "quit": self._handle_quit,
            "play": self._handle_play,
            "pause": self._handle_pause,
            "resume": self._handle_resume,
            "stop": self._handle_stop,
            "add": self._handle_add,
            "queue": self._handle_queue,
            "remove": self._handle_remove,
            "empty": self._handle_empty,
            "next": self._handle_next,
            "previous": self._handle_previous,
            "search": self._handle_search,
            "select": self._handle_select,
            "login": self._handle_login,
            "logout": self._handle_logout,
            "auth": self._handle_auth,
            "playlists": self._handle_playlists,
            "playlist": self._handle_playlist,
            "liked": self._handle_liked,
        }

    def _handle_help(self, args: List[str]) -> CommandResult:
        print("\nAvailable commands:")
        print("  login          - Connect YouTube account")
        print("  logout         - Disconnect YouTube account")
        print("  auth           - Show authentication status")
        print("  playlists      - List your YouTube playlists")
        print("  playlist [N]   - Show tracks in playlist N")
        print("  liked          - Show your liked videos (YouTube, not YT Music)")
        print("  search [query] - Search YouTube")
        print("  select [N]     - Select search result N")
        print("  add [file|N]   - Add to queue: selected track (no arg), file path, or result N")
        print("  queue          - Display the queue")
        print("  remove [N]     - Remove track at index N (1-based)")
        print("  empty          - Clear the queue")
        print("  play           - Play current track")
        print("  next           - Play next track")
        print("  previous       - Play previous track")
        print("  pause          - Pause playback")
        print("  resume         - Resume playback")
        print("  stop           - Stop playback")
        print("  help           - Show this help")
        print("  clear          - Clear terminal screen")
        print("  quit           - Exit application\n")
        return CommandResult(should_quit=False)

    def _handle_clear(self, args: List[str]) -> CommandResult:
        os.system("cls" if os.name == "nt" else "clear")
        return CommandResult(should_quit=False)

    def _handle_quit(self, args: List[str]) -> CommandResult:
        print("Goodbye!")
        return CommandResult(should_quit=True)

    def _handle_play(self, args: List[str]) -> CommandResult:
        track = self.queue.current()
        if track:
            self.player.play()
            # Print full track info (player.play already prints title,
            # but we also show artist here for a richer display)
            if self.player.state.name == "PLAYING":
                print(f"  {track.artist}")
        else:
            self.player.play()  # player will print 'Queue is empty'
        return CommandResult(should_quit=False)

    def _handle_pause(self, args: List[str]) -> CommandResult:
        self.player.pause()
        return CommandResult(should_quit=False)

    def _handle_resume(self, args: List[str]) -> CommandResult:
        self.player.resume()
        return CommandResult(should_quit=False)

    def _handle_stop(self, args: List[str]) -> CommandResult:
        self.player.stop()
        return CommandResult(should_quit=False)

    def _handle_search(self, args: List[str]) -> CommandResult:
        if not args:
            print("Please provide a search query.")
            return CommandResult(should_quit=False)
        query = " ".join(args)
        print(f"Searching YouTube for '{query}'...")
        try:
            results = self.youtube.search(query)
            self.recent_search_results = results
            self._open_playlist_tracks = []  # search clears playlist context
            self.selected_track = None       # clear any previous selection
            if not results:
                print("\nNo results found.")
            else:
                print("\nSEARCH RESULTS\n")
                for i, track in enumerate(results):
                    print(f"{i + 1}. {track.title}\n   {track.artist}\n")
        except YouTubeAPIError as e:
            print(f"\nYouTube API Error: {e}")
        except ValueError as e:
            print(f"\nError: {e}")

        return CommandResult(should_quit=False)

    def _handle_select(self, args: List[str]) -> CommandResult:
        """Select a search result by number, storing it as the current selection."""
        if not args or not args[0].isdigit():
            print("Usage: select <number>  (e.g. 'select 2')")
            return CommandResult(should_quit=False)

        if not self.recent_search_results:
            print("No search results. Run 'search <query>' first.")
            return CommandResult(should_quit=False)

        idx = int(args[0]) - 1
        if not (0 <= idx < len(self.recent_search_results)):
            print(f"Invalid search result: {args[0]}")
            return CommandResult(should_quit=False)

        self.selected_track = self.recent_search_results[idx]
        print(f"\nSelected:\n{self.selected_track.title} — {self.selected_track.artist}\n")
        return CommandResult(should_quit=False)

    def _handle_add(self, args: List[str]) -> CommandResult:
        # --- No args: add the currently selected track ---
        if not args:
            if self.selected_track:
                self.queue.add(self.selected_track)
                print(f"Added to queue:\n{self.selected_track.title}")
                self.selected_track = None   # consume the selection
            else:
                print(
                    "Nothing selected. Use 'select <N>' after a search, "
                    "or 'add <N>' to add directly."
                )
            return CommandResult(should_quit=False)

        # --- Numeric arg: add by position from search results or open playlist ---
        if len(args) == 1 and args[0].isdigit():
            idx = int(args[0]) - 1
            # Priority 1: if a playlist is open, use its tracks
            if self._open_playlist_tracks:
                if 0 <= idx < len(self._open_playlist_tracks):
                    track = self._open_playlist_tracks[idx]
                    self.queue.add(track)
                    print(f"Added to queue:\n{track.title}")
                else:
                    print(f"Invalid playlist track number: {args[0]}")
            # Priority 2: fall back to most recent search results
            elif self.recent_search_results:
                if 0 <= idx < len(self.recent_search_results):
                    track = self.recent_search_results[idx]
                    self.queue.add(track)
                    print(f"Added to queue:\n{track.title}")
                else:
                    print(f"Invalid search result number: {args[0]}")
            else:
                print("No search results or playlist open. Run 'search' or 'playlist N' first.")
        else:
            # --- String arg: treat as a local file path ---
            path = " ".join(args)
            title = os.path.basename(path)
            track = Track(title=title, artist="Unknown", source=path)
            self.queue.add(track)
            print(f"Added: {title}")

        return CommandResult(should_quit=False)

    def _handle_queue(self, args: List[str]) -> CommandResult:
        tracks = self.queue.all()
        if not tracks:
            print("\nQueue is empty.\n")
            return CommandResult(should_quit=False)
        
        print("\nQUEUE\n")
        for i, track in enumerate(tracks):
            marker = "▶" if i == self.queue.current_index else " "
            print(f"{marker} {i + 1}. {track.title}")
        print()
        return CommandResult(should_quit=False)

    def _handle_remove(self, args: List[str]) -> CommandResult:
        if not args:
            print("Please specify the queue position to remove.")
            return CommandResult(should_quit=False)
        try:
            pos = int(args[0])
            idx = pos - 1
            if self.queue.remove(idx):
                print(f"Removed track at position {pos}.")
            else:
                print(f"Invalid queue position: {pos}")
        except ValueError:
            print("Invalid queue position. Must be a number.")
        return CommandResult(should_quit=False)

    def _handle_empty(self, args: List[str]) -> CommandResult:
        self.queue.clear()
        self.player.stop()
        print("Queue cleared.")
        return CommandResult(should_quit=False)

    def _handle_next(self, args: List[str]) -> CommandResult:
        old_index = self.queue.current_index
        track = self.queue.next()
        if track:
            if old_index != self.queue.current_index:
                self.player.stop()
                self.player.play()
            else:
                print("Already at the end of the queue.")
        else:
            print("Queue is empty.")
        return CommandResult(should_quit=False)

    def _handle_previous(self, args: List[str]) -> CommandResult:
        old_index = self.queue.current_index
        track = self.queue.previous()
        if track:
            if old_index != self.queue.current_index:
                self.player.stop()
                self.player.play()
            else:
                print("Already at the beginning of the queue.")
        else:
            print("Queue is empty.")
        return CommandResult(should_quit=False)

    def _handle_login(self, args: List[str]) -> CommandResult:
        try:
            self.auth_manager.login()
            print("\n✓ Account connected successfully!")
        except AuthError as e:
            print(f"\nAuthentication failed: {e}")
        return CommandResult(should_quit=False)

    def _handle_logout(self, args: List[str]) -> CommandResult:
        self.auth_manager.logout()
        print("\nLogged out successfully (local credentials removed).")
        print("Note: To completely revoke access, visit https://myaccount.google.com/permissions")
        return CommandResult(should_quit=False)

    def _handle_auth(self, args: List[str]) -> CommandResult:
        if self.auth_manager.is_authenticated():
            print("\nAuthentication status:\n✓ Connected\n")
        else:
            print("\nAuthentication status:\n✗ Not connected\n")
        return CommandResult(should_quit=False)

    def _handle_playlists(self, args: List[str]) -> CommandResult:
        try:
            playlists = self.youtube.get_playlists()
            self._open_playlists = playlists
            self._open_playlist_tracks = []  # reset track context
            if not playlists:
                print("\nNo playlists found.\n")
            else:
                print("\nYOUR PLAYLISTS\n")
                for i, pl in enumerate(playlists):
                    count = f"{pl.item_count} tracks" if pl.item_count else ""
                    print(f"{i + 1}. {pl.title}  {count}")
                print()
        except YouTubeAPIError as e:
            print(f"\nYouTube API Error: {e}")
        return CommandResult(should_quit=False)

    def _handle_playlist(self, args: List[str]) -> CommandResult:
        if not args or not args[0].isdigit():
            print("Usage: playlist <number>  (e.g. 'playlist 2')")
            return CommandResult(should_quit=False)

        if not self._open_playlists:
            print("No playlists loaded. Run 'playlists' first.")
            return CommandResult(should_quit=False)

        idx = int(args[0]) - 1
        if not (0 <= idx < len(self._open_playlists)):
            print(f"Invalid playlist number: {args[0]}")
            return CommandResult(should_quit=False)

        playlist = self._open_playlists[idx]
        try:
            tracks = self.youtube.get_playlist_items(playlist.id)
            self._open_playlist_tracks = tracks
            self.recent_search_results = []  # clear search context
            if not tracks:
                print(f"\n{playlist.title.upper()}\n\n(No tracks found or playlist is empty.)\n")
            else:
                print(f"\n{playlist.title.upper()}\n")
                for i, track in enumerate(tracks):
                    print(f"{i + 1}. {track.title}\n   {track.artist}\n")
        except YouTubeAPIError as e:
            print(f"\nYouTube API Error: {e}")
        return CommandResult(should_quit=False)

    def _handle_liked(self, args: List[str]) -> CommandResult:
        print("Fetching liked videos (YouTube liked videos, not YouTube Music)...")
        try:
            tracks = self.youtube.get_liked_videos()
            self._open_playlist_tracks = tracks
            self.recent_search_results = []
            if not tracks:
                print("\nNo liked videos found.\n")
            else:
                print("\nLIKED VIDEOS (most recent 50)\n")
                print("Note: This shows YouTube liked videos, not YouTube Music 'Liked Music'.")
                print("YouTube Music's library is not accessible via the YouTube Data API.\n")
                for i, track in enumerate(tracks):
                    print(f"{i + 1}. {track.title}\n   {track.artist}\n")
        except YouTubeAPIError as e:
            print(f"\nYouTube API Error: {e}")
        return CommandResult(should_quit=False)

    def normalize_input(self, raw_input: str) -> Tuple[str, List[str]]:
        tokens = raw_input.strip().split()
        if not tokens:
            return ("", [])
        command = tokens[0].lower()
        args = tokens[1:]
        return (command, args)

    def dispatch(self, raw_input: str) -> CommandResult:
        command, args = self.normalize_input(raw_input)
        if not command:
            return CommandResult(should_quit=False)

        handler = self._handlers.get(command)
        if handler:
            return handler(args)
        else:
            print(f"\nUnknown command: {command}\n")
            return CommandResult(should_quit=False)

