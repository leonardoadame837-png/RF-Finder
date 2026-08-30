"""Common interface for RF sample sources."""
from abc import ABC, abstractmethod
import numpy as np


class SampleSource(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def generate_frame(self) -> np.ndarray: ...

    @abstractmethod
    def device_info(self) -> dict: ...
