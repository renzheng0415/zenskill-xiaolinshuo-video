#!/usr/bin/env python3
"""程序合成音效 + 占位配乐（纯代码生成，无第三方版权）。音效算法沿用 digital-human-koubo/make_assets.py。
用法：
  python scripts/make_audio_assets.py sfx <输出目录>                      # install.sh 生成到 assets/sfx/
  python scripts/make_audio_assets.py music <out.wav> [--seconds 60] [--bpm 112]   # 占位音乐床（selftest/草稿用）
正式片的音乐请从可商用曲库挑 2–3 首候选给用户选（见 SKILL.md「音乐」）。
"""
import argparse
import wave
from pathlib import Path

import numpy as np

SR = 48000
rng = np.random.default_rng(42)
t_ = lambda d: np.arange(int(SR * d)) / SR


def env(n, a=0.002, r=0.1):
    x = np.arange(n) / SR
    return np.minimum(1, x / max(a, 1e-4)) * np.exp(-x / max(r, 1e-4))


def bp_noise(d, lo, hi):
    n = int(SR * d); X = np.fft.rfft(rng.standard_normal(n)); f = np.fft.rfftfreq(n, 1 / SR)
    X[(f < lo) | (f > hi)] = 0; y = np.fft.irfft(X, n); return y / (np.abs(y).max() + 1e-9)


def sweep_noise(d, f0, f1):
    n = int(SR * d); out = np.zeros(n); seg = 2048
    for i in range(0, n, seg):
        c = f0 + (f1 - f0) * i / n; out[i:i + seg] = bp_noise(seg / SR, c * 0.6, c * 1.6)[: len(out[i:i + seg])]
    return out


def tone(f, d):
    t = t_(d)
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(f, t.shape)) / SR if np.ndim(f) else 2 * np.pi * f * t
    return np.sin(ph)


def norm(x, peak=0.8):
    return x / (np.abs(x).max() + 1e-9) * peak


def fade_edges(x, ms=2):
    k = int(SR * ms / 1000)
    if len(x) > 2 * k:
        x = x.copy(); x[:k] *= np.linspace(0, 1, k); x[-k:] *= np.linspace(1, 0, k)
    return x


def write_wav(p, x):
    x = np.clip(x, -1, 1); st = np.stack([x, x], 1); d = (st * 32767).astype("<i2")
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(d.tobytes())


def sfx():
    S = {}
    n = lambda d: int(SR * d)
    thump = lambda f0, d: tone(np.linspace(f0, 40, n(d)), d) * env(n(d), 0.001, d / 4)
    S["click"] = norm(bp_noise(0.04, 2000, 9000) * env(n(0.04), 0.0005, 0.008), 0.7)
    S["tap"] = norm(tone(1800, 0.06) * env(n(0.06), 0.001, 0.015) + 0.3 * bp_noise(0.06, 3000, 8000) * env(n(0.06), 0.0005, 0.006), 0.6)
    S["pop"] = norm(tone(np.linspace(900, 420, n(0.12)), 0.12) * env(n(0.12), 0.002, 0.04), 0.75)
    S["ding"] = norm(sum(a * tone(f, 1.2) for f, a in [(1318.5, 1), (2637, 0.35), (3951, 0.15)]) * env(n(1.2), 0.002, 0.35), 0.6)
    S["whoosh"] = norm(sweep_noise(0.55, 300, 4000) * np.hanning(n(0.55)), 0.6)
    for k, (a, b, d) in enumerate([(500, 5000, 0.3), (800, 6000, 0.25), (400, 3500, 0.35)], 1):
        S[f"swish-{k}"] = norm(sweep_noise(d, a, b) * np.hanning(n(d)) ** 1.5, 0.55)
    S["impact"] = norm(thump(120, 0.7) + 0.35 * bp_noise(0.7, 100, 2500) * env(n(0.7), 0.001, 0.06), 0.9)
    for k, f0 in enumerate([140, 110, 90], 1):
        S[f"slam-{k}"] = norm(thump(f0, 0.5) + 0.5 * bp_noise(0.5, 200, 5000) * env(n(0.5), 0.0005, 0.04), 0.9)
    S["cut"] = norm(bp_noise(0.08, 1500, 12000) * env(n(0.08), 0.0003, 0.012) + 0.4 * thump(200, 0.08), 0.7)
    S["riser"] = norm(sweep_noise(1.6, 200, 7000) * np.linspace(0, 1, n(1.6)) ** 2 + 0.3 * tone(np.linspace(200, 900, n(1.6)), 1.6) * np.linspace(0, 1, n(1.6)), 0.6)
    return {k: fade_edges(v) for k, v in S.items()}


def bgm(seconds=60, bpm=112):
    """四拍循环占位配乐：kick / 反拍 hat / clap / bass / 和弦（C 大调 I–V–vi–IV）"""
    beat = 60 / bpm; n = int(SR * seconds); mix = np.zeros(n)
    def add(x, at):
        i = int(round(at * SR)); j = min(n, i + len(x))
        if i < n:
            mix[i:j] += x[: j - i]
    kick = tone(np.linspace(110, 45, int(SR * 0.25)), 0.25) * env(int(SR * 0.25), 0.001, 0.09)
    hat = bp_noise(0.05, 7000, 14000) * env(int(SR * 0.05), 0.0005, 0.012)
    clap = bp_noise(0.18, 900, 4500) * env(int(SR * 0.18), 0.001, 0.05)
    chords = [[261.6, 329.6, 392.0], [196.0, 246.9, 293.7], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6]]
    roots = [65.4, 49.0, 55.0, 43.7]
    k = 0; t = 0.0
    while t < seconds:
        bar = (k // 4) % 4
        add(0.9 * kick, t); add(0.25 * hat, t + beat / 2)
        if k % 2 == 1:
            add(0.35 * clap, t)
        add(0.35 * fade_edges(tone(roots[bar] * 2, beat * 0.9) * env(int(SR * beat * 0.9), 0.005, beat * 0.5)), t + beat / 2)
        if k % 4 == 0:
            d = beat * 4
            add(0.08 * fade_edges(sum(tone(f, d) + 0.5 * tone(f * 2.003, d) for f in chords[bar]) * env(int(SR * d), 0.08, d * 0.8), 20), t)
        k += 1; t += beat
    return norm(mix, 0.7)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["sfx", "music"])
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--bpm", type=float, default=112)
    a = ap.parse_args()
    if a.what == "sfx":
        d = Path(a.out); d.mkdir(parents=True, exist_ok=True)
        S = sfx()
        for k, x in S.items():
            write_wav(d / f"{k}.wav", x)
        print(f"✓ {len(S)} 个音效 → {d}")
    else:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        write_wav(a.out, bgm(a.seconds, a.bpm))
        print(f"✓ 占位配乐 {a.seconds}s @{a.bpm}bpm → {a.out}")
