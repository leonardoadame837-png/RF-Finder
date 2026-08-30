"""GPS abstraction with a safe no-hardware default."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    latitude: float | None = None
    longitude: float | None = None
    altitude_m: float | None = None
    accuracy_m: float | None = None


class GpsProvider:
    def current_location(self) -> Location:
        return Location()
