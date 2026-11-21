"""Real-time voice changer engine (numpy only).

Pitch shifting uses a two-tap delay-line (granular) shifter, which keeps the
speech duration unchanged and is fast enough for live audio.
"""
import numpy as np

SAMPLE_RATE = 16000
BLOCK = 512  # ~32 ms per block at 16 kHz

EFFECTS = ["None", "Robot", "Alien", "Echo"]

# name: (pitch ratio, effect)
PRESETS = {
    "Normal":    (1.00, "None"),
    "Deep":      (0.75, "None"),
    "Very deep": (0.62, "None"),
    "High":      (1.30, "None"),
    "Child":     (1.55, "None"),
    "Robot":     (1.00, "Robot"),
    "Alien":     (1.20, "Alien"),
    "Cave":      (0.80, "Echo"),
}


class PitchShifter:
    def __init__(self, ratio=1.0, window=1024):
        self.ratio = ratio
        self.W = window
        self.hist = np.zeros(window * 3, dtype=np.float32)
        self.phase = 0.0

    def process(self, x):
        n = len(x)
        W = self.W
        if abs(self.ratio - 1.0) < 1e-3:
            self.hist = np.concatenate([self.hist, x])[-len(self.hist):]
            return x
        buf = np.concatenate([self.hist, x]).astype(np.float32)
        base = len(self.hist)
        idx = np.arange(n)
        step = 1.0 - self.ratio  # delay sweeps linearly, wraps every W samples
        ph = (self.phase + idx * step) % W
        out = np.zeros(n, dtype=np.float32)
        for offs in (0.0, W / 2.0):
            d = (ph + offs) % W
            gain = 0.5 - 0.5 * np.cos(2 * np.pi * d / W)  # Hann crossfade
            pos = base + idx - d - 1
            i0 = np.floor(pos).astype(np.int64)
            frac = (pos - i0).astype(np.float32)
            i0 = np.clip(i0, 0, len(buf) - 2)
            s = buf[i0] * (1 - frac) + buf[i0 + 1] * frac
            out += gain.astype(np.float32) * s
        self.phase = (self.phase + n * step) % W
        self.hist = buf[-len(self.hist):]
        return out


class VoiceChanger:
    def __init__(self, preset="Normal", sr=SAMPLE_RATE):
        self.sr = sr
        self.t = 0
        self.gain = 1.0
        self.level = 0.0  # last output level 0..1 (for the dashboard meter)
        self.echo_buf = np.zeros(int(0.25 * sr), dtype=np.float32)
        self.shifter = PitchShifter(1.0)
        self.fx = "None"
        self.set_preset(preset)

    def set_preset(self, name):
        ratio, fx = PRESETS[name]
        self.set_ratio(ratio)
        self.set_fx(fx)

    def set_ratio(self, ratio):
        self.shifter.ratio = float(ratio)

    def set_fx(self, fx):
        self.fx = fx

    def process(self, pcm16):
        """int16 numpy array in -> int16 numpy array out."""
        x = pcm16.astype(np.float32) / 32768.0
        y = self.shifter.process(x)
        n = len(y)
        if self.fx in ("Robot", "Alien"):
            f = 50.0 if self.fx == "Robot" else 30.0
            tt = (self.t + np.arange(n)) / self.sr
            y = y * (0.4 + 0.6 * np.sin(2 * np.pi * f * tt)).astype(np.float32)
        elif self.fx == "Echo":
            y = y + 0.4 * self.echo_buf[:n]
            self.echo_buf = np.concatenate([self.echo_buf[n:], y])
        self.t += n
        y = np.clip(y * self.gain, -1.0, 1.0)
        self.level = float(np.sqrt(np.mean(y * y))) if n else 0.0
        return (y * 32767).astype(np.int16)
