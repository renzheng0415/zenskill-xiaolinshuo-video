#!/usr/bin/env python3
"""步骤 7：分段渲染（同一个 Film 合成按帧段渲染 → 进度条/时间轴天然连续）。
用法：
  python scripts/render_parts.py <项目> --all                    # film.json 里所有分段
  python scripts/render_parts.py <项目> --parts open,ch1          # 指定分段（逐章出片给用户看）
  python scripts/render_parts.py <项目> --sample 15               # 先出 ~15 秒样片（name=sample）
  python scripts/render_parts.py <项目> --range 30 45 --name test  # 任意区间
  选项：--review（用 build/mix.wav 配上声音出审片版 render/review/<name>.mp4 + 抽帧）--concurrency N --chunk 300 --keep-frames

做法（实战经验：长片一次渲染会在 OffthreadVideo 取帧处超时/卡死）：
  先 remotion bundle（public 目录一起打包，素材变了自动重打）→ 每 300 帧一块渲 JPEG(q95) 序列，失败/卡死自动重试 3 次 →
  ffmpeg 编成 crf12 中间片 render/parts/<name>.mp4 → 核对帧数 = 段长。中间片无音频；音频在 assemble 时整条一次混进去。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from xl_common import ENGINE_DIR, FPS, Project, count_frames, die, need, npx, run


def signature(P: Project) -> str:
    h = hashlib.sha1()
    for base in (ENGINE_DIR / "src", P.public):
        for p in sorted(base.rglob("*")):
            if p.is_file():
                st = p.stat(); h.update(f"{p.relative_to(base)}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()


def ensure_bundle(P: Project, force=False) -> Path:
    need("node")
    if not (ENGINE_DIR / "node_modules" / "remotion").exists():
        die(f"{ENGINE_DIR}/node_modules 不存在，先运行 install.sh")
    out = P.build / "bundle"; sig = signature(P); sf = out / ".xl_sig"
    if not force and sf.exists() and sf.read_text() == sig and (out / "index.html").exists():
        return out
    if out.exists():
        shutil.rmtree(out)
    print("… remotion bundle（public 目录会复制进 bundle）")
    run(npx() + ["remotion", "bundle", "src/index.ts", "--public-dir", str(P.public), "--out-dir", str(out), "--log=error"], cwd=ENGINE_DIR)
    sf.write_text(sig)
    return out


def frames_in(d: Path, s: int, e: int) -> int:
    n = 0
    for f in d.glob("*.jpeg"):
        m = re.search(r"(\d+)\.jpeg$", f.name)
        if m and s <= int(m.group(1)) <= e:
            n += 1
    return n


def frames_dir(P: Project, name: str) -> Path:
    """Remotion 的 --sequence 输出目录不能含 '.'（它把整条路径最后一个点之后当扩展名）。
    项目路径无点 → build/frames_<name>；否则放到无点的临时目录（可用 XL_FRAMES_DIR 指定），同项目同名固定路径，可断点续渲。"""
    d = P.build / f"frames_{name}"
    if "." not in str(d):
        return d
    base = Path(os.environ.get("XL_FRAMES_DIR") or tempfile.gettempdir()).resolve()
    tag = hashlib.sha1(str(P.root.resolve()).encode()).hexdigest()[:10]
    d = base / f"xl_frames_{tag}_{name}"
    if "." in str(d):
        die(f"帧目录 {d} 含 '.'，Remotion 不接受；请设置 XL_FRAMES_DIR=某个不含点的目录")
    return d


def render_range(P: Project, bundle: Path, name: str, start: int, end: int, conc: int, chunk: int, timeout: int, keep=False) -> Path:
    fr_dir = frames_dir(P, name); fr_dir.mkdir(parents=True, exist_ok=True)
    logs = P.build / "logs"; logs.mkdir(exist_ok=True)
    total = end - start + 1
    t0 = time.time()
    for s in range(start, end + 1, chunk):
        e = min(end, s + chunk - 1)
        for attempt in range(1, 4):
            if frames_in(fr_dir, s, e) == e - s + 1:
                break
            cmd = npx() + ["remotion", "render", str(bundle), "Film", str(fr_dir), "--sequence", "--image-format=jpeg", "--jpeg-quality=95",
                           f"--frames={s}-{e}", f"--props={P.film_json}", f"--concurrency={conc}", "--timeout=240000", "--log=error"]
            with open(logs / f"{name}_{s}.log", "w") as lg:
                try:
                    r = subprocess.run(cmd, cwd=ENGINE_DIR, stdout=lg, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=timeout)
                    rc = r.returncode
                except subprocess.TimeoutExpired:
                    rc = "timeout"
            if rc != 0:
                print(f"  ⚠ {name} {s}-{e} 第 {attempt} 次失败（{rc}），日志 {logs / f'{name}_{s}.log'}", flush=True)
        got = frames_in(fr_dir, s, e)
        if got != e - s + 1:
            sys.stderr.write((logs / f"{name}_{s}.log").read_text()[-3000:])
            die(f"{name} {s}-{e} 只渲出 {got}/{e - s + 1} 帧")
        print(f"  {name} {s}-{e} ✓ ({time.time() - t0:.0f}s)", flush=True)
    for f in fr_dir.glob("*.jpeg"):
        m = re.search(r"(\d+)\.jpeg$", f.name)
        tgt = fr_dir / f"f{int(m.group(1)):06d}.jpg"
        if f != tgt:
            f.rename(tgt)
    out = P.render / "parts" / f"{name}.mp4"; out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-framerate", str(FPS), "-start_number", str(start), "-i", str(fr_dir / "f%06d.jpg"), "-frames:v", str(total),
         "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)])
    n = count_frames(out)
    if n != total:
        die(f"{out} 帧数 {n} ≠ {total}")
    if not keep:
        shutil.rmtree(fr_dir)
    print(f"✓ PART {name}: {out}  {n} 帧 = {n / FPS:.3f}s（帧 {start}–{end}）")
    return out


def review(P: Project, name: str, start: int, end: int):
    """审片版：分段画面 + 同位置的整片混音切片（逐采样对齐），再抽 4 张图"""
    part = P.render / "parts" / f"{name}.mp4"; mix = P.build / "mix.wav"
    if not mix.exists():
        print("  （没有 build/mix.wav，审片版无声；先跑 mix.py）")
    out = P.render / "review" / f"{name}.mp4"; out.parent.mkdir(parents=True, exist_ok=True)
    n = end - start + 1
    a0, a1 = round(start / FPS * 48000), round((end + 1) / FPS * 48000)
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(part)]
    if mix.exists():
        cmd += ["-i", str(mix), "-filter_complex", f"[1:a]atrim=start_sample={a0}:end_sample={a1},asetpts=N/SR/TB,apad=whole_len={a1 - a0}[a]", "-map", "0:v", "-map", "[a]",
                "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart", str(out)]
    run(cmd)
    for k, q in enumerate((0.15, 0.4, 0.65, 0.9)):
        t = n * q / FPS
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(out), "-frames:v", "1", "-q:v", "3",
             str(P.render / "review" / f"{name}_{(start / FPS + t):.1f}s.jpg")], quiet=True)
    print(f"✓ 审片版 {out}（抽帧 render/review/{name}_*.jpg）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--parts")
    g.add_argument("--sample", type=float, metavar="SEC")
    g.add_argument("--range", nargs=2, type=float, metavar=("FROM", "TO"))
    ap.add_argument("--name")
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--concurrency", type=int, default=int(os.environ.get("XL_CONCURRENCY", max(1, (os.cpu_count() or 2) // 2))))
    ap.add_argument("--chunk", type=int, default=300)
    ap.add_argument("--chunk-timeout", type=int, default=1800)
    ap.add_argument("--keep-frames", action="store_true")
    ap.add_argument("--rebundle", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    film = P.load_film()
    N = film["meta"]["durationInFrames"]
    if a.all:
        jobs = [(p["name"], p["start"], p["end"]) for p in film["parts"]]
    elif a.parts:
        want = [x.strip() for x in a.parts.split(",")]
        jobs = [(p["name"], p["start"], p["end"]) for p in film["parts"] if p["name"] in want]
        if len(jobs) != len(want):
            die(f"分段名不对，可选：{[p['name'] for p in film['parts']]}")
    elif a.sample:
        jobs = [(a.name or "sample", 0, min(N, round(a.sample * FPS)) - 1)]
    else:
        jobs = [(a.name or "range", max(0, round(a.range[0] * FPS)), min(N, round(a.range[1] * FPS)) - 1)]
    bundle = ensure_bundle(P, a.rebundle)
    for name, s, e in jobs:
        render_range(P, bundle, name, s, e, a.concurrency, a.chunk, a.chunk_timeout, a.keep_frames)
        if a.review or a.sample or a.range:
            review(P, name, s, e)


if __name__ == "__main__":
    main()
