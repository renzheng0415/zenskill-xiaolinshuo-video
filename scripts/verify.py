#!/usr/bin/env python3
"""步骤 10：成片校验（流式读取，长片不爆内存）。
用法：
  python scripts/verify.py <video.mp4> [--expect-frames N] [--voice build/voice.wav] [--cover render/cover_16x9.png]
        [--face-box 0.31,0.22,0.69,0.74] [--lufs -16 --lufs-tol 1.0 --tp-max -1.0] [--max-mb 95] [--json out.json] [--strict]

检查项（FAIL → 退出码 1）：
  格式      h264 1920x1080 24fps + AAC
  帧        PTS 间隔全部 = 1/24（无掉帧/跳帧）；帧数 = --expect-frames
  重复帧    孤立重复帧（前后都在动、这一帧不动）：>1% 帧 → FAIL（典型是 30fps 素材没 conform）；少量 → WARN（静态图/图表可能误报）
  人物卡顿  人脸区域孤立停顿 → WARN（剪切点/推镜起步属正常）
  黑帧      ≥3 帧连续全黑（片头除外）→ WARN
  音频      咔哒/跳变、句中断音（数字静音空洞）→ FAIL；静音后突然起音 → WARN；结尾不归零 → WARN
  响度      Integrated = -16 ±1 LUFS、真峰值 ≤ -1 dBTP
  音画同步  音轨时长 = 视频时长（±1 帧+AAC 填充）；给了 --voice 时在 10%/50%/90% 处互相关，偏移 ≤ 1 帧
  封面      给了 --cover 时前 3 帧 ≈ 封面、第 4 帧不是封面
  体积      给了 --max-mb 时文件 < 上限
"""
import argparse
import json
import subprocess
import sys

import numpy as np

from xl_common import ebur128, frac, probe, vstream, astream

