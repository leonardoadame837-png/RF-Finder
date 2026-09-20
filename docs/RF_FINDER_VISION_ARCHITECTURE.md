# RF Finder Vision: Live RF Capture + Camera/Audio Correlation

## Purpose

RF Finder Vision adds a camera-and-audio workspace that correlates authorized RF measurements with time-aligned video and audio observations. It extends the existing RF Finder application; it is not a separate product.

**A camera does not measure radio frequency.** RF frequency, power, bandwidth, noise-floor, and SNR values must come from the existing RF analyzer using an authorized capture source or an imported measurement. Camera video/audio are independent evidence streams and must never be presented as proof of RF causation, transmitter identity, or transmitter location.

## Existing RF Finder integration points

- Spectrum API: authenticated `/api/spectrum` field-service endpoint.
- Browser spectrum workspace: `docs/spectrum.html`.
- Source provenance: `SIMULATED`, `IMPORTED_MEASUREMENT`, `LIVE_MEASUREMENT`, or `UNKNOWN`.
- Existing detection contract includes `frequency_hz`, `power_dbfs`, `bandwidth_hz`, `noise_floor_dbfs`, `snr_db`, `confidence`, `source_type`, and `timestamp`.
- Investigation storage and authorization remain the system of record. Preserve existing `rf.read`, `rf.scan`, and `investigation.write` boundaries; do not add anonymous access.

## Proposed data flow

```text
Authorized RF capture source / IQ import
                  |
                  v
      Existing IQ normalization + FFT
                  |
                  v
       Source-aware RF detections --------------------+
                                                      |
IP camera (RTSP/ONVIF) -> server-side stream adapter  |
                  |                                   |
                  +-> video/audio observations -------+--> timestamp correlation
                                                      |        |
                                                      +--------v
                                                Camera & Audio UI
                                                      |
                                                      v
                                           Investigation evidence store
```

## Components

### 1. Camera source registry

Store a camera ID, analyst-defined display name, connection state, audio availability, optional installation location, and server-side secret reference. Never return RTSP credentials to the browser or write them to logs. Support configuration without committing credentials to the repository.

### 2. Camera stream adapter

Accept an explicitly configured, authorized RTSP/ONVIF-compatible source. Browsers generally cannot play RTSP directly, so the backend must broker the stream into a browser-compatible transport (for example, WebRTC or HLS) supported by the deployment. Do not expose a raw RTSP URL or camera password in page JavaScript. GitHub Pages alone cannot host this backend or safely broker private camera streams.

### 3. Audio analysis

When the camera exposes an accessible audio track and the operator enables it, derive timestamped audio observations such as relative sound level, dominant audible tones, and coarse anomaly indicators. Label the units and analysis method. Audio observations are not RF detections and should not imply that a sound was caused by an RF signal. Avoid storing continuous audio by default; make evidence capture explicit and access-controlled.

### 4. RF capture integration

Reuse the current source-aware analyzer and detection contract. A live RF source must explicitly identify its provenance as `LIVE_MEASUREMENT`; imported captures remain `IMPORTED_MEASUREMENT`. The application must not promote `SIMULATED` or `UNKNOWN` data to measured status. Retain capture metadata, timestamps, and calibration/reference information when supplied. Do not label relative dBFS-like values as calibrated dBm without a calibrated measurement chain.

### 5. Correlation and event model

Correlate events by timestamp within a configurable time window, retaining each stream's original timestamp, source ID, and provenance. A correlation means events occurred near one another in time; it is not causal attribution. Camera motion, audio events, and RF detections remain separate event types.

Suggested normalized event fields:

- `event_id`
- `event_type` (`RF_DETECTION`, `AUDIO_EVENT`, `MOTION_EVENT`, `VIDEO_SNAPSHOT`)
- `source_id`
- `source_type` / provenance
- `timestamp`
- `payload` (type-specific, validated fields)
- `correlation_group_id` (optional)
- `evidence_refs` (optional)

### 6. Camera & Audio workspace

Provide:

- Camera connection and audio-availability status
- Live video panel when a compatible backend stream is available
- RF spectrum/waterfall using actual API frames, with clear `SIMULATED` vs measured labeling
- Audio waveform/spectrum and sound-level readouts when audio is available
- Unified RF/audio/video event timeline
- Snapshot/event attachment to investigations
- Clear empty, disconnected, unauthorized, and unsupported-stream states

The UI must not fabricate live camera footage, audio events, or RF detections. Any demo content must be visibly marked `SIMULATED`.

## Security, privacy, and operational requirements

- Require authenticated access and existing RBAC checks for RF reads, capture controls, and investigation writes.
- Keep camera credentials and stream URLs server-side; redact secrets from logs and error messages.
- Do not allow arbitrary user-supplied stream URLs to become an unrestricted server-side fetch/SSRF path. Validate configured camera hosts and restrict destinations/protocols.
- Use authorized cameras and respect applicable privacy/recording requirements. Make audio capture opt-in and evidence retention explicit.
- Do not expose private camera feeds through a public GitHub Pages deployment. Use GitHub Pages only for static, non-secret UI assets; the authenticated backend must broker private data.
- Preserve the receive-only, lawful-measurement scope of RF Finder.

## Delivery phases

1. **Contract and UI foundation:** event schema, camera configuration contract, provenance rules, Camera & Audio workspace shell, and tests for correlation/provenance.
2. **Camera adapter:** connect one confirmed camera model/stream format through a backend broker; validate video and audio availability.
3. **Real RF source adapter:** connect a confirmed authorized measurement source or validate IQ import; ensure source-aware measurements reach the existing analyzer.
4. **Evidence correlation:** timestamp alignment, event timeline, snapshots/audio evidence where explicitly enabled, and investigation attachment.
5. **Hardening:** authorization, secret redaction, stream failure handling, retention controls, and end-to-end tests.

## Required deployment inputs before hardware-specific implementation

- IP camera make/model and whether RTSP/ONVIF and an audio track are enabled.
- RF measurement source/model, or the intended IQ capture file format and metadata.
- Whether the first deployment is local Windows/PyCharm or a separately hosted backend.

These inputs determine the supported stream adapter and prevent claiming a camera or RF device is connected before it has been tested.
