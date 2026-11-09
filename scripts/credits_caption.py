#!/usr/bin/env python3
"""发布文案里的素材署名（默认不做片尾字幕卡，CC BY / BY-SA 署名放 post caption）。
用法：python scripts/credits_caption.py <项目> [--all]
  只列成片实际用到的素材（film.json）；CC BY/BY-SA 必须署名，其余（CC0/PD/Pexels/Pixabay/Mixkit）加 --all 也列出。
输出：render/credits_caption.txt
"""
import argparse
import re

from xl_common import Project


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    film = P.load_film()
    used = set()
    for s in film["shots"]:
        for k in ("media", "bg"):
            if s.get(k) and s[k].get("src", "").startswith("footage/"):
                used.add(s[k]["src"].split("/")[-1].rsplit(".", 1)[0])
    lines = []
    for c in P.credits():
        if c.get("id") not in used:
            continue
        lic = c.get("license", "")
        if not a.all and not re.search(r"CC BY", lic, re.I):
            continue
        lines.append(f"• {c.get('title') or c['id']} — {c.get('author', '?')}，{lic}（{c.get('license_url', '')}），来源 {c.get('page', '')}"
                     + ("，已裁切调色" if re.search(r"BY", lic) else ""))
    txt = "素材署名：\n" + "\n".join(lines) if lines else "（本片没有需要署名的 CC BY 素材）"
    out = P.render / "credits_caption.txt"; out.write_text(txt + "\n", encoding="utf-8")
    print(txt); print(f"\n✓ {out}")


if __name__ == "__main__":
    main()
