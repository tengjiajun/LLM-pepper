"""Reusable Butterworth low-pass filters extracted from the Pepper teleoperation project.

This module isolates the joint-angle smoothing code that previously lived inside
``pepper_approach_control.py``/``pepper_approach_control_thread.py`` so it can be
re-used in other projects.  The filters rely on ``scipy.signal``'s digital
Butterworth design and expose a small stateful API that works well for
sample-by-sample real-time pipelines.

Typical usage
-------------

>>> from butterworth_lowpass import ButterworthLowpass
>>> filt = ButterworthLowpass(cutoff_hz=0.7, fs=5.3, order=1)
>>> filt.filter_sample(0.5)
0.499...

When you need to manage multiple channels (e.g. a Pepper arm with several
joints), ``ButterworthLowpassBank`` keeps a filter instance per joint:

>>> joints = ["LShoulderPitch", "LShoulderRoll"]
>>> bank = ButterworthLowpassBank(cutoff_hz=0.7, fs=5.3, channel_names=joints)
>>> bank.filter_sample({"LShoulderPitch": 0.1, "LShoulderRoll": 0.2})
{"LShoulderPitch": 0.099..., "LShoulderRoll": 0.199...}

Both classes maintain the internal ``zi`` state between calls exactly like the
original implementation, ensuring smooth continuous output even when processing
streams one sample at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

import numpy as np
from scipy import signal

__all__ = [
    "ButterworthLowpass",
    "ButterworthLowpassBank",
]


@dataclass
class ButterworthLowpass:
    """Stateful Butterworth low-pass filter that operates on scalar samples.

    Parameters
    ----------
    cutoff_hz:
        Desired cut-off frequency of the low-pass filter (Hz).
    fs:
        Sampling frequency of the input signal (Hz).
    order:
        Filter order.  The original Pepper teleoperation pipeline used ``order=1``
        for the arm joints and ``order=2`` for the hip joint.
    initial_value:
        Optional value used to initialise the filter state.  Providing the first
        sample here removes start-up transients.
    """

    cutoff_hz: float
    fs: float
    order: int = 1
    initial_value: float = 0.0
    _b: np.ndarray = field(init=False, repr=False)
    _a: np.ndarray = field(init=False, repr=False)
    _zi: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.fs <= 0:
            raise ValueError("Sampling frequency 'fs' must be positive.")
        if not 0 < self.cutoff_hz < 0.5 * self.fs:
            raise ValueError(
                "cutoff_hz must be between 0 and Nyquist frequency (fs / 2)."
            )
        if self.order < 1:
            raise ValueError("Filter order must be >= 1.")

        nyq = 0.5 * self.fs
        normal_cutoff = self.cutoff_hz / nyq
        self._b, self._a = signal.butter(
            self.order, normal_cutoff, btype="low", analog=False, output="ba"
        )

        # ``lfilter_zi`` returns steady-state initial conditions so the filter
        # output starts close to ``initial_value`` when we multiply the state by
        # that value.
        zi = signal.lfilter_zi(self._b, self._a)
        self._zi = zi * self.initial_value

    def reset(self, initial_value: float = 0.0) -> None:
        """Reset the filter state.

        Parameters
        ----------
        initial_value:
            Value to re-initialise the state with.  Passing the last observed
            sample avoids discontinuities at the reset point.
        """

        self._zi = signal.lfilter_zi(self._b, self._a) * initial_value

    def filter_sample(self, sample: float) -> float:
        """Filter a single scalar sample and update the internal state."""

        filtered, self._zi = signal.lfilter(self._b, self._a, [sample], zi=self._zi)
        return float(filtered[0])

    def filter_batch(self, samples: Sequence[float]) -> np.ndarray:
        """Filter a sequence of samples, returning the filtered signal.

        The internal state is updated as if ``filter_sample`` were called for
        each element in ``samples`` sequentially.
        """

        samples_arr = np.asarray(samples, dtype=float)
        filtered, self._zi = signal.lfilter(self._b, self._a, samples_arr, zi=self._zi)
        return filtered

    @property
    def coefficients(self) -> Dict[str, np.ndarray]:
        """Return the filter coefficients ``b`` and ``a`` for inspection."""

        return {"b": self._b.copy(), "a": self._a.copy()}


class ButterworthLowpassBank:
    """Manage a collection of ``ButterworthLowpass`` filters, one per channel."""

    def __init__(
        self,
        cutoff_hz: float,
        fs: float,
        order: int = 1,
        channel_names: Optional[Iterable[str]] = None,
        initial_values: Optional[Mapping[str, float]] = None,
    ) -> None:
        names: Iterable[str]
        if channel_names is None:
            names = []  # allow deferred registration via ``add_channel``
        else:
            names = list(channel_names)

        self._filters: Dict[str, ButterworthLowpass] = {}
        for name in names:
            init = 0.0
            if initial_values is not None and name in initial_values:
                init = initial_values[name]
            self._filters[name] = ButterworthLowpass(
                cutoff_hz=cutoff_hz, fs=fs, order=order, initial_value=init
            )

        self.cutoff_hz = cutoff_hz
        self.fs = fs
        self.order = order

    def add_channel(self, name: str, initial_value: float = 0.0) -> None:
        if name in self._filters:
            raise ValueError(f"Channel '{name}' already exists.")
        self._filters[name] = ButterworthLowpass(
            cutoff_hz=self.cutoff_hz,
            fs=self.fs,
            order=self.order,
            initial_value=initial_value,
        )

    def filter_sample(self, sample_map: Mapping[str, float]) -> Dict[str, float]:
        """Filter one sample per channel.

        Any channels present in ``sample_map`` but missing from the bank will be
        created on the fly.
        """

        outputs: Dict[str, float] = {}
        for name, value in sample_map.items():
            if name not in self._filters:
                self.add_channel(name, initial_value=value)
            outputs[name] = self._filters[name].filter_sample(value)
        return outputs

    def reset(self, initial_values: Optional[Mapping[str, float]] = None) -> None:
        for name, filt in self._filters.items():
            value = 0.0
            if initial_values is not None and name in initial_values:
                value = initial_values[name]
            filt.reset(initial_value=value)

    def coefficients(self) -> Dict[str, Dict[str, np.ndarray]]:
        """Return filter coefficients for all registered channels."""

        return {name: filt.coefficients for name, filt in self._filters.items()}


def demo() -> None:
    """Simple command-line demo showing the filter in action."""

    import math

    fs = 10.0
    cutoff = 0.7
    t = np.arange(0, 10, 1 / fs)
    signal_clean = np.sin(2 * math.pi * 0.3 * t)
    rng = np.random.default_rng(seed=42)
    noisy = signal_clean + rng.normal(scale=0.2, size=t.shape)

    filt = ButterworthLowpass(cutoff_hz=cutoff, fs=fs, order=1)
    filtered = filt.filter_batch(noisy)

    print("Demo complete. Showing first five samples (clean / noisy / filtered):")
    for i in range(5):
        print(f"{signal_clean[i]: .3f}\t{noisy[i]: .3f}\t{filtered[i]: .3f}")


if __name__ == "__main__":
    demo()
