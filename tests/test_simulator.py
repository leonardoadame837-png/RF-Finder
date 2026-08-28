"""Unit tests for the signal simulator."""

import pytest
import numpy as np
from app.config import Config
from app.sources.simulator import SignalSimulator


class TestSignalSimulator:
    """Test suite for SignalSimulator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(fft_size=2048, sample_rate=2_000_000)
        self.simulator = SignalSimulator(self.config)
    
    def test_initialization(self):
        """Test simulator initializes correctly."""
        assert self.simulator.frame_index == 0
        assert len(self.simulator.signals) == 0
    
    def test_add_signal(self):
        """Test adding signals to simulator."""
        self.simulator.add_signal(10_000_000, -20.0)
        assert len(self.simulator.signals) == 1
        assert self.simulator.signals[0].frequency_offset_hz == 10_000_000
        assert self.simulator.signals[0].power_dbm == -20.0
    
    def test_start(self):
        """Test simulator start adds default signals."""
        self.simulator.start()
        assert len(self.simulator.signals) == 3  # Default 3 signals
        assert self.simulator.frame_index == 0
    
    def test_generate_frame_shape(self):
        """Test generated frame has correct shape."""
        self.simulator.start()
        frame = self.simulator.generate_frame()
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (self.config.fft_size,)
        assert np.iscomplexobj(frame)
    
    def test_generate_frame_increments_index(self):
        """Test frame generation increments frame counter."""
        self.simulator.start()
        assert self.simulator.frame_index == 0
        self.simulator.generate_frame()
        assert self.simulator.frame_index == 1
        self.simulator.generate_frame()
        assert self.simulator.frame_index == 2
    
    def test_stop(self):
        """Test simulator stop resets frame index."""
        self.simulator.start()
        self.simulator.generate_frame()
        assert self.simulator.frame_index == 1
        self.simulator.stop()
        assert self.simulator.frame_index == 0
    
    def test_dbm_to_linear_conversion(self):
        """Test dBm to linear power conversion."""
        # 0 dBm = 1 mW
        assert abs(SignalSimulator._dbm_to_linear(0) - 0.001) < 1e-6
        # -30 dBm = 1 µW
        assert abs(SignalSimulator._dbm_to_linear(-30) - 1e-6) < 1e-9
    
    def test_deterministic_output(self):
        """Test that simulator produces deterministic output with seed."""
        np.random.seed(42)
        self.simulator.start()
        frame1 = self.simulator.generate_frame()
        
        np.random.seed(42)
        self.simulator.start()
        frame2 = self.simulator.generate_frame()
        
        np.testing.assert_array_almost_equal(frame1, frame2)
