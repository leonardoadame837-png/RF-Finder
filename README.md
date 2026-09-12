# RF Finder

**RF Finder** is a local RF signal detection and analysis application. It uses one DSP pipeline for synthetic test data, imported samples, and optional live receiver measurements.

## Spectrum Analyzer

The Spectrum Analyzer is available at `/spectrum` when the local field server is running. It provides a live frequency-vs-power spectrum, peak selection, noise-floor/SNR readouts, detection table, controls, and an IQ/sample import path.

### Source provenance

Every spectrum frame and detection carries exactly one source type:

- `SIMULATED` — generated test IQ. Never a verified environmental measurement.
- `IMPORTED_MEASUREMENT` — samples supplied by an import file. Hardware origin is not inferred.
- `LIVE_MEASUREMENT` — samples received from a configured live measurement source.
- `UNKNOWN` — provenance has not been established.

A simulated frame cannot be upgraded to a verified measurement by the UI or storage layer.

### DSP and frequency axis

Complex baseband IQ is windowed and transformed with the existing FFT analyzer. For sample rate `Fs` and center frequency `Fc`, the ordered bins run from `Fc - Fs/2` through the final FFT bin immediately below `Fc + Fs/2`; the upper Nyquist endpoint is not a distinct even-length FFT bin. Bin spacing is `Fs/N`.

Power is reported on a normalized digital full-scale (`dBFS`) basis. This is not an RF dBm calibration. A real receiver calibration would require a known reference and receiver-specific calibration data.

Noise floor is the median FFT-bin power, a robust central estimate. Detection SNR is:

`SNR = peak_power_dBFS - noise_floor_dBFS`

Detection confidence is an algorithmic score based on the measured SNR margin. It is **not** proof that a particular transmitter, person, device, activity, or legal status exists.

### Import format

The current import abstraction accepts JSON or CSV. JSON may contain:

```json
{
  "samples": [{"real": 0.1, "imag": 0.0}],
  "center_frequency_hz": 100000000,
  "sample_rate_hz": 2000000,
  "timestamp": "2026-01-01T00:00:00Z",
  "sample_format": "complex128"
}
```

CSV accepts `real,imag` (or `i,q`) columns. The current analyzer requires exactly the configured FFT frame length. Imported data is classified as `IMPORTED_MEASUREMENT` unless metadata explicitly supplies another supported source type.

## Architecture

```text
Capture / Simulation / Import
          |
          v
Sample / IQ normalization
          |
          v
Existing DSP analyzer
          |
          +--> Noise-floor estimation
          |
          v
Existing peak detector
          |
          v
Source-aware Detection model
          |
          v
Authenticated API / service state
          |
          v
Spectrum Analyzer UI
          |
          +--> Detection table
          +--> Field observation / investigation
```

The AI/voice layer can request approved RF Finder operations but does not own the RF/DSP, database, GPS, authentication, or operating-system internals.

## Authentication and RBAC

RF Finder uses local authentication with salted PBKDF2-HMAC-SHA256 password hashing and process-local session tokens. API operations remain permission checked through the existing RBAC layer. Spectrum read operations require `rf.read`; scanning/import and field-observation creation require the existing write permissions.

## Existing capabilities

- Synthetic IQ signal simulator
- FFT-based spectrum analysis
- Signal detection and characterization
- Source-aware spectrum/detection API
- IQ/sample import abstraction
- Local password authentication and RBAC
- Investigation and field-observation workflow
- Optional receive-only SDR source
- Controlled assistant tool gateway
- Automated GitHub Actions tests

## Installation

### Prerequisites

- Python 3.11+
- pip
- Windows is the primary target

```bash
git clone https://github.com/leonardoadame837-png/RF-Finder.git
cd RF-Finder
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run RF Finder

```bash
python app/main.py
```

For the field Spectrum Analyzer server:

```bash
python -m app.field
```

Then open `/spectrum` on the server port after authentication.

## Test

Run the complete suite:

```bash
python -m pytest -q
```

Tests cover FFT frequency-axis correctness, complex IQ processing, noise-floor estimation, strong/noise-only detection, multiple peaks, SNR, source labeling, invalid input, serialization, service lifecycle, and investigation persistence.

## Configuration

Configuration is centralized in `app/config.py`.

| Parameter | Default | Description |
|---|---:|---|
| `sample_rate` | 2 MS/s | Complex IQ sample rate |
| `center_frequency` | 100 MHz | RF center frequency |
| `fft_size` | 2048 | FFT transform size |
| `detection_threshold_db` | 6 dB | Configured minimum detection margin; detector retains a 15 dB practical floor |
| `minimum_signal_bandwidth_hz` | 10 kHz | Minimum detected bandwidth |
| `waterfall_history_frames` | 256 | Waterfall display depth |
| `database_path` | `data/database/rf_finder.db` | SQLite database location |
| `simulation_seed` | 12345 | Deterministic simulator seed |

## Measurement limitations

RF Finder reports measurable digital signal characteristics from the supplied sample stream. It does not by itself establish the physical identity or location of a transmitter, intent, legality, surveillance, or malicious activity. Phone/device telemetry is not an RF measurement source. Imported data retains its supplied metadata and is not automatically attributed to SDR hardware.

## Legal Notice

RF Finder is intended for lawful spectrum analysis and measurement. Do not use it for interception of private communications, unauthorized decryption, unauthorized RF interference, or other unlawful activity. Comply with applicable RF regulations.

## References

- GNU Radio: https://www.gnuradio.org/
- RTL-SDR: https://osmocom.org/projects/rtl-sdr/wiki
- scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
- NumPy FFT: https://numpy.org/doc/stable/reference/routines.fft.html
