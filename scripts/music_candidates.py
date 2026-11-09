#!/usr/bin/env python3
"""音乐候选：先给用户 2–3 首可商用候选的 20 秒试听，选定后再做全片音乐床。
用法：
  python scripts/music_candidates.py <项目> --suggest                         # 列出实战用过/推荐的可商用曲（只给链接，不打包）
  python scripts/music_candidates.py <项目> <URL或文件> [<URL或文件> ...] [--start 15] [--len 20]
  python scripts/music_candidates.py <项目> --choose A                         # 把候选 A 的整首复制成 music/bed.<ext>
输出：music/candidates/{A,B,C}_<名>.<ext>（整首）+ *_preview.mp3（试听）+ music/candidates/SOURCES.md（曲名/作者/页面/许可，需补全）+ 估算 BPM
"""
import argparse
import shutil
import string
import urllib.parse
import urllib.request
from pathlib import Path

from mix import estimate_bpm, read
from xl_common import Project, die, duration, run

SUGGEST = [
    ("Minimal Techno 01 / Alejandro Magaña (A. M.)", "https://mixkit.co/free-stock-music/minimal-techno-01-162/", "https://assets.mixkit.co/music/162/162.mp3",
     "极简 tech house，稳定四拍，冷静科技感，最不抢人声（实战定稿用曲）"),
    ("Trap Electro Vibes / Alejandro Magaña (A. M.)", "https://mixkit.co/free-stock-music/trap-electro-vibes-126/", "https://assets.mixkit.co/music/126/126.mp3",
     "电子 trap，重低音+切分鼓，更有冲击力"),
    ("Running Out of Time / Ahjay Stelino", "https://mixkit.co/free-stock-music/running-out-of-time-77/", "https://assets.mixkit.co/music/77/77.mp3",
     "企业纪录片式紧迫推进，明快"),
]
LIC = "Mixkit Stock Music Free License（可商用、社媒可用、无需署名）https://mixkit.co/license/#musicFree"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("items", nargs="*")
    ap.add_argument("--suggest", action="store_true")
    ap.add_argument("--choose")
    ap.add_argument("--start", type=float, default=15)
    ap.add_argument("--len", type=float, default=20)
    a = ap.parse_args()
    P = Project(a.project)
    cd = P.root / "music" / "candidates"; cd.mkdir(parents=True, exist_ok=True)
    if a.suggest:
        for t, page, url, note in SUGGEST:
            print(f"- {t}\n  页面 {page}\n  音频 {url}\n  {note}\n  许可 {LIC}")
        print("\n挑 2–3 首：python scripts/music_candidates.py <项目> <音频URL1> <音频URL2> <音频URL3>")
        return
    if a.choose:
        src = sorted(f for f in cd.glob(f"{a.choose}_*") if "_preview" not in f.name)
        if not src:
            die(f"没有候选 {a.choose}")
        dst = P.root / "music" / f"bed{src[0].suffix}"
        shutil.copy(src[0], dst)
        print(f"✓ {dst}（shotlist.yaml 里 music.src 改成 music/{dst.name}，再跑 compile + mix）"); return
    if not a.items:
        die("给出 2–3 个音频 URL 或文件，或用 --suggest")
    rows = ["| 候选 | 文件 | 曲名 / 作者 | 来源页 | 许可 | BPM≈ |", "|---|---|---|---|---|---|"]
    for k, it in zip(string.ascii_uppercase, a.items):
        name = Path(urllib.parse.urlparse(it).path).name or f"track{k}.mp3"
        dst = cd / f"{k}_{name}"
        if it.startswith("http"):
            req = urllib.request.Request(it, headers={"User-Agent": "Mozilla/5.0"})
            dst.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        else:
            shutil.copy(it, dst)
        d = duration(dst); st = a.start if d > a.start + a.len else 0
        prev = cd / f"{k}_preview.mp3"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(st), "-t", str(a.len), "-i", str(dst), "-af", f"afade=t=in:d=0.5,afade=t=out:st={a.len - 1}:d=1",
             "-b:a", "192k", str(prev)], quiet=True)
        bpm, off = estimate_bpm(read(dst))
        sug = next((s for s in SUGGEST if s[2] == it), None)
        rows.append(f"| {k} | {dst.name} | {sug[0] if sug else 'TODO'} | {sug[1] if sug else 'TODO'} | {LIC if sug else 'TODO（必须可商用）'} | {bpm} |")
        print(f"✓ {k}: {dst.name} {d:.1f}s，BPM≈{bpm}（首拍≈{off:.2f}s），试听 {prev.name}")
    (cd / "SOURCES.md").write_text("# 音乐候选\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"✓ {cd / 'SOURCES.md'}；把试听发给用户选，选定后 --choose A")


if __name__ == "__main__":
    main()
