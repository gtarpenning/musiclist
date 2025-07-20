from dataclasses import dataclass
from urllib.parse import urljoin
from typing import Optional


@dataclass
class Venue:
    name: str
    base_url: str
    calendar_path: str = "/calendar/"

    def __post_init__(self):
        # Ensure base_url ends with /
        if not self.base_url.endswith("/"):
            self.base_url += "/"

        # Ensure calendar_path starts with /
        if not self.calendar_path.startswith("/"):
            self.calendar_path = "/" + self.calendar_path

    @property
    def calendar_url(self) -> str:
        """Full URL to venue's calendar page"""
        return urljoin(self.base_url, self.calendar_path.lstrip("/"))

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "calendar_path": self.calendar_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Venue":
        """Create Venue from dictionary"""
        return cls(
            name=data["name"],
            base_url=data["base_url"],
            calendar_path=data.get("calendar_path", "/calendar/"),
        )
