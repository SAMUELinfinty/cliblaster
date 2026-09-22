from dataclasses import dataclass, field


@dataclass
class Playlist:
    """Represents a YouTube playlist from the authenticated user's account."""
    id: str
    title: str
    description: str
    item_count: int
