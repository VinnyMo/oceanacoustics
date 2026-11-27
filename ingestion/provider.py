"""Interface for public, UTC-indexed mono PCM archives consumed by the 2 kHz worker."""
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol


class SourceObject(Protocol):
    key: str  # Stable archive-wide ID; future providers must namespace their keys.
    size: int
    modified: str
    etag: str
    start: datetime


class Archive(Protocol):
    location: str
    first_month: str

    def latest_month(self) -> str: ...
    def records(self, month: str) -> Iterable[SourceObject]: ...
    def source_url(self, recording: SourceObject) -> str: ...
    def fetch(self, recording: SourceObject, first: int, last: int, target: Path) -> None: ...
    def layout(self, header: bytes, size: int) -> tuple[int,int,int]: ...
