#!/usr/bin/env python3
"""步骤 6：整片混音 —— 人声为主 + 音乐床（按拍点循环）+ 轻剪切音效 → -16 LUFS、真峰值 ≤ -1 dBTP。
用法：
  python scripts/mix.py <项目> [--music music/bed.mp3] [--music-gain -18] [--bpm 120] [--loop-beats 64] [--no-sfx]
                       [--sfx-offset 0] [--target -16] [--tp -1.0]
默认值来自 film.json 的 music / sfx 段（shotlist.yaml 里写）。

规则（实战定稿参数）：
- 时长 = A-roll 帧数/24，逐采样精确；从不使用 ffmpeg -shortest。
- 人声开头 5ms 淡入、片尾 0.25s 余弦淡出；音乐 0.3s 淡入、尾 2.5s 淡出；末端 80ms 归零防爆音。
- 音乐增益默认 -18 dB（压在人声下）；曲子不够长时按拍点回接：在拍格上的 J 点跳回 loop_beats 拍之前，80ms 交叉，之后逐样本周期延续。
- 音效（引擎合成的无版权音效，assets/sfx）：人物镜头 tap -22、硬切 cut -20、甩/擦 whoosh -14（提前 40ms）、punch swish -13、iris swish -13、slam -16、
  叠字出现 pop -21（每镜最多 1 个，离切点 ≥0.35s）；全部吸附到 24fps 帧格。extra 里可手动加 {t, name, gain}。
- 求和 → 响度归一到 -16 LUFS（pyloudnorm, BS.1770）→ 前瞻限幅（天花板 -1.5 dBFS）→ ffmpeg ebur128 复核真峰值，超了再降天花板。
输出：build/mix.wav（48k/16bit 立体声）、build/mix_report.json、build/sfx_events.json
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from xl_common import FPS, Project, die, ebur128, write_json

SR = 48000
db = lambda g: 10 ** (g / 20)


def read(path, sr=SR):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True)
    if r.returncode:
        die(f"读不了音频 {path}: {r.stderr.decode()[-300:]}")
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2).astype(np.float32)


def estimate_bpm(x):
    """粗估 BPM 与首拍相位：能量包络差分的自相关（70–180 BPM）"""
    mono = x.mean(1); hop = 480  # 10ms
    n = len(mono) // hop
    if n < 400:
        return 120.0, 0.0
    e = np.sqrt((mono[: n * hop].reshape(n, hop) ** 2).mean(1))
    o = np.maximum(0, np.diff(e, prepend=e[0])); o -= o.mean()
    ac = np.correlate(o, o, "full")[n - 1:]
    lags = np.arange(len(ac)); bpm = 6000 / np.maximum(lags, 1)
    ok = (bpm >= 70) & (bpm <= 180)
    lag = lags[ok][np.argmax(ac[ok])]
    period = lag  # in hops
    phase = max(range(int(period)), key=lambda p: o[p::int(period)].sum()) if period >= 1 else 0
    return round(6000 / lag, 2), phase * hop / SR


def music_bed(x, total, bpm, offset, loop_beats, xfade=0.08):
    """曲子够长直接截；不够长按拍点回接并逐样本周期延续"""
    if len(x) >= total:
        return x[:total].copy(), None
    beat = 60 / bpm * SR
    lb = loop_beats
    tail = int(2.0 * SR); xf = int(xfade * SR)
    while lb > 1 and lb * beat > len(x) - tail - offset * SR - xf:
        lb //= 2
    P = int(round(lb * beat))
    if P < SR * 0.5:
        die("音乐太短，无法按拍点循环")
    k = int((len(x) - tail - xf - offset * SR) // beat)
    J = int(round(offset * SR + k * beat))
    while J - P < 0:
        J += int(round(beat))
    out = np.zeros((total, 2), np.float32)
    out[:J] = x[:J]
    r = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
    out[J:J + xf] = x[J:J + xf] * (1 - r) + x[J - P:J - P + xf] * r
    for t in range(J + xf, total, P):
        e = min(total, t + P)
        out[t:e] = out[t - P:e - P]
    return out, {"jump_at": round(J / SR, 3), "back_to": round((J - P) / SR, 3), "period_s": round(P / SR, 4), "beats": lb}


def limiter(x, ceiling, block=240, release_ms=80):
    """块级前瞻限幅：每块增益 ≤ 本块及相邻块所需，释放 80ms，逐样本插值后保证不过天花板"""
    n = len(x); nb = (n + block - 1) // block
    pk = np.abs(x).max(1)
    pad = np.zeros(nb * block, np.float32); pad[:n] = pk
    bmax = pad.reshape(nb, block).max(1)
    need = np.minimum(1.0, ceiling / np.maximum(bmax, 1e-9))
    tgt = need.copy(); tgt[1:] = np.minimum(tgt[1:], need[:-1]); tgt[:-1] = np.minimum(tgt[:-1], need[1:])
    rel = 1 - np.exp(-block / SR * 1000 / release_ms)
    g = np.empty(nb, np.float64); cur = 1.0
    for i in range(nb):
        cur = tgt[i] if tgt[i] < cur else min(tgt[i], cur + (1 - cur) * rel)
        g[i] = cur
    centers = np.arange(nb) * block + block / 2
    gs = np.interp(np.arange(n), centers, g).astype(np.float32)
    y = x * gs[:, None]
    return np.clip(y, -ceiling, ceiling), float(1 - g.min())


def sfx_events(film, extra, offset):
    ev = []
    shots = film["shots"]
    for i, s in enumerate(shots):
        a = s["from"]; tr = s.get("trans", "cut")
        if i > 0:
            if s["kind"] == "person":
                ev.append((a, "tap", -22))
            elif tr == "cut":
                ev.append((a, "cut", -20))
            elif tr in ("whip", "wipe"):
                ev.append((a - 0.04, "whoosh", -14))
            elif tr == "punch":
                ev.append((a, "swish-1", -13))
            elif tr == "iris":
                ev.append((a, "swish-3", -13))
            elif tr == "slam":
                ev.append((a, "slam-1", -16))
            elif tr == "sweep":
                ev.append((a, "swish-2", -15))
        ats = sorted(float(x["at"]) for x in (s.get("tags") or []) + (s.get("items") or []) + ((s.get("panel") or {}).get("items") or []) if "at" in x)
        ats += [float(c["at"]) for c in (s.get("chart"), (s.get("panel") or {}).get("chart")) if c and "at" in c]
        for z in sorted(ats):
            if a + 0.35 <= z < s["to"] - 0.2:
                ev.append((z, "pop", -21)); break
    for e in extra or []:
        ev.append((float(e["t"]), e["name"], float(e.get("gain", -20))))
    return sorted((round(round(t * FPS) / FPS, 6), n, g + offset) for t, n, g in ev if t >= 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--voice")
    ap.add_argument("--music")
    ap.add_argument("--music-gain", type=float)
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--beat-offset", type=float)
    ap.add_argument("--loop-beats", type=int)
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--no-sfx", action="store_true")
    ap.add_argument("--sfx-offset", type=float, default=0.0)
    ap.add_argument("--target", type=float, default=-16.0)
    ap.add_argument("--tp", type=float, default=-1.0)
    ap.add_argument("--out", default="build/mix.wav")
    a = ap.parse_args()
    P = Project(a.project)
    film = P.load_film()
    N = film["meta"]["durationInFrames"]; total = int(round(N / FPS * SR))
    mcfg = film.get("music") or {}; scfg = film.get("sfx") or {}
    out = np.zeros((total, 2), np.float32)
    rep = {"duration_s": total / SR, "frames": N}
    meter = pyln.Meter(SR)

    vpath = Path(a.voice) if a.voice else P.build / "voice.wav"
    if not vpath.exists():
        die(f"人声不存在：{vpath}（prepare_aroll.py 会生成 build/voice.wav）")
    v = read(vpath); voice = np.zeros((total, 2), np.float32); n = min(len(v), total); voice[:n] = v[:n]
    fi = int(0.005 * SR); voice[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    fo = int(0.25 * SR); voice[-fo:] *= (np.cos(np.linspace(0, np.pi, fo)) * 0.5 + 0.5).astype(np.float32)[:, None]
    out += voice
    vI = meter.integrated_loudness(voice.astype(np.float64)) if total > SR * 0.5 else float("nan")
    rep["voice_lufs"] = round(vI, 2)

    msrc = a.music or mcfg.get("src")
    if msrc and not a.no_music:
        mp = Path(msrc); mp = mp if mp.is_absolute() else P.root / mp
        if not mp.exists():
            die(f"音乐不存在：{mp}（先从 2–3 首候选里选定，或 --no-music）")
        m = read(mp)
        bpm = a.bpm or mcfg.get("bpm"); off = a.beat_offset if a.beat_offset is not None else mcfg.get("beat_offset")
        if not bpm or off is None:
            eb, eo = estimate_bpm(m); bpm = bpm or eb; off = eo if off is None else off
        bed, loop = music_bed(m, total, float(bpm), float(off), int(a.loop_beats or mcfg.get("loop_beats") or 64))
        gain = a.music_gain if a.music_gain is not None else float(mcfg.get("gain_db", -18))
        bed *= db(gain)
        fi = min(total, int(0.3 * SR)); bed[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
        fo = min(total, int(2.5 * SR)); bed[-fo:] *= ((np.cos(np.linspace(0, np.pi, fo)) * 0.5 + 0.5) ** 1.3).astype(np.float32)[:, None]
        out += bed
        mI = meter.integrated_loudness(bed.astype(np.float64)) if total > SR * 0.5 else float("nan")
        rep.update({"music": str(mp), "music_gain_db": gain, "bpm": float(bpm), "beat_offset": round(float(off), 3), "loop": loop,
                    "music_lufs": round(mI, 2), "music_below_voice_lu": round(vI - mI, 2)})
        if np.isfinite(vI - mI) and not (8 <= vI - mI <= 26):
            print(f"⚠ 音乐比人声低 {vI - mI:.1f} LU（建议 10–20 LU；调 --music-gain）")

    ev = [] if (a.no_sfx or scfg.get("auto") is False and not scfg.get("extra")) else \
        sfx_events(film if scfg.get("auto", True) else {"shots": []}, scfg.get("extra"), a.sfx_offset)
    cache, missing = {}, set()
    sd = P.sfx_dir()
    for t, name, g in ev:
        if name not in cache:
            f = sd / f"{name}.wav"
            if not f.exists():
                missing.add(name); cache[name] = None
            else:
                cache[name] = read(f)
        s = cache[name]
        if s is None:
            continue
        i = int(round(t * SR)); j = min(total, i + len(s))
        if i < total:
            out[i:j] += s[: j - i] * db(g)
    if missing:
        print(f"⚠ 缺音效文件 {sorted(missing)}（{sd}）")
    write_json(P.build / "sfx_events.json", ev)
    rep["sfx"] = len(ev)

    fz = min(total, int(0.08 * SR)); out[-fz:] *= np.linspace(1, 0, fz, dtype=np.float32)[:, None]
    ceiling = db(-1.5)
    y = out
    for it in range(4):
        I = meter.integrated_loudness(out.astype(np.float64))
        y = out * db(a.target - I)
        y, red = limiter(y, ceiling)
        I2 = meter.integrated_loudness(y.astype(np.float64))
        if abs(I2 - a.target) > 0.3:
            y = y * db(a.target - I2); y, red = limiter(y, ceiling)
        y[-1] = 0
        dst = P.root / a.out; dst.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dst), y, SR, subtype="PCM_16")
        m = ebur128(dst)
        if m["TP"] <= a.tp + 1e-6 or it == 3:
            break
        ceiling *= db(-0.5)
        print(f"  真峰值 {m['TP']} dBTP > {a.tp}，天花板降到 {20 * np.log10(ceiling):.1f} dBFS 重做")
    rep.update({"I": m["I"], "TP": m["TP"], "LRA": m["LRA"], "limiter_max_reduction": round(red, 3), "out": str(dst)})
    write_json(P.build / "mix_report.json", rep)
    ok = abs(m["I"] - a.target) <= 0.5 and m["TP"] <= a.tp
    print(f"{'✓' if ok else '⚠'} {dst}: {total / SR:.3f}s  I={m['I']} LUFS  TP={m['TP']} dBTP  LRA={m['LRA']}  音效 {len(ev)} 个"
          + (f"  音乐低于人声 {rep.get('music_below_voice_lu')} LU" if "music_below_voice_lu" in rep else ""))


if __name__ == "__main__":
    main()
