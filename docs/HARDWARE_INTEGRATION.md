# RF Finder hardware integration test procedure

This procedure is intentionally separate from the software-only validation suite. It is for the first test with a physical RTL-SDR receiver and a local `rtl_tcp` server.

## 1. Prerequisites

- Windows, Linux, or macOS development machine with RF Finder installed.
- RTL-SDR-compatible USB receiver and a suitable antenna.
- A supported `rtl_tcp` server installation for the receiver.
- RF Finder dependencies installed and the normal test suite passing.

**Safety:** RF Finder's SDR integration is receive-only. Do not connect RF Finder to equipment configured to transmit. Follow local radio regulations and the receiver manufacturer's instructions.

## 2. Validate the receiver outside RF Finder

1. Connect the RTL-SDR to the development machine.
2. Confirm the operating system detects the USB device.
3. Start the `rtl_tcp` server and note its listening address and port. The RF Finder default is `127.0.0.1:1234`.
4. Confirm the server reports an RTL0-compatible handshake and remains running while a client connects.

Do not continue until the receiver and `rtl_tcp` server work independently.

## 3. Configure RF Finder

Use the network source configuration:

```text
source = network_sdr
network_sdr_host = 127.0.0.1
network_sdr_port = 1234
network_sdr_timeout_s = 5
center_frequency = <test frequency in Hz>
sample_rate = <supported sample rate in samples/s>
fft_size = <test FFT size>
```

The default network endpoint is local-only. Change the host only when the `rtl_tcp` server is intentionally running on another machine you control.

## 4. Run the automated preflight

From the repository root:

```powershell
pytest -q
```

The software-only suite must pass before hardware testing. In particular, `tests/test_software_validation.py` verifies:

- simulator → DSP → detector → SQLite flow;
- Tactical UI and spectrum API reachability;
- rtl_tcp handshake/IQ framing without physical hardware; and
- propagation of runtime center-frequency/sample-rate metadata.

## 5. Start RF Finder

Start the tactical service using the project's normal local command. Select `network_sdr` through the configuration rather than modifying the DSP code.

Open the Tactical UI and verify:

- the source is reported as `network_sdr` / `rtl_tcp`;
- the source is classified as a live measurement;
- center frequency and sample rate match the active receiver settings;
- spectrum bins are populated;
- waterfall frames accumulate;
- detections, when present, are persisted; and
- no unexpected error appears in the service status.

## 6. Retune test

Change the active center frequency through the supported source control path. Verify that the receiver acknowledges the command and that RF Finder's status, latest spectrum, and waterfall metadata report the new center frequency.

Repeat for sample rate when the active source exposes sample-rate control.

The important acceptance criterion is that runtime metadata describes the capture that produced the displayed data, rather than continuing to report stale startup configuration values.

## 7. Stop/cleanup

1. Stop RF Finder cleanly.
2. Stop `rtl_tcp`.
3. Disconnect the receiver.
4. Confirm no RF source process remains unexpectedly active.

## 8. Evidence to record

For the first hardware test, record:

- OS and RF Finder commit SHA;
- RTL-SDR model and driver version;
- `rtl_tcp` version/build;
- host and port used;
- center frequency and sample rate;
- FFT size;
- observed spectrum/waterfall behavior;
- whether detections were persisted; and
- any errors from RF Finder or `rtl_tcp`.

Do not commit credentials, private network addresses, or unrelated personal data to the repository.

## Scope boundary

The first hardware milestone covers **RTL-SDR → rtl_tcp → RF Finder** only. SDR++ Server and SpyServer adapters are intentionally deferred until this path has been validated with real hardware. This keeps each capture backend independently testable and prevents multiple network protocols from being introduced before the base receive path is proven.
