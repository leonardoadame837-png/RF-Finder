"""Grounded Spectrum Analyst for RF Finder.

The agent consumes RF-Finder measurements; it never invents RF measurements.
A deterministic analyst is provided by default so the feature works without an
LLM API key.  An LLM adapter can later consume the same ``agent_context`` and
must return interpretations tied to the supplied evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentFinding:
    """A grounded statement produced from measured spectrum data."""

    category: str
    statement: str
    confidence: float
    evidence: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "statement": self.statement,
            "confidence": round(float(self.confidence), 3),
            "evidence": list(self.evidence),
        }


class SpectrumAgentProvider(Protocol):
    """Optional LLM boundary for future OpenAI/Gemini/local providers."""

    def analyze(self, context: dict[str, Any]) -> dict[str, Any]: ...


class LocalSpectrumAnalyst:
    """Evidence-first analyst that requires no external AI service."""

    name = "local-spectrum-analyst"
    version = "1.0"

    def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        provenance = context.get("provenance") or {}
        observations = context.get("observations") or []
        noise = context.get("noise_floor_db")
        findings: list[AgentFinding] = []

        if provenance.get("simulated"):
            findings.append(AgentFinding(
                "data-integrity",
                "This spectrum is simulated and must not be presented as a verified RF measurement.",
                1.0,
                ["provenance.simulated=true"],
            ))
        elif provenance.get("verified_rf"):
            findings.append(AgentFinding(
                "data-integrity",
                "This spectrum comes from the configured SDR capture source.",
                1.0,
                ["provenance.verified_rf=true"],
            ))

        count = len(observations)
        findings.append(AgentFinding(
            "activity",
            f"{count} detected signal observation(s) are available in the current analysis window.",
            0.98,
            [f"observations.count={count}"],
        ))

        strongest = max(observations, key=lambda x: float(x.get("snr_db", float("-inf"))), default=None)
        if strongest:
            snr = float(strongest.get("snr_db", 0.0))
            freq = float(strongest.get("frequency_hz", 0.0))
            bandwidth = float(strongest.get("bandwidth_hz", 0.0))
            findings.append(AgentFinding(
                "strongest-signal",
                f"The strongest detected observation is near {freq / 1e6:.6f} MHz with {snr:.1f} dB SNR and approximately {bandwidth / 1000:.1f} kHz bandwidth.",
                0.95,
                [f"frequency_hz={freq}", f"snr_db={snr}", f"bandwidth_hz={bandwidth}"],
            ))

        if noise is not None:
            findings.append(AgentFinding(
                "noise-floor",
                f"The estimated noise floor for this scan is {float(noise):.1f} dB.",
                0.95,
                [f"noise_floor_db={float(noise)}"],
            ))

        return {
            "agent": self.name,
            "version": self.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self._summary(provenance, observations, noise),
            "findings": [f.as_dict() for f in findings],
            "limitations": [
                "RF measurements come from the capture source and DSP pipeline; the agent does not measure RF itself.",
                "A spectrum view alone does not identify a transmitter, person, or communication content.",
                "Signal classification is an interpretation and should remain confidence-scored and evidence-linked.",
            ],
        }

    @staticmethod
    def _summary(provenance: dict[str, Any], observations: list[dict[str, Any]], noise: Any) -> str:
        mode = "simulated" if provenance.get("simulated") else "live SDR" if provenance.get("verified_rf") else "unknown source"
        summary = f"Spectrum analysis is based on {mode} data with {len(observations)} detected observation(s)."
        if noise is not None:
            summary += f" Estimated noise floor: {float(noise):.1f} dB."
        return summary


def build_agent_context(spectrum: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the only context an external LLM adapter should receive."""
    return {
        "provenance": spectrum.get("provenance", {}),
        "timestamp": spectrum.get("timestamp"),
        "center_frequency_hz": spectrum.get("center_frequency_hz"),
        "sample_rate_hz": spectrum.get("sample_rate_hz"),
        "noise_floor_db": spectrum.get("noise_floor_db"),
        "observations": observations,
        "instruction": (
            "Explain only the supplied measurements. Never invent frequencies, power, "
            "bandwidth, identities, locations, or communication content. Clearly label uncertainty."
        ),
    }
