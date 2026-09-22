from typing import Protocol

class AudioBackend(Protocol):
    def load(self, path: str) -> None:
        """Load an audio file for playback."""
        ...
        
    def play(self) -> None:
        """Start playing the loaded audio."""
        ...
        
    def pause(self) -> None:
        """Pause playback."""
        ...
        
    def resume(self) -> None:
        """Resume playback."""
        ...
        
    def stop(self) -> None:
        """Stop playback."""
        ...

    def set_volume(self, volume: float) -> None:
        """Set playback volume between 0.0 and 1.0."""
        ...

    def get_volume(self) -> float:
        """Get current playback volume."""
        ...
