# RF-Finder RF Evidence + Mapping Architecture

## Purpose

RF-Finder records passive RF observations together with receiver GPS telemetry so an operator can review repeated measurements on a map and prepare a neutral evidence package for an appropriate authority.

RF-Finder must never infer that a signal is illegal solely from frequency, signal strength, or AI classification. The product uses terms such as **unusual RF activity**, **potential interference**, and **investigation candidate** until an authorized authority makes a legal determination.

## Data flow

```text
Receive-only SDR
      |
      v
IQ samples
      |
      v
RF-Finder DSP / FFT / detector
      |
      +---- frequency, bandwidth, power, noise floor, SNR
      |
      v
RFObservation + provenance
      ^
      |
phone/laptop GPS + telemetry
      |
      v
SQLite observation store
      |
      +---- Live spectrum
      +---- Waterfall
      +---- Evidence map
      +---- Investigation records
      +---- AI Spectrum Agent (interpretation only)
```

## Observation integrity

Every observation retains:

- UTC timestamp
- frequency and bandwidth
- peak power and noise floor
- SNR
- receiver latitude/longitude/altitude when available
- capture source (`sdr` or `simulator`)
- simulation flag
- classification and confidence
- evidence/provenance string

Simulation observations are displayed separately and can never be represented as verified RF measurements.

## Map semantics

A map marker represents the **receiver measurement position**. It does not prove that the RF transmitter is physically at that coordinate.

Future localization can use multiple passive observations from different receiver positions to estimate a probable source area. Any source-location estimate must be displayed as an uncertainty area, not as an exact address unless independently verified.

## Priority model

The UI may visually prioritize observations using measurable characteristics such as repeated detections and SNR. Priority is an operational review aid, not a legal classification.

Recommended states:

- Normal observation
- Unusual RF activity
- Persistent interference candidate
- High-priority investigation candidate

## Authority workflow

1. Collect passive measurements.
2. Verify the capture source is an SDR and not simulation.
3. Review GPS accuracy and observation timestamps.
4. Correlate repeated measurements.
5. Open an investigation record.
6. Generate a neutral evidence report containing measurements, map coordinates, uncertainty, and methodology.
7. Human operator decides whether an appropriate authority should be contacted.

The system must not automatically contact law enforcement or make an unsupported claim that a person or property is committing an offense.

## AI Spectrum Agent boundary

The AI agent receives structured measurements only. It may summarize patterns, persistence, anomalies, and measurement limitations. It must not invent frequencies, locations, transmitter identities, or legal conclusions. The DSP and capture-source layer remain the source of truth for RF measurements.
