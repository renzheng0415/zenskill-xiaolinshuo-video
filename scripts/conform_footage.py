#!/usr/bin/env python3
"""步骤 4：实拍素材整帧对齐（conform）到 24fps。
用法：
  python scripts/conform_footage.py <项目> --all                 # footage_raw/ 里全部
  python scripts/conform_footage.py <项目> a.mp4 b.jpg [--id x]  # 指定文件

规则（实战踩过的坑：30fps 素材原速放进 24fps 时间线每 5 帧重复 1 帧，人眼可见顿挫）：
  每个成片帧必须走「整数个」源帧 → 速度 = k·24/源fps，k = round(源fps/24)
  30fps → 0.8x（1 帧对 1 帧）  25fps → 0.96x  50fps → 0.96x（每 2 帧取 1）  60fps → 0.8x  24/23.976 → 1x
  实现：setpts=N/(k·24·TB) 按帧序号重排时间戳，再 fps=24 取整帧；输出 1080p H.264、无音轨、每 24 帧一个关键帧（取帧快）。
图片：最长边 ≤2560，转 JPG（带透明的 PNG 保留 PNG）。
输出：public/footage/<id>.mp4|jpg，build/footage.json（源帧率、速度、时长）。credits.json 没登记的 id 会报警。
"""
import argparse
import json
from pathlib import Path

from xl_common import FPS, Project, die, frac, probe, run, vstream, write_json

VID = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".mpg", ".mpeg", ".ogv"}
IMG = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def conform_video(src: Path, dst: Path):
    v = vstream(probe(src))
    if not v:
        die(f"{src} 没有视频流")
    fps = frac(v.get("avg_frame_rate")) or frac(v.get("r_frame_rate"))
    if fps <= 1:
        die(f"{src} 帧率读不出来")
    k = max(1, round(fps / FPS))
    rate = k * FPS / fps
    if abs(rate - 1) < 0.002:
        rate = 1.0
    w, h = int(v["width"]), int(v["height"])
    scale = "scale='if(gt(a,16/9),-2,1920)':'if(gt(a,16/9),1080,-2)':flags=lanczos"
    vf = f"setpts=N/({k * FPS}*TB),fps={FPS},{scale},format=yuv420p"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "17",
         "-g", "24", "-r", str(FPS), "-movflags", "+faststart", dst])
    d = float(probe(dst)["format"]["duration"])
    note = "竖屏素材（会被裁成横屏）" if h > w else ""
    return {"kind": "video", "src_fps": round(fps, 3), "k": k, "rate": round(rate, 4), "duration": round(d, 3), "src_size": f"{w}x{h}", "note": note}


def conform_image(src: Path, dst: Path):
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-vf", "scale='min(2560,iw)':-2:flags=lanczos", "-frames:v", "1"] +
        (["-q:v", "2"] if dst.suffix == ".jpg" else []) + [dst])
    v = vstream(probe(dst))
    return {"kind": "image", "size": f"{v['width']}x{v['height']}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true", help="处理 footage_raw/ 下全部文件")
    ap.add_argument("--id", help="单个文件时指定 id（默认=文件名）")
    ap.add_argument("--force", action="store_true", help="已存在也重做")
    a = ap.parse_args()
    P = Project(a.project)
    files = [Path(f) for f in a.files]
    if a.all:
        files += sorted(f for f in (P.root / "footage_raw").glob("*") if f.suffix.lower() in VID | IMG)
    if not files:
        die("没有要处理的素材")
    out_dir = P.public / "footage"; out_dir.mkdir(parents=True, exist_ok=True)
    db_path = P.build / "footage.json"
    db = json.loads(db_path.read_text()) if db_path.exists() else {}
    credited = {c.get("id") for c in P.credits()}
    for f in files:
        ext = f.suffix.lower()
        fid = a.id if (a.id and len(files) == 1) else f.stem
        if ext in VID:
            dst = out_dir / f"{fid}.mp4"
        elif ext in IMG:
            dst = out_dir / (f"{fid}.png" if ext == ".png" and "a" in (vstream(probe(f)) or {}).get("pix_fmt", "") else f"{fid}.jpg")
        else:
            print(f"跳过 {f}"); continue
        rel = f"footage/{dst.name}"
        if dst.exists() and rel in [d.get("src") for d in db.values()] and not a.force:
            print(f"= {rel} 已存在"); continue
        info = conform_video(f, dst) if ext in VID else conform_image(f, dst)
        info["src"] = rel; info["raw"] = str(f)
        db[fid] = info
        msg = f"✓ {rel}" + (f"  {info['src_fps']}fps → 24fps @{info['rate']}x，{info['duration']}s" if info["kind"] == "video" else f"  {info['size']}")
        if fid not in credited:
            msg += "   ⚠ credits.json 里没有这个 id（作者/页面/许可/许可链接必须登记）"
        print(msg)
    write_json(db_path, db)
    print(f"footage.json：{len(db)} 条")


if __name__ == "__main__":
    main()
