# RF Finder

**RF Finder** is a local RF signal detection and analysis application for Windows. It is designed to run against a simulator during development and later against supported SDR hardware.

## Current Status

**Stage 1 + Voice Assistant Foundation — ready for local testing.**

Implemented:
- Synthetic IQ signal simulator
- FFT-based spectrum analysis
- Signal detection
- Local password authentication
- Process-local sessions
- Controlled assistant tool gateway
- Natural-language RF command parser
- Assistant context and routing
- Console assistant for hardware/cloud-free testing
- Automated GitHub Actions tests

The voice layer is intentionally provider-independent. The repository currently uses console input/output so it can be tested without microphone drivers, cloud credentials, or an AI API key. Microphone speech-to-text and text-to-speech providers can be added behind the existing interfaces without changing the RF engine.

## Voice Assistant

Run the assistant with:

```bash
python app/voice_bot.py
```

After authentication, try:

```text
start scan
status
stop scan
what can you do
```

The assistant uses this flow:

```text
Input
  |
  v
Command parser
  |
  v
Intent
  |
  v
Tool Registry
  |
  +---- permission check
  |
  v
RF Finder service
  |
  v
Structured result
  |
  v
Assistant response
```

The assistant cannot execute arbitrary Python, shell commands, PowerShell, filesystem operations, or unregistered tools. Every operation must be explicitly registered and permission-checked.

### Voice architecture

```text
app/assistant/
├── assistant.py     # Orchestration + speech interfaces
├── intents.py       # Intent model and command parsing
├── router.py        # Intent-to-tool routing
└── tools.py         # Controlled tool gateway and permissions

app/voice_bot.py     # Development assistant entry point
```

### Planned voice providers

The `SpeechInput` and `SpeechOutput` interfaces are provider-neutral. A future microphone/STT/TTS implementation should be added as a separate provider rather than embedded in the router or RF engine.

No API key or cloud credential is required for the current console implementation.

## Authentication

RF Finder requires local authentication before the main RF processing pipeline starts.

On first run, create an administrator account. Passwords are never stored in plaintext. The account metadata uses a random salt and PBKDF2-HMAC-SHA256 password hashing.

Session tokens are generated with Python's `secrets` module, kept only in memory, and expire after one hour. Authentication is local and is not an OAuth server or network identity provider.

Authentication files:
- `app/auth.py` — account and session management
- `tests/test_auth.py` — authentication tests
- `data/auth/users.json` — local credential metadata; ignored by Git

Security properties:
- Salted PBKDF2-HMAC-SHA256
- 600,000 password-hash iterations
- Random per-account salt
- Cryptographically random session tokens
- Constant-time password comparison
- Generic authentication errors
- Credentials excluded from Git

## Architecture

```text
RF-Finder/
├── app/
│   ├── main.py
│   ├── voice_bot.py
│   ├── auth.py
│   ├── config.py
│   ├── assistant/
│   │   ├── assistant.py
│   │   ├── intents.py
│   │   ├── router.py
│   │   └── tools.py
│   ├── sources/
│   │   └── simulator.py
│   ├── dsp/
│   │   ├── analyzer.py
│   │   └── detector.py
│   ├── visualization/
│   ├── database/
│   └── gps/
├── tests/
├── data/
├── .github/workflows/test.yml
├── requirements.txt
└── README.md
```

The architectural rule is: **AI/voice code may request approved RF Finder operations, but it does not own RF, DSP, database, GPS, authentication, or operating-system internals.**

## Installation

### Prerequisites

- Python 3.11+
- pip
- Windows is the primary target

### Setup

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

The first run creates the local administrator account. Later runs require login before RF processing begins.

## Run the Assistant

```bash
python app/voice_bot.py
```

The current assistant is a **console test harness**, not yet microphone voice input. This keeps the project deterministic and dependency-light while the RF and security layers are validated.

## Test

Run all tests locally:

```bash
python -m pytest -q
```

GitHub Actions automatically runs the test suite on pushes to `main` and pull requests against `main` using Python 3.11 and 3.12.

## Configuration

Configuration is centralized in `app/config.py`.

| Parameter | Default | Description |
|---|---:|---|
| `sample_rate` | 2 MS/s | Complex IQ sample rate |
| `center_frequency` | 100 MHz | RF center frequency |
| `fft_size` | 2048 | FFT transform size |
| `detection_threshold_db` | 6 dB | Detection threshold above noise |
| `minimum_signal_bandwidth_hz` | 10 kHz | Minimum detected bandwidth |
| `waterfall_history_frames` | 256 | Waterfall display depth |
| `database_path` | `data/database/rf_finder.db` | SQLite database location |

## Development Roadmap

### v0.3 — Voice Assistant Foundation ✓
- [x] Assistant orchestration
- [x] Intent parser
- [x] Tool registry
- [x] Permission boundary
- [x] Conversation context
- [x] Console development provider
- [x] Assistant tests
- [x] GitHub Actions CI

### v0.4 — Desktop Interface
- [ ] Live spectrum display
- [ ] Scrolling waterfall
- [ ] Signal table
- [ ] Login screen
- [ ] Assistant panel
- [ ] Push-to-talk controls

### v0.5 — RF Hardware
- [ ] SDR abstraction
- [ ] RTL-SDR source
- [ ] Device discovery/status
- [ ] Hardware error handling

### v0.6 — Data and Location
- [ ] SQLite measurement service
- [ ] CSV export
- [ ] GPS integration
- [ ] Location-tagged measurements

### v0.7 — RF Intelligence
- [ ] Signal classification
- [ ] Frequency database
- [ ] Advanced filtering
- [ ] Measurement summaries
- [ ] Voice explanations of detected signals

## Legal Notice

RF Finder is a spectrum analysis and measurement application intended for lawful use.

Do not use it for interception of private communications, decryption of encrypted signals, identification of private individuals, unauthorized RF interference, or other unlawful activity. Comply with applicable RF regulations.

## License

TBD

## References

- GNU Radio: https://www.gnuradio.org/
- RTL-SDR: https://osmocom.org/projects/rtl-sdr/wiki
- scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
- NumPy FFT: https://numpy.org/doc/stable/reference/routines.fft.html
