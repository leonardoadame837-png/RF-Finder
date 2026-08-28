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

## Target Platform

- **OS**: Windows 11 Pro
- **CPU**: Intel Core i5-8365U (4 cores / 8 threads)
- **RAM**: 8 GB
- **Storage**: 256 GB SSD
- **Python**: 3.11+

## Architecture

RF Finder uses a modular, layered architecture:

```
RF-Finder/
├── app/
│   ├── main.py              # Application entry point
│   ├── config.py            # Centralized configuration
│   ├── sources/             # RF signal sources (simulator, SDR)
│   ├── dsp/                 # Signal processing (FFT, detection)
│   ├── visualization/       # Display components (spectrum, waterfall)
│   ├── database/            # Measurement storage
│   └── gps/                 # Location services
├── data/                    # Application data (DB, captures)
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
# Clone repository
git clone https://github.com/leonardoadame837-png/RF-Finder.git
cd RF-Finder

# Create virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Run Main Application

```bash
python app/main.py
```

This will:
1. Initialize the signal simulator
2. Generate synthetic RF signals
3. Perform FFT analysis
4. Detect signals above noise floor
5. Display results to console

Expected output:

```
======================================================================
RF FINDER — Stage 1: Software-only Prototype
======================================================================
Configuration:
  Source: simulator
  Sample Rate: 2.0 MS/s
  Center Frequency: 100.0 MHz
  FFT Size: 2048
  Detection Threshold: 6.0 dB above noise

Initializing signal source...
Signal source initialized.
  Simulated signals:
    • 10 MHz above center @ -20 dBm
    • 25 MHz below center @ -25 dBm
    • 5 MHz above center @ -30 dBm

Initializing DSP pipeline...
DSP pipeline ready.
  Frequency resolution: 1000.0 kHz

Processing 5 RF frames...
----------------------------------------------------------------------
Frame 1:
  Noise Floor: -80.0 dB
  Detected Signals: 3
    [1] 110.00 MHz | Power: -20.0 dB | SNR: 60.0 dB | BW: 48.8 kHz
    [2] 75.00 MHz | Power: -25.0 dB | SNR: 55.0 dB | BW: 48.8 kHz
    [3] 105.00 MHz | Power: -30.0 dB | SNR: 50.0 dB | BW: 48.8 kHz
...
```

### Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Or use unittest
python -m unittest discover tests/
```

## Configuration

Configuration is centralized in `app/config.py`:

```python
from app.config import default_config

# Access or modify settings
print(default_config.sample_rate)        # 2,000,000 Hz
print(default_config.center_frequency)   # 100,000,000 Hz
print(default_config.fft_size)           # 2048
print(default_config.detection_threshold_db)  # 6.0 dB
```

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

**SignalSimulator**: Generates synthetic RF data
- Configurable noise floor
- Multiple simultaneous signals
- Adjustable frequency and power
- Deterministic output for testing

**SDRSource** (Future): Real USB SDR interface
- RTL-SDR support planned
- Graceful fallback to simulator

### DSP Pipeline (`app/dsp/`)

**SpectrumAnalyzer**: FFT-based spectrum analysis
- Windowed FFT
- Power spectrum calculation
- Noise floor estimation
- Frequency bin mapping

**SignalDetector**: Peak detection and characterization
- Threshold-based detection above noise floor
- Peak identification
- Bandwidth estimation
- SNR calculation

### Data Structures

**Detection**: Signal detection record
- Timestamp
- Center frequency
- Peak power (dB)
- Noise floor (dB)
- Signal-to-noise ratio (dB)
- Estimated bandwidth
- Peak magnitude

## Testing

Unit test coverage includes:

- **Simulator**: Shape validation, signal generation, start/stop
- **FFT Analyzer**: Frequency resolution, dynamic range, noise floor estimation
- **Detector**: Peak detection, noise rejection, signal characterization

Run tests:

```bash
python -m unittest discover tests/ -v
```

## Performance Considerations

Optimized for the Lenovo ThinkPad T490 (i5-8365U, 8 GB RAM):

- FFT size: 2048 samples (~1 ms latency at 2 MS/s)
- Windowing: Hamming window (good sidelobe performance)
- Noise floor: 20th percentile estimation (robust to signals)
- Memory: Bounded circular buffers (no unlimited growth)
- Threading: Single-threaded main loop (no GIL contention)

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
