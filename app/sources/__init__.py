"""Signal source factory for RF-Finder.

This module provides create_source(config) which returns a signal source
implementation matching config.source. Supported values:
- "simulator" (default) -> SignalSimulator
- "soapy" or "sdr" -> SoapySDRSource (if available); falls back to
  SignalSimulator if the adapter import/initialization fails.
"""

from typing import Any
import logging

from .simulator import SignalSimulator

logger = logging.getLogger(__name__)

__all__ = ["create_source"]


def create_source(config: Any):
    """Create and return a source matching config.source.

    The function performs a lazy import of the SoapySDR adapter so environments
    without hardware bindings continue to work (e.g. CI).
    """
    source_name = getattr(config, "source", "simulator")
    if source_name in ("soapy", "sdr"):
        try:
            # Lazy import to avoid hard dependency in environments without SoapySDR
            from .soapy_sdr import SoapySDRSource  # type: ignore
            return SoapySDRSource(config)
        except Exception as exc:
            # On any import/initialization error, log and fall back to simulator
            logger.warning("SoapySDR adapter not available, falling back to simulator: %s", exc)
            sim = SignalSimulator(config)
            # expose the cause for UI/debugging if desired
            setattr(sim, "_adapter_error", str(exc))
            return sim

    # Default to simulator
    return SignalSimulator(config)
