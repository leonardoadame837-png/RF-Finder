"""SoapySDR source adapter for RF-Finder.

This adapter is optional and depends on SoapySDR (https://github.com/pothosware/SoapySDR).
It provides a device-backed source with the same interface as the existing
SignalSimulator: start(), stop(), status(), and read_frame() returning a
numpy complex64 array sized to config.fft_size.

Notes for Windows users:
- RTL-SDR devices require a WinUSB-compatible driver. Use Zadig to install
  the WinUSB driver for your RTL2832U device before using SoapySDR/pyrtlsdr.
- SoapySDR Python bindings and the underlying drivers/libraries must be
  installed on the system. The adapter imports SoapySDR lazily so the
  repository remains usable in CI or developer environments without the
  hardware dependency.
"""

from typing import Optional
import numpy as np

try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_RX
except Exception as e:
    SoapySDR = None  # type: ignore


class SoapySDRSource:
    """Adapter that reads complex IQ frames from a SoapySDR-supported device.

    The adapter sets sample rate, center frequency, and returns frames of
    size config.fft_size as numpy.complex64 arrays.
    """

    def __init__(self, config):
        self.config = config
        self.device = None
        self.stream = None
        self.frame_index = 0
        self.running = False
        self.error: Optional[str] = None

    def _check_dependency(self):
        if SoapySDR is None:
            raise RuntimeError("SoapySDR Python bindings are not installed")

    def start(self):
        """Open the first available device and configure RX parameters."""
        self._check_dependency()
        try:
            # Open default device (empty args). Users can modify this adapter to
            # pass specific args via config if desired.
            self.device = SoapySDR.Device({})

            # Configure sample rate, center frequency, and gain
            sr = int(self.config.sample_rate)
            cf = int(self.config.center_frequency)

            self.device.setSampleRate(SOAPY_SDR_RX, 0, float(sr))
            try:
                # some devices accept integer Hz, others require float
                self.device.setFrequency(SOAPY_SDR_RX, 0, float(cf))
            except Exception:
                # try alternative setFrequency with dict
                self.device.setFrequency(SOAPY_SDR_RX, 0, {'center': float(cf)})

            # Try to enable automatic gain if available, otherwise use a middle value
            try:
                self.device.setGainMode(SOAPY_SDR_RX, 0, True)
            except Exception:
                try:
                    # set a reasonable default gain if manual control is required
                    self.device.setGain(SOAPY_SDR_RX, 0, 20.0)
                except Exception:
                    # ignore if gain isn't supported
                    pass

            # Setup an RX stream for complex floats (CF32 / complex64)
            self.stream = self.device.setupStream(SOAPY_SDR_RX, "CF32")
            self.device.activateStream(self.stream)

            self.running = True
            self.frame_index = 0
            self.error = None
        except Exception as exc:
            self.error = str(exc)
            # Clean up partially initialized resources
            try:
                if self.stream is not None and self.device is not None:
                    self.device.deactivateStream(self.stream)
                    self.device.closeStream(self.stream)
            except Exception:
                pass
            self.stream = None
            self.device = None
            self.running = False
            raise

    def stop(self):
        """Deactivate stream and close device."""
        if self.device is None:
            self.running = False
            return
        try:
            if self.stream is not None:
                self.device.deactivateStream(self.stream)
                self.device.closeStream(self.stream)
        except Exception:
            pass
        self.stream = None
        self.device = None
        self.running = False

    def status(self) -> dict:
        """Return status information for UI/assistant."""
        return {
            "active": self.running,
            "source": "soapy_sdr",
            "frame_index": self.frame_index,
            "device": None if self.device is None else self.device.getHardwareKey(),
            "error": self.error,
        }

    def read_frame(self) -> np.ndarray:
        """Read one frame of IQ data and return a numpy.complex64 array sized
        to config.fft_size.

        Raises RuntimeError if the stream is not active or an error occurs.
        """
        if not self.running or self.device is None or self.stream is None:
            raise RuntimeError("SDR source is not started")

        n = int(self.config.fft_size)
        # allocate buffer for CF32 (complex floats). SoapySDR expects a list of
        # buffers for each channel
        buf = np.empty(n, dtype=np.complex64)
        try:
            # readStream returns (rc, flags, timeNs)
            rc = self.device.readStream(self.stream, [buf], n, timeoutUs=int(1e6))
            # rc may be a tuple or integer depending on binding; normalize
            if isinstance(rc, tuple) or isinstance(rc, list):
                ret = int(rc[0])
            else:
                ret = int(rc)

            if ret < 0:
                raise RuntimeError(f"SoapySDR readStream error: {ret}")

            if ret != n:
                # zero-pad or trim as needed
                if ret == 0:
                    raise RuntimeError("No samples read from SDR (device may be busy)")
                buf = buf[:ret]

            self.frame_index += 1
            # Ensure dtype complex64 and return exactly config.fft_size by padding if needed
            if buf.dtype != np.complex64:
                buf = buf.astype(np.complex64)

            if buf.shape[0] < n:
                padded = np.zeros(n, dtype=np.complex64)
                padded[: buf.shape[0]] = buf
                return padded
            return buf
        except Exception as exc:
            self.error = str(exc)
            raise
