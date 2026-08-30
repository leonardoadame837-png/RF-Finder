"""Intent definitions and lightweight command parsing for RF Finder."""

from dataclasses import dataclass
from enum import Enum
import re


class Intent(str, Enum):
    START_SCAN = "start_scan"
    STOP_SCAN = "stop_scan"
    GET_STATUS = "get_status"
    GET_SIGNALS = "get_signals"
    GET_STRONGEST_SIGNAL = "get_strongest_signal"
    SET_FREQUENCY = "set_frequency"
    SAVE_MEASUREMENT = "save_measurement"
    GET_LOCATION = "get_location"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ParsedIntent:
    intent: Intent
    arguments: dict


def _frequency_hz(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(ghz|mhz|khz|hz)", text.lower())
    if not match:
        return None
    value = float(match.group(1))
    multiplier = {"ghz": 1e9, "mhz": 1e6, "khz": 1e3, "hz": 1}[match.group(2)]
    return value * multiplier


def parse_command(text: str) -> ParsedIntent:
    """Parse common RF Finder voice commands without executing anything."""
    normalized = " ".join(text.lower().strip().split())
    if not normalized:
        return ParsedIntent(Intent.UNKNOWN, {})
    if any(p in normalized for p in ("start scan", "start scanning", "begin scan", "scan now")):
        return ParsedIntent(Intent.START_SCAN, {})
    if any(p in normalized for p in ("stop scan", "stop scanning", "end scan")):
        return ParsedIntent(Intent.STOP_SCAN, {})
    if "strongest" in normalized and "signal" in normalized:
        return ParsedIntent(Intent.GET_STRONGEST_SIGNAL, {})
    if any(p in normalized for p in ("what signals", "show signals", "list signals", "detected signals")):
        return ParsedIntent(Intent.GET_SIGNALS, {})
    if any(p in normalized for p in ("status", "are we scanning", "is it scanning")):
        return ParsedIntent(Intent.GET_STATUS, {})
    if "save" in normalized and "measurement" in normalized:
        return ParsedIntent(Intent.SAVE_MEASUREMENT, {})
    if any(p in normalized for p in ("where am i", "my location", "gps location")):
        return ParsedIntent(Intent.GET_LOCATION, {})
    if any(p in normalized for p in ("help", "what can you do", "commands")):
        return ParsedIntent(Intent.HELP, {})
    if "frequency" in normalized or "center freq" in normalized:
        frequency = _frequency_hz(normalized)
        if frequency is not None:
            return ParsedIntent(Intent.SET_FREQUENCY, {"frequency_hz": frequency})
    return ParsedIntent(Intent.UNKNOWN, {})
