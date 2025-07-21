from datetime import datetime, date, time
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Event:
    date: date
    time: Optional[time]
    artists: List[str]
    venue: str
    url: str
    cost: Optional[str] = None
    pinned: bool = False
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

        # Clean and validate artists
        if isinstance(self.artists, str):
            self.artists = [self.artists]
        self.artists = [artist.strip() for artist in self.artists if artist.strip()]

        if not self.artists:
            raise ValueError("Event must have at least one artist")

    @property
    def artists_display(self) -> str:
        """Format artists for display"""
        return ", ".join(self.artists)

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            "date": self.date.isoformat(),
            "time": self.time.isoformat() if self.time else None,
            "artists": self.artists_display,
            "venue": self.venue,
            "url": self.url,
            "cost": self.cost,
            "pinned": self.pinned,
            "id": self.id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """Create Event from dictionary"""
        return cls(
            date=date.fromisoformat(data["date"]),
            time=time.fromisoformat(data["time"]) if data["time"] else None,
            artists=data["artists"].split(", ") if data["artists"] else [],
            venue=data["venue"],
            url=data["url"],
            cost=data.get("cost"),
            pinned=data.get("pinned", False),
            id=data.get("id"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
