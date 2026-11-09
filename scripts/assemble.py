#!/usr/bin/env python3
"""步骤 9：整片拼接 + 混音 + （可选）封面替换前 3 帧 + 聊天版。
用法：
  python scripts/assemble.py <项目> [--cover render/cover_16x9.png] [--no-chat] [--chat-mb 95] [--name full]
输出：render/<name>.mp4（原画：crf20 / maxrate 5M / AAC 192k / faststart）+ render/<name>_1080p_chat.mp4（两遍，<95MB）

规则：
- 分段必须首尾相接覆盖全片，且每段帧数 = film.json 里的段长（不对就停）。
- 音频 = build/mix.wav，用 atrim/apad 锁到精确采样数；永不使用 -shortest。
- 封面：16:9 封面 overlay 到第 0–2 帧（3 帧 = 0.125s），原位替换，不插帧、不平移时间轴。
"""
import argparse
from pathlib import Path

from chat_encode import two_pass
from xl_common import FPS, Project, count_frames, die, run

SR = 48000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--cover", help="16:9 封面 PNG（cover.py 生成 render/cover_16x9.png）")
    ap.add_argument("--no-chat", action="store_true")
    ap.add_argument("--chat-only", action="store_true")
    ap.add_argument("--chat-mb", type=float, default=95)
    ap.add_argument("--name", default="full")
    a = ap.parse_args()
    P = Project(a.project)
    film = P.load_film()
    N = film["meta"]["durationInFrames"]
    parts = film["parts"]
    files = []
    for p in parts:
        f = P.render / "parts" / f"{p['name']}.mp4"
        if not f.exists():
            die(f"缺分段 {f}（render_parts.py --parts {p['name']}）")
        n = count_frames(f)
        if n != p["end"] - p["start"] + 1:
            die(f"{f} 帧数 {n} ≠ {p['end'] - p['start'] + 1}")
        files.append(f.resolve())
    mix = (P.build / "mix.wav").resolve()
    if not mix.exists():
        die("缺 build/mix.wav（先跑 mix.py）")
    total = int(round(N / FPS * SR))
    inputs = []
    for f in files:
        inputs += ["-i", str(f)]
    k = len(files)
    fc = "".join(f"[{i}:v]" for i in range(k)) + f"concat=n={k}:v=1:a=0,format=yuv420p,setpts=N/({FPS}*TB)[c]"
    if a.cover:
        cov = Path(a.cover).resolve()
        if not cov.exists():
            die(f"封面不存在 {cov}")
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{3 / FPS:.6f}", "-i", str(cov)]
        fc += f";[{k}:v]scale=1920:1080,format=yuv420p[cv];[c][cv]overlay=0:0:eof_action=pass:enable='lt(n\\,3)'[v]"
        ai = k + 1
    else:
        fc += ";[c]null[v]"
        ai = k
    inputs += ["-i", str(mix)]
    fc += f";[{ai}:a]atrim=end_sample={total},apad=whole_len={total},asetpts=N/SR/TB[a]"
    out = (P.render / f"{a.name}.mp4").resolve()
    if not a.chat_only:
        run(["ffmpeg", "-nostdin", "-v", "error", "-y"] + inputs + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-maxrate", "5M", "-bufsize", "10M", "-profile:v", "high", "-level", "4.1",
             "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
        n = count_frames(out)
        print(f"{'✓' if n == N else '✗'} {out}: {n}/{N} 帧，{out.stat().st_size / 1e6:.1f} MB")
        if n != N:
            die("成片帧数不对")
    if not a.no_chat:
        chat = (P.render / f"{a.name}_1080p_chat.mp4").resolve()
        two_pass(inputs, ["-filter_complex", fc], "[v]", "[a]", N / FPS, chat, a.chat_mb, 128, workdir=P.build)
        n = count_frames(chat)
        print(f"{'✓' if n == N else '✗'} {chat}: {n}/{N} 帧")
        if n != N:
            die("聊天版帧数不对")


if __name__ == "__main__":
    main()
