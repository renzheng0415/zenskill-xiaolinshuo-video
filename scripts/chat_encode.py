#!/usr/bin/env python3
"""聊天发送版：1080p 两遍 x264，按时长算码率，保证 < 上限（默认 95MB）。
用法：python scripts/chat_encode.py <in.mp4> <out.mp4> [--max-mb 95] [--audio-kbps 128]
（assemble.py 内部直接复用 two_pass()，从分段源一次编码，画质比转码成片更好。）
"""
import argparse
import os
import tempfile
from pathlib import Path

from xl_common import FPS, die, duration, run


def bitrate_for(dur: float, max_mb: float, audio_kbps: int) -> int:
    budget_kbps = max_mb * 1e6 * 8 / 1000 / dur * 0.95       # 留 5% 余量（容器开销 + 码率波动）
    return int(max(300, min(6000, budget_kbps - audio_kbps)))


def two_pass(inputs: list, vfilter_args: list, vmap: str, amap: str | None, dur: float, out: Path, max_mb=95.0, audio_kbps=128, workdir=None):
    workdir = Path(workdir or tempfile.mkdtemp(prefix="xlchat_"))
    log = str(workdir / "x264pass")
    vk = bitrate_for(dur, max_mb, audio_kbps)
    for attempt in range(3):
        common = ["-c:v", "libx264", "-preset", "slow", "-b:v", f"{vk}k", "-pix_fmt", "yuv420p", "-r", str(FPS), "-passlogfile", log]
        amaps = ["-map", amap] if amap else []
        # 第 1 遍也映射音频（filtergraph 里有带标签的音频输出时，不映射会报 "output unconnected"）；输出到 null 不落盘
        run(["ffmpeg", "-nostdin", "-v", "error", "-y"] + inputs + vfilter_args + ["-map", vmap] + amaps + common + ["-pass", "1", "-c:a", "pcm_s16le", "-f", "null", os.devnull], cwd=workdir)
        run(["ffmpeg", "-nostdin", "-v", "error", "-y"] + inputs + vfilter_args + ["-map", vmap] + amaps + common +
            ["-maxrate", f"{vk * 2}k", "-bufsize", f"{vk * 4}k", "-profile:v", "high", "-level", "4.1", "-pass", "2",
             "-c:a", "aac", "-b:a", f"{audio_kbps}k", "-movflags", "+faststart", str(out)], cwd=workdir)
        mb = out.stat().st_size / 1e6
        if mb < max_mb:
            print(f"✓ 聊天版 {out}: {mb:.1f} MB（视频 {vk}k + 音频 {audio_kbps}k，两遍）")
            return mb
        vk = int(vk * max_mb / mb * 0.95)
        print(f"  {mb:.1f}MB 超限，降到 {vk}k 重编")
    die("聊天版压不到上限以内")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--max-mb", type=float, default=95)
    ap.add_argument("--audio-kbps", type=int, default=128)
    a = ap.parse_args()
    d = duration(a.inp)
    two_pass(["-i", str(Path(a.inp).resolve())], [], "0:v:0", "0:a:0?", d, Path(a.out).resolve(), a.max_mb, a.audio_kbps)
