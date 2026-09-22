from typing import List, Optional
from cliblaster.track import Track

class Queue:
    """Manages an in-memory queue of tracks and the current playback position."""
    
    def __init__(self) -> None:
        self.tracks: List[Track] = []
        self.current_index: int = -1

    def add(self, track: Track) -> None:
        """Adds a track to the end of the queue."""
        self.tracks.append(track)
        if self.current_index == -1:
            self.current_index = 0

    def remove(self, index: int) -> bool:
        """Removes a track at the given 0-based index. Returns True if successful."""
        if 0 <= index < len(self.tracks):
            self.tracks.pop(index)
            # Adjust current index if necessary
            if self.current_index > index:
                self.current_index -= 1
            elif self.current_index == index:
                if self.current_index >= len(self.tracks):
                    self.current_index = len(self.tracks) - 1
            if not self.tracks:
                self.current_index = -1
            return True
        return False

    def clear(self) -> None:
        """Removes all tracks from the queue."""
        self.tracks.clear()
        self.current_index = -1

    def current(self) -> Optional[Track]:
        """Returns the currently selected track, or None if the queue is empty."""
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def next(self) -> Optional[Track]:
        """Moves to the next track if available and returns it."""
        if not self.tracks:
            return None
        if self.current_index < len(self.tracks) - 1:
            self.current_index += 1
        return self.current()

    def previous(self) -> Optional[Track]:
        """Moves to the previous track if available and returns it."""
        if not self.tracks:
            return None
        if self.current_index > 0:
            self.current_index -= 1
        return self.current()

    def all(self) -> List[Track]:
        """Returns a copy of the list of all tracks."""
        return list(self.tracks)
