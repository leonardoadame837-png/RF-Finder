# RF Finder

**RF Finder** is a professional RF signal detection and analysis application for Windows, designed to run locally without requiring physical SDR hardware.

## Overview

RF Finder performs passive RF spectrum monitoring and signal analysis:

- **Signal Detection**: Identifies RF signals above noise floor
- **Spectrum Analysis**: FFT-based frequency domain analysis
- **Measurements**: Records signal characteristics (frequency, power, bandwidth, SNR)
- **Visualization**: Live spectrum and waterfall displays
- **Database Storage**: Local SQLite storage of measurements
- **GPS Integration**: Future support for location tagging
- **Local Authentication**: Password-protected startup with process-local sessions

## Authentication

RF Finder now requires local authentication before the RF processing pipeline starts.

### First run

When no local account exists, RF Finder prompts for an administrator account. Passwords are **never stored in plaintext**. The account file contains a random salt and a PBKDF2-HMAC-SHA256 password hash.

### Login flow

```text
Start RF Finder
      |
      v
Check data/auth/users.json
      |
      +-- missing/empty --> create first admin account
      |
      v
Prompt for username + password
      |
      v
PBKDF2-HMAC-SHA256 verification
      |
      +-- failure --> reject login
      |
      v
Issue random session token in memory
      |
      v
Start RF Finder DSP pipeline
      |
      v
Logout / process exit -> invalidate token
```

Session tokens are generated with Python's `secrets` module, kept only in memory, and expire after one hour. They are not written to disk or included in RF measurements. The current implementation is intentionally local; it is **not** a network identity provider or OAuth server.

### Authentication components

- `app/auth.py` — account creation, password hashing/verification, session creation, token validation, and logout.
- `app/main.py` — authentication gate before RF source/DSP initialization.
- `tests/test_auth.py` — tests for successful login, failed login, plaintext-password protection, logout, and duplicate accounts.
- `data/auth/users.json` — local credential metadata. The `data/` directory is ignored by Git and must never be committed.

### Security model

- Passwords: salted PBKDF2-HMAC-SHA256 with 600,000 iterations.
- Salt: cryptographically random 16-byte value per account.
- Session token: cryptographically random value generated with `secrets`.
- Token storage: memory only.
- Token lifetime: 1 hour by default.
- Comparison: constant-time `hmac.compare_digest`.
- Authentication errors: deliberately generic to avoid revealing whether a username exists.

This local authentication layer should be replaced or extended with a dedicated identity service if RF Finder later becomes a multi-user network application.

## Target Platform

- **OS**: Windows 11 Pro
- **CPU**: Intel Core i5-8365U (4 cores / 8 threads)
- **RAM**: 8 GB
- **Storage**: 256 GB SSD
- **Python**: 3.11+

## Architecture

RF Finder uses a modular, layered architecture:

```text
RF-Finder/
├── app/
│   ├── main.py              # Authenticated application entry point
│   ├── auth.py              # Local authentication and sessions
│   ├── config.py            # Centralized configuration
│   ├── sources/             # RF signal sources (simulator, SDR)
│   ├── dsp/                 # Signal processing (FFT, detection)
│   ├── visualization/       # Display components (spectrum, waterfall)
│   ├── database/            # Measurement storage
│   └── gps/                 # Location services
├── data/                    # Local application data; ignored by Git
├── tests/                   # Unit tests
├── requirements.txt         # Python dependencies
└── README.md
```

## Development Stages

### Stage 1 ✓ Complete
- Signal simulator (synthetic IQ data)
- FFT spectrum analyzer
- Signal detector
- Command-line output
- Unit tests
- Local authentication

### Stage 2 (Future)
- Live spectrum visualization (matplotlib)
- Waterfall display
- SQLite database storage
- Configuration file support

### Stage 3 (Future)
- USB SDR support (RTL-SDR)
- Simulated GPS
- Enhanced visualization

## Installation

### Prerequisites

- Python 3.11 or higher
- pip

### Setup

```bash
git clone https://github.com/leonardoadame837-png/RF-Finder.git
cd RF-Finder
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Run Main Application

```bash
python app/main.py
```

On the first run, create the requested administrator account. On subsequent runs, sign in with that account. Only after successful authentication does RF Finder initialize its signal source and DSP pipeline.

### Run Tests

```bash
python -m pytest tests/ -v
# Or
python -m unittest discover tests/ -v
```

## Configuration

Configuration is centralized in `app/config.py`.

Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sample_rate` | 2 MS/s | Complex IQ sample rate |
| `center_frequency` | 100 MHz | RF center frequency |
| `fft_size` | 2048 | FFT transform size |
| `detection_threshold_db` | 6 dB | Signal detection threshold above noise |
| `minimum_signal_bandwidth_hz` | 10 kHz | Minimum detected signal bandwidth |
| `waterfall_history_frames` | 256 | Waterfall display depth |
| `database_path` | `data/database/rf_finder.db` | SQLite database location |

## Components

### Signal Sources (`app/sources/`)

**SignalSimulator**: Generates synthetic RF data.

**SDRSource** (Future): Real USB SDR interface; RTL-SDR support is planned.

### DSP Pipeline (`app/dsp/`)

**SpectrumAnalyzer**: FFT-based spectrum analysis, noise-floor estimation, and frequency mapping.

**SignalDetector**: Peak detection, bandwidth estimation, and SNR calculation.

## Performance Considerations

Optimized for the Lenovo ThinkPad T490 (i5-8365U, 8 GB RAM):

- FFT size: 2048 samples
- Windowing: Hamming window
- Noise floor: 20th percentile estimation
- Memory: bounded circular buffers
- Threading: single-threaded main loop

## Legal Notice

RF Finder is a **spectrum analysis and measurement application** for lawful use.

Do NOT use for:
- Interception of private communications
- Decryption of encrypted signals
- Identification of private individuals
- Unauthorized RF interference
- Any illegal activity

Use responsibly and comply with applicable RF regulations.

## Future Features

- [ ] Real-time spectrum visualization
- [ ] Scrolling waterfall display
- [ ] SQLite measurement database
- [ ] CSV export
- [ ] USB SDR support (RTL-SDR)
- [ ] GPS location tagging
- [ ] Signal classification
- [ ] Frequency database lookup
- [ ] Advanced filtering
- [ ] Multi-threaded acquisition
- [ ] Optional network authentication for multi-user deployments

## License

TBD

## References

- GNU Radio: https://www.gnuradio.org/
- RTL-SDR: https://osmocom.org/projects/rtl-sdr/wiki
- scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
- NumPy FFT: https://numpy.org/doc/stable/reference/routines.fft.html

## Contributing

Contributions welcome. Please ensure:
- Code follows existing style
- All tests pass
- New components are well-documented
- No external dependencies added without discussion