SR = 48000
GW, GH = 480, 270


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--expect-frames", type=int)
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--voice")
    ap.add_argument("--cover")
    ap.add_argument("--face-box", default="0.31,0.22,0.69,0.74")
    ap.add_argument("--lufs", type=float, default=-16)
    ap.add_argument("--lufs-tol", type=float, default=1.0)
    ap.add_argument("--tp-max", type=float, default=-1.0)
    ap.add_argument("--max-mb", type=float)
    ap.add_argument("--json")
    ap.add_argument("--strict", action="store_true", help="WARN 也算失败")
    a = ap.parse_args()
    R = {"file": a.video, "checks": {}}
    fails, warns = [], []
    def chk(name, ok, detail, warn_only=False):
        R["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            (warns if warn_only else fails).append(f"{name}: {detail}")
        print(f"{'PASS' if ok else ('WARN' if warn_only else 'FAIL')}  {name}: {detail}", flush=True)

    p = probe(a.video); v = vstream(p); au = astream(p)
    size_mb = int(p["format"]["size"]) / 1e6
    fps = frac(v.get("r_frame_rate")) if v else 0
    chk("format", v and v["codec_name"] == "h264" and int(v["width"]) == 1920 and int(v["height"]) == 1080 and abs(fps - a.fps) < 0.01 and au is not None,
        f"{v and v['codec_name']} {v and v['width']}x{v and v['height']} {fps:.3f}fps audio={au and au['codec_name']} {au and au.get('sample_rate')}Hz, {size_mb:.1f}MB")
    if a.max_mb:
        chk("size", size_mb < a.max_mb, f"{size_mb:.1f} MB < {a.max_mb}")

    # ---- PTS（逐包流式）----
    pr = subprocess.Popen(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-of", "csv=p=0", a.video],
                          stdout=subprocess.PIPE, text=True)
    pts = np.array(sorted(float(l.strip().strip(",")) for l in pr.stdout if l.strip().strip(",") not in ("", "N/A")))
    pr.wait()
    d = np.diff(pts); bad = np.where(np.abs(d - 1 / a.fps) > 1e-3)[0]
    nfr = len(pts)
    chk("pts", len(bad) == 0, f"{nfr} 帧，不规则间隔 {len(bad)} 处 {[round(pts[i], 3) for i in bad[:8]]}")
    if a.expect_frames:
        chk("frames", nfr == a.expect_frames, f"{nfr} / 期望 {a.expect_frames}")

    # ---- 逐帧差（流式）----
    fx0, fy0, fx1, fy1 = [float(x) for x in a.face_box.split(",")]
    X0, X1, Y0, Y1 = int(fx0 * GW), int(fx1 * GW), int(fy0 * GH), int(fy1 * GH)
    pv = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", a.video, "-vf", f"scale={GW}:{GH},format=gray", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    FB = GW * GH; prev = None; full, face, luma = [], [], []; first = []
    while True:
        b = pv.stdout.read(FB)
        if len(b) < FB:
            break
        cur = np.frombuffer(b, np.uint8).reshape(GH, GW).astype(np.float32)
        if len(first) < 4:
            first.append(cur)
        luma.append(cur.mean())
        if prev is not None:
            full.append(np.abs(cur - prev).mean()); face.append(np.abs(cur[Y0:Y1, X0:X1] - prev[Y0:Y1, X0:X1]).mean())
        prev = cur
    pv.wait()
    full = np.array(full); face = np.array(face); luma = np.array(luma)
    rep = [i + 1 for i in range(1, len(full) - 1) if full[i] < 0.08 and full[i - 1] > 0.4 and full[i + 1] > 0.4]
    frep = [i + 1 for i in range(1, len(face) - 1) if face[i] < 0.25 * min(face[i - 1], face[i + 1]) and min(face[i - 1], face[i + 1]) > 0.6]
    many = len(rep) > max(2, 0.01 * nfr)
    chk("dup_frames", not many, f"孤立重复帧 {len(rep)} 个 {[round(x / a.fps, 3) for x in rep[:12]]}" + ("（>1%：疑似素材帧率没 conform）" if many else ""), warn_only=not many and len(rep) > 0 and not a.strict)
    if not many and rep:
        pass
    chk("face_stutter", len(frep) == 0, f"人物区卡帧 {len(frep)} 处 {[round(x / a.fps, 3) for x in frep[:12]]}（剪切点/推镜起步可忽略）", warn_only=True)
    blk, run_ = [], 0
    for i, l in enumerate(luma):
        run_ = run_ + 1 if l < 3 else 0
        if run_ == 3 and i > 3:
            blk.append(round((i - 2) / a.fps, 3))
    chk("black", not blk, f"黑帧段 {blk[:8]}", warn_only=True)
    if a.cover:
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", a.cover, "-vf", f"scale={GW}:{GH},format=gray", "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True)
        cv = np.frombuffer(r.stdout, np.uint8).reshape(GH, GW).astype(np.float32)
        ds = [float(np.abs(f - cv).mean()) for f in first]
        chk("cover", all(x < 6 for x in ds[:3]) and (len(ds) < 4 or ds[3] > 2), f"前 4 帧与封面均差 {[round(x, 2) for x in ds]}（前 3 帧应≈0，第 4 帧应明显不同）")

    # ---- 音频（分块流式）----
    pa = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", a.video, "-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], stdout=subprocess.PIPE)
    CH = SR * 10; CTX = 4800
    tail = np.zeros(0, np.float32); off = 0; issues = []; total = 0; last_click = -1e9
    last_samples = np.zeros(0, np.float32)
    def scan(x, base, lo, hi):
        nonlocal last_click
        rms = lambda s, e: float(np.sqrt((x[max(0, s):e] ** 2).mean())) if e > max(0, s) else 0.0
        z = np.abs(x) < 2e-4
        idx = np.where(np.diff(np.r_[0, z.astype(np.int8), 0]))[0]
        for s, e in zip(idx[::2], idx[1::2]):
            if not (lo <= s < hi):
                continue
            if e - s >= 96 and e < len(x) and rms(e, e + 48) > 0.08:
                issues.append((round((base + e) / SR, 3), "abrupt onset after silence", "warn"))
            if e - s >= 96 and s > 0 and rms(s - 48, s) > 0.08:
                issues.append((round((base + s) / SR, 3), "abrupt cut to silence", "warn"))
            if 144 <= e - s <= 4800 and rms(s - 2400, s) > 0.05 and rms(e, e + 2400) > 0.05:
                issues.append((round((base + s) / SR, 3), f"dropout {round((e - s) / SR * 1000)}ms", "fail"))
        dd = np.abs(np.diff(x)); loc = np.convolve(dd, np.ones(480) / 480, "same") + 1e-4
        for i in np.where((dd > 0.2) & (dd > 12 * loc))[0]:
            if lo <= i < hi and base + i - last_click > 480:
                issues.append((round((base + i) / SR, 3), "click/jump", "fail")); last_click = base + i
    while True:
        b = pa.stdout.read(CH * 2)
        if not b:
            break
        x = np.frombuffer(b, np.int16).astype(np.float32) / 32768
        total += len(x)
        buf = np.concatenate([tail, x]); base = off - len(tail)
        scan(buf, base, len(tail) - min(len(tail), CTX // 2) if len(tail) else 0, len(buf) - CTX // 2 if len(b) == CH * 2 else len(buf))
        tail = buf[-CTX:]; off += len(x); last_samples = buf[-SR // 50:]
    pa.wait()
    hard = [i for i in issues if i[2] == "fail"]; soft = [i for i in issues if i[2] == "warn"]
    chk("audio_clicks", not hard, f"咔哒/断音 {len(hard)} {hard[:6]}")
    chk("audio_onsets", not soft, f"突兀起止 {len(soft)} {soft[:6]}", warn_only=True)
    end_rms = float(np.sqrt((last_samples ** 2).mean())) if len(last_samples) else 0
    chk("audio_tail", end_rms < 0.01, f"末尾 20ms RMS {end_rms:.4f}", warn_only=True)

    # ---- 响度 ----
    m = ebur128(a.video)
    chk("loudness", abs(m["I"] - a.lufs) <= a.lufs_tol and m["TP"] <= a.tp_max, f"I={m['I']} LUFS（目标 {a.lufs}±{a.lufs_tol}） TP={m['TP']} dBTP（≤{a.tp_max}） LRA={m['LRA']}")

    # ---- 音画同步 ----
    vd = nfr / a.fps; ad = total / SR
    chk("av_duration", abs(ad - vd) <= 1 / a.fps + 0.05, f"视频 {vd:.3f}s / 音频 {ad:.3f}s")
    if a.voice:
        lags = []
        for q in (0.1, 0.5, 0.9):
            t0 = max(0.0, min(vd - 6, vd * q - 3))
            dur = min(6.0, vd)
            def rd(path):
                r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", path, "-map", "0:a:0", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
                return np.frombuffer(r.stdout, np.int16).astype(np.float32)
            xo, xv = rd(a.video), rd(a.voice)
            n = min(len(xo), len(xv))
            if n < 800 or xv[:n].std() < 1:
                continue
            xo, xv = xo[:n] - xo[:n].mean(), xv[:n] - xv[:n].mean()
            L = 1 << int(np.ceil(np.log2(2 * n)))
            c = np.fft.irfft(np.fft.rfft(xo, L) * np.conj(np.fft.rfft(xv, L)), L)
            c = np.r_[c[-n + 1:], c[:n]]
            lag = (np.argmax(c) - (n - 1)) / 8000
            lags.append(round(float(lag) * 1000, 1))
        chk("av_sync", lags and all(abs(l) <= 1000 / a.fps for l in lags), f"成片音轨 vs 定稿配音偏移 {lags} ms（≤{1000 / a.fps:.0f}ms）")

    R["fails"] = fails; R["warns"] = warns; R["pass"] = not fails and not (a.strict and warns)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(R, fh, ensure_ascii=False, indent=1)
    print(("VERIFY PASS" if R["pass"] else "VERIFY FAIL") + f"  ({len(fails)} fail, {len(warns)} warn)  {a.video}")
    sys.exit(0 if R["pass"] else 1)


if __name__ == "__main__":
    main()
