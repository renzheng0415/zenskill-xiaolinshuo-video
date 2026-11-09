#!/usr/bin/env python3
"""步骤 1：定稿 A-roll 入库 + 体检。
用法：
  python scripts/prepare_aroll.py <项目> --aroll input/aroll.mp4 [--voice input/voice.wav] [--force-24] [--drop-first-dup]

做的事：
- 检查 A-roll 必须是 24fps 恒定帧率（时间线 24fps；A-roll 不能变速，否则口型错）。非 24fps 默认报错，--force-24 才用 fps 滤镜转换（会轻微顿挫，最好让上游重出 24fps）。
- 检查「首帧重复」（concat demuxer 常见：帧0=帧1，会让后面整体晚 1 帧）；--drop-first-dup 去掉。
- 无声视频 → public/assets/aroll.mp4（引擎用）；配音 → build/voice.wav（48k 立体声，开头 5ms 淡入防咔哒）。
- 核对配音时长与视频帧数（差 >1 帧报警）。写 build/aroll.json。
"""
import argparse
import subprocess

import numpy as np

from xl_common import FPS, Project, astream, count_frames, die, frac, probe, run, vstream, write_json


def gray_frames(path, n=3):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-frames:v", str(n), "-vf", "scale=480:270,format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    return a.reshape(-1, 270, 480).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--aroll", required=True)
    ap.add_argument("--voice", help="定稿配音 wav（缺省则从 A-roll 音轨抽取）")
    ap.add_argument("--force-24", action="store_true")
    ap.add_argument("--drop-first-dup", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    p = probe(a.aroll); v = vstream(p)
    if not v:
        die("A-roll 没有视频流")
    fps = frac(v.get("avg_frame_rate")) or frac(v.get("r_frame_rate"))
    w, h = int(v["width"]), int(v["height"])
    print(f"A-roll: {w}x{h} {fps:.3f}fps codec={v['codec_name']} pix={v.get('pix_fmt')}")
    if abs(w / h - 16 / 9) > 0.01:
        print("⚠ A-roll 不是 16:9，PersonLayer 以 cover 方式铺满（会裁边）")
    if h < 1080:
        print(f"⚠ A-roll 只有 {h}p：左右机位放大到 1.4× 时会偏软，能拿到 1080p/4K 版本更好")
    if abs(fps - FPS) > 0.01 and not a.force_24:
        die(f"A-roll 是 {fps:.3f}fps，时间线固定 24fps。请上游重出 24fps，或加 --force-24 强制转换（会轻微顿挫）")
    g = gray_frames(a.aroll)
    dup = len(g) >= 3 and np.abs(g[1] - g[0]).mean() < 0.05 and np.abs(g[2] - g[1]).mean() > 0.3
    if dup:
        print("⚠ 检测到首帧重复（帧0=帧1），后续画面会整体晚 1 帧" + ("，已按 --drop-first-dup 去掉" if a.drop_first_dup else "；加 --drop-first-dup 去掉"))
    out = P.public / "assets" / "aroll.mp4"; out.parent.mkdir(parents=True, exist_ok=True)
    vf = []
    if a.drop_first_dup and dup:
        vf.append("select='gt(n\\,0)',setpts=N/(24*TB)")
    if abs(fps - FPS) > 0.01:
        vf.append("fps=24")
    simple = not vf and v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p"
    if simple:
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", a.aroll, "-map", "0:v:0", "-c", "copy", "-an", "-movflags", "+faststart", out])
    else:
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", a.aroll, "-map", "0:v:0", "-an"] + (["-vf", ",".join(vf)] if vf else []) +
            ["-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", "-r", "24", "-g", "48", "-movflags", "+faststart", out])
    n = count_frames(out)
    # 配音
    voice = P.build / "voice.wav"
    src = a.voice or a.aroll
    if not a.voice and not astream(p):
        die("A-roll 没有音轨，请用 --voice 指定定稿配音")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-map", "0:a:0", "-ac", "2", "-ar", "48000", "-af", "afade=t=in:d=0.005", "-c:a", "pcm_s16le", voice])
    vd = float(probe(voice)["format"]["duration"])
    info = {"src": "assets/aroll.mp4", "fps": FPS, "frames": n, "duration": n / FPS, "voice": str(voice), "voice_duration": vd,
            "width": w, "height": h, "first_frame_dup": bool(dup)}
    write_json(P.build / "aroll.json", info)
    print(f"✓ A-roll {n} 帧 = {n / FPS:.3f}s；配音 {vd:.3f}s（差 {abs(vd - n / FPS) * 1000:.0f}ms）")
    if abs(vd - n / FPS) > 1 / FPS:
        print("⚠ 配音和视频长度差超过 1 帧：确认它们来自同一次定稿导出（成片时长以视频帧数为准，混音会补静音/截断）")


if __name__ == "__main__":
    main()
