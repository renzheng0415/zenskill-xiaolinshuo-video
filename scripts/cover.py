#!/usr/bin/env python3
"""步骤 11（可选）：封面。
用法：
  python scripts/cover.py <项目> [--bg-from footage/x.mp4@1.5 | --bg footage/x.jpg] [--show-safe]
输出：render/cover_16x9.png/.jpg（1920×1080，assemble --cover 用它替换前 3 帧）、render/cover_9x16.png/.jpg（1080×1920）
文案来自镜头表 cover: {kicker, title[], highlight, lines[]}；所有文字居中且在中央 3:4 安全区内。默认不加 AI 标。
"""
import argparse
import json

from render_parts import ensure_bundle
from xl_common import ENGINE_DIR, Project, npx, run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--bg", help="public 内相对路径的背景图")
    ap.add_argument("--bg-from", help="从视频抽一帧做背景：footage/x.mp4@秒")
    ap.add_argument("--show-safe", action="store_true", help="画出 3:4 安全区虚线（检查用）")
    a = ap.parse_args()
    P = Project(a.project)
    film = P.load_film()
    cover = dict(film.get("cover") or {"title": [film["meta"]["title"]]})
    if a.bg_from:
        src, t = a.bg_from.rsplit("@", 1)
        out = P.public / "assets" / "cover_bg.jpg"; out.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", t, "-i", str(P.public / src), "-frames:v", "1", "-q:v", "2", str(out)])
        cover["bg"] = "assets/cover_bg.jpg"
    if a.bg:
        cover["bg"] = a.bg
    if a.show_safe:
        cover["showSafe"] = True
    film["cover"] = cover
    props = P.build / "cover_props.json"
    props.write_text(json.dumps(film, ensure_ascii=False), encoding="utf-8")
    bundle = ensure_bundle(P)
    for comp, name in (("CoverH", "cover_16x9"), ("CoverV", "cover_9x16")):
        png = P.render / f"{name}.png"
        run(npx() + ["remotion", "still", str(bundle), comp, str(png), f"--props={props}", "--frame=0", "--log=error"], cwd=ENGINE_DIR)
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(png), "-q:v", "2", str(P.render / f"{name}.jpg")], quiet=True)
        print(f"✓ {png}")


if __name__ == "__main__":
    main()
