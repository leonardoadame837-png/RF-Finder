# RF Finder Audio Demodulation

RF Finder now includes a software-only, receive-side audio demodulation layer for signals the operator is authorized to receive.

## Current scope

- AM envelope demodulation
- FM phase-difference demodulation
- NFM and WFM dispatch modes using FM demodulation with different default audio bandwidths
- Audio resampling to a browser/player-friendly rate such as 48 kHz
- Normalized mono `float32` audio output
- Deterministic unit tests using synthetic IQ; no SDR or antenna required

## Signal path

```text
IQ source
  -> RF Studio / Spectrum Analyzer
  -> selected signal
  -> AM / NFM / WFM demodulator
  -> normalized PCM audio
  -> future audio playback endpoint/UI
```

The current commit adds the DSP layer and software validation. It does **not** yet provide continuous speaker playback from the Tactical UI.

## Software-only validation

The test suite generates synthetic AM and FM IQ samples and verifies that the demodulators produce finite, non-trivial, normalized audio. Run:

```text
pytest -q tests/test_audio_demodulator.py
```

No physical RF hardware is required for this test.

## Planned UI integration

The next integration layer can expose:

1. Select a visible spectrum peak.
2. Choose AM, NFM, or WFM.
3. Set audio bandwidth.
4. Start/stop receive-side audio.
5. Stream decoded PCM to the browser audio subsystem while the spectrum continues updating.

Digital, encrypted, proprietary, or otherwise protected communications are outside this initial demodulation scope. The feature is intended for public broadcasts, test signals, and other signals the operator is authorized to receive.
