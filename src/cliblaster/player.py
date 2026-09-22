from enum import Enum, auto
import sys
from typing import Optional

from cliblaster.track import Track
from cliblaster.audio_backend import AudioBackend
from cliblaster.music_queue import Queue


def safe_print(text: str) -> None:
    """Prints text safely, falling back to ASCII if stdout encoding fails."""
    try:
        print(text)
    except UnicodeEncodeError:
        ascii_text = text.replace("▶", ">").replace("⏸", "||").replace("■", "[STOP]")
        print(ascii_text)


class PlayerState(Enum):
    """Enumeration of possible playback states."""
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class Player:
    """Manages playback state and current track information."""

    def __init__(self, backend: AudioBackend, queue: Queue) -> None:
        self.state: PlayerState = PlayerState.STOPPED
        self.backend = backend
        self.queue = queue
        self.volume: int = 100

    def set_volume(self, percent: int) -> int:
        """Sets playback volume percentage (0 to 100)."""
        self.volume = max(0, min(100, percent))
        if hasattr(self.backend, "set_volume"):
            self.backend.set_volume(self.volume / 100.0)
        return self.volume

    def volume_up(self, step: int = 10) -> int:
        """Increases volume by step percent."""
        return self.set_volume(self.volume + step)

    def volume_down(self, step: int = 10) -> int:
        """Decreases volume by step percent."""
        return self.set_volume(self.volume - step)

    def play(self) -> None:
        """Starts playing the current track from the queue, or resumes playback."""
        track = self.queue.current()
        if not track:
            safe_print("Queue is empty. Add tracks using 'add <file>'.")
            return

        if self.state == PlayerState.PAUSED:
            self.backend.resume()
        else:
            try:
                self.backend.load(track.source)
                self.backend.play()
            except Exception as e:
                safe_print(f"Error loading track: {e}")
                return

        self.state = PlayerState.PLAYING
        safe_print(f"▶ Playing: {track.title}")

    def pause(self) -> None:
        """Pauses the player if it is currently playing."""
        if self.state == PlayerState.PLAYING:
            self.backend.pause()
            self.state = PlayerState.PAUSED
            safe_print("⏸ Paused")
        elif self.state == PlayerState.PAUSED:
            safe_print("Player is already paused.")
        else:
            safe_print("Nothing is currently playing.")

    def resume(self) -> None:
        """Resumes playback if the player is currently paused."""
        if self.state == PlayerState.PAUSED:
            self.backend.resume()
            self.state = PlayerState.PLAYING
            safe_print("▶ Playing")
        elif self.state == PlayerState.PLAYING:
            safe_print("Player is already playing.")
        else:
            safe_print("Nothing to resume.")

    def stop(self) -> None:
        """Stops playback if currently playing or paused."""
        if self.state in (PlayerState.PLAYING, PlayerState.PAUSED):
            self.backend.stop()
            self.state = PlayerState.STOPPED
            safe_print("■ Stopped")
        else:
            safe_print("Player is already stopped.")

