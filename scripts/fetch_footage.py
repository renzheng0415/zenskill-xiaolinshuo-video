#!/usr/bin/env python3
"""实拍素材检索 / 下载 / 登记署名（只用可商用来源，自动排除 ND / NC）。
用法：
  python scripts/fetch_footage.py search "<中文关键词>" "<english keywords>" [--kind video|image] [--sources wikimedia,pexels,pixabay,archive,loc,europeana,openbeelden] [--n 6] [--save hits.json]
  python scripts/fetch_footage.py get <项目> --hits hits.json --pick 3 --id city_aerial      # 从搜索结果下载第 3 条
  python scripts/fetch_footage.py add <项目> --id x --source Mixkit --author Mixkit --page <页面> --license "Mixkit License" \
         --license-url https://mixkit.co/license/ [--url <直链> | --file <本地文件>] [--title ..]          # 手动登记（Mixkit 等无 API 来源）

来源与许可（全部可商用；每条 credits 必须有 author / page / license / license_url）：
  Pexels（PEXELS_API_KEY，Pexels License）  Pixabay（PIXABAY_API_KEY，Pixabay Content License）  Mixkit（手动 add，Mixkit License）
  Wikimedia Commons（无需 key；只收 CC0 / PD / CC BY / CC BY-SA）  Internet Archive Prelinger（无需 key；多为公有领域，逐条核对页面）
  Library of Congress（无需 key；只收 rights 写明 no known restrictions 的条目）
  Europeana / Open Beelden（EUROPEANA_API_KEY，reusability=open → CC0/PDM/BY/BY-SA；Open Beelden 走 Europeana 的 DATA_PROVIDER 过滤）
key 只从环境变量读取（或 ~/.config/xiaolinshuo/keys.env），不写进项目。
下载到 <项目>/footage_raw/<id>.<ext>，再跑 conform_footage.py。
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "zenskill-xiaolinshuo-video/1.0 (footage research; contact: local)"}
OK_LIC = re.compile(r"(CC0|Public ?Domain|PDM|^PD|No known restrictions|CC[ -]BY(?![ -]?(NC|ND))(-SA)?|Pexels|Pixabay|Mixkit)", re.I)
BAD_LIC = re.compile(r"(\bNC\b|\bND\b|NonCommercial|NoDerivs|No ?Derivatives|-nc|-nd|Editorial)", re.I)


def keys():
    k = dict(os.environ)
    f = Path.home() / ".config/xiaolinshuo/keys.env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                a, _, b = line.partition("="); k.setdefault(a.strip(), b.strip().strip('"'))
    return k


def get(url, headers=None, timeout=40):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def gj(url, headers=None):
    return json.loads(get(url, headers))


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def lic_ok(lic):
    return bool(lic) and OK_LIC.search(lic) and not BAD_LIC.search(lic)


# ---------------- 各来源 ----------------
def s_wikimedia(q, kind, n, K):
    ft = "filetype:video" if kind == "video" else "filetype:bitmap"
    u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(dict(
        action="query", format="json", generator="search", gsrnamespace=6, gsrlimit=n * 3, gsrsearch=f"{q} {ft}",
        prop="imageinfo", iiprop="url|size|extmetadata|mime", iiextmetadatafilter="LicenseShortName|LicenseUrl|Artist|ImageDescription"))
    out = []
    for p in gj(u).get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]; m = ii.get("extmetadata", {})
        lic = m.get("LicenseShortName", {}).get("value", "")
        if not lic_ok(lic) or (kind == "image" and ii.get("width", 0) < 1600):
            continue
        out.append({"source": "Wikimedia Commons", "title": p["title"][5:], "author": strip(m.get("Artist", {}).get("value", "")) or "unknown",
                    "page": ii.get("descriptionurl"), "url": ii.get("url"), "license": lic,
                    "license_url": m.get("LicenseUrl", {}).get("value", "") or "https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia",
                    "size": f"{ii.get('width')}x{ii.get('height')}"})
    return out[:n]


def s_pexels(q, kind, n, K, locale=None):
    if not K.get("PEXELS_API_KEY"):
        return []
    h = {"Authorization": K["PEXELS_API_KEY"]}
    base = "https://api.pexels.com/videos/search" if kind == "video" else "https://api.pexels.com/v1/search"
    d = gj(base + "?" + urllib.parse.urlencode({"query": q, "per_page": n, "orientation": "landscape", **({"locale": locale} if locale else {})}), h)
    out = []
    for it in d.get("videos", d.get("photos", [])):
        if kind == "video":
            fs = sorted([f for f in it["video_files"] if (f.get("height") or 0) <= 1080 and f.get("file_type") == "video/mp4"], key=lambda f: -(f.get("height") or 0))
            if not fs:
                continue
            url = fs[0]["link"]; author = it["user"]["name"]; size = f"{fs[0]['width']}x{fs[0]['height']} {fs[0].get('fps')}fps"
        else:
            url = it["src"]["original"]; author = it["photographer"]; size = f"{it['width']}x{it['height']}"
        out.append({"source": "Pexels", "title": it.get("url", "").rstrip("/").split("/")[-1], "author": author, "page": it["url"], "url": url,
                    "license": "Pexels License", "license_url": "https://www.pexels.com/license/", "size": size})
    return out


def s_pixabay(q, kind, n, K):
    if not K.get("PIXABAY_API_KEY"):
        return []
    base = "https://pixabay.com/api/videos/" if kind == "video" else "https://pixabay.com/api/"
    d = gj(base + "?" + urllib.parse.urlencode({"key": K["PIXABAY_API_KEY"], "q": q, "per_page": max(3, n), "safesearch": "true"}))
    out = []
    for it in d.get("hits", []):
        if kind == "video":
            v = it["videos"].get("large") or it["videos"].get("medium"); url = v["url"]; size = f"{v['width']}x{v['height']}"
        else:
            url = it.get("largeImageURL"); size = f"{it.get('imageWidth')}x{it.get('imageHeight')}"
        out.append({"source": "Pixabay", "title": it.get("tags", ""), "author": it.get("user", ""), "page": it.get("pageURL"), "url": url,
                    "license": "Pixabay Content License", "license_url": "https://pixabay.com/service/license-summary/", "size": size})
    return out


def s_archive(q, kind, n, K):
    coll = "collection:prelinger" if kind == "video" else "mediatype:image"
    u = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {"q": f"{coll} AND ({q})", "fl[]": ["identifier", "title", "creator", "licenseurl", "year"], "rows": n, "output": "json"}, doseq=True)
    out = []
    for d in gj(u).get("response", {}).get("docs", []):
        lu = d.get("licenseurl") or ""
        if BAD_LIC.search(lu):
            continue
        lic = "CC0" if "zero" in lu else ("Public Domain Mark" if "publicdomain" in lu or not lu else lu)
        out.append({"source": "Internet Archive (Prelinger)", "title": d.get("title"), "author": d.get("creator") or "Prelinger Archives",
                    "page": f"https://archive.org/details/{d['identifier']}", "url": f"archive:{d['identifier']}", "license": lic,
                    "license_url": lu or "https://creativecommons.org/publicdomain/mark/1.0/", "size": str(d.get("year", "")),
                    "note": "" if lu else "页面无 licenseurl：Prelinger 多为公有领域，下载前打开页面核对"})
    return out


def s_loc(q, kind, n, K):
    fa = "online-format:video" if kind == "video" else "online-format:image"
    d = gj("https://www.loc.gov/search/?" + urllib.parse.urlencode({"q": q, "fo": "json", "fa": fa, "c": n * 2}))
    out = []
    for it in d.get("results", []):
        rights = " ".join(it.get("rights", []) if isinstance(it.get("rights"), list) else [str(it.get("rights", ""))])
        if not re.search(r"no known restrictions|public domain", rights, re.I):
            continue
        out.append({"source": "Library of Congress", "title": it.get("title"), "author": ", ".join(it.get("contributor", [])[:2]) or "Library of Congress",
                    "page": it.get("id") or it.get("url"), "url": (it.get("image_url") or [None])[-1] if kind == "image" else None,
                    "license": "No known restrictions (LoC)", "license_url": "https://www.loc.gov/legal/understanding-copyright/", "size": "",
                    "note": "视频请在页面找下载直链后用 add --url 登记"})
    return out[:n]


def s_europeana(q, kind, n, K, provider=None):
    if not K.get("EUROPEANA_API_KEY"):
        return []
    params = [("wskey", K["EUROPEANA_API_KEY"]), ("query", q), ("rows", n), ("reusability", "open"), ("media", "true"),
              ("qf", "TYPE:VIDEO" if kind == "video" else "TYPE:IMAGE"), ("profile", "rich")]
    if provider:
        params.append(("qf", f'DATA_PROVIDER:"{provider}"'))
    d = gj("https://api.europeana.eu/record/v2/search.json?" + urllib.parse.urlencode(params))
    out = []
    for it in d.get("items", []):
        lic = (it.get("rights") or [""])[0]
        if BAD_LIC.search(lic):
            continue
        out.append({"source": "Open Beelden" if provider else "Europeana", "title": (it.get("title") or [""])[0], "author": ", ".join(it.get("dcCreator", [])[:2]) or (it.get("dataProvider") or [""])[0],
                    "page": it.get("guid"), "url": (it.get("edmIsShownBy") or [None])[0], "license": lic, "license_url": lic, "size": ""})
    return out


SOURCES = {"wikimedia": s_wikimedia, "pexels": s_pexels, "pixabay": s_pixabay, "archive": s_archive, "loc": s_loc,
           "europeana": s_europeana, "openbeelden": lambda q, k, n, K: s_europeana(q, k, n, K, "Netherlands Institute for Sound and Vision")}


def cmd_search(a):
    K = keys(); hits = []
    for src in a.sources.split(","):
        fn = SOURCES.get(src.strip())
        if not fn:
            print(f"未知来源 {src}"); continue
        for q, zh in ((a.en, False), (a.zh, True)):
            if not q or (zh and src not in ("wikimedia", "pexels")):
                continue
            try:
                r = s_pexels(q, a.kind, a.n, K, "zh-CN") if (zh and src == "pexels") else fn(q, a.kind, a.n, K)
            except Exception as e:  # noqa
                print(f"  {src} 出错：{e}", file=sys.stderr); r = []
            for h in r:
                h["query"] = q
            hits += r
        if src in ("pexels", "pixabay", "europeana", "openbeelden") and not any(K.get(x) for x in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "EUROPEANA_API_KEY")):
            print(f"  （{src} 需要 API key 环境变量，已跳过）")
    seen = set(); uniq = []
    for h in hits:
        if h["page"] in seen:
            continue
        seen.add(h["page"]); uniq.append(h)
    for i, h in enumerate(uniq, 1):
        print(f"[{i}] {h['source']} | {h['license']} | {h['size']} | {h['title'][:70]} | {h['author'][:30]}\n     {h['page']}" + (f"\n     ⚠ {h['note']}" if h.get("note") else ""))
    if a.save:
        Path(a.save).write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8"); print(f"✓ 结果存到 {a.save}")


def download(url, dst: Path):
    if url.startswith("archive:"):
        ident = url.split(":", 1)[1]
        files = gj(f"https://archive.org/metadata/{ident}").get("files", [])
        mp4 = [f for f in files if f["name"].lower().endswith(".mp4")]
        if not mp4:
            raise SystemExit(f"{ident} 没有 mp4")
        mp4.sort(key=lambda f: ("h.264" not in f.get("format", "").lower(), -int(f.get("size", 0) or 0)))
        url = f"https://archive.org/download/{ident}/{urllib.parse.quote(mp4[0]['name'])}"
    data = get(url, timeout=300)
    dst.write_bytes(data)
    return url


def credit(project: Path, entry: dict):
    p = project / "credits.json"
    db = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    db = [c for c in db if c.get("id") != entry["id"]] + [entry]
    p.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_get(a):
    hits = json.loads(Path(a.hits).read_text(encoding="utf-8")); h = hits[a.pick - 1]
    if not lic_ok(h["license"]):
        raise SystemExit(f"许可不可商用：{h['license']}")
    if not h.get("url"):
        raise SystemExit("这条没有直链，请打开页面找下载地址，用 add --url 登记")
    proj = Path(a.project); raw = proj / "footage_raw"; raw.mkdir(parents=True, exist_ok=True)
    ext = Path(urllib.parse.urlparse(h["url"]).path).suffix.lower() or (".mp4" if "video" in a.kind else ".jpg")
    if h["url"].startswith("archive:"):
        ext = ".mp4"
    dst = raw / f"{a.id}{ext}"
    real = download(h["url"], dst)
    credit(proj, {"id": a.id, "source": h["source"], "title": h["title"], "author": h["author"], "page": h["page"], "license": h["license"],
                  "license_url": h["license_url"], "download_url": real, "file": str(dst), "keywords": h.get("query", ""),
                  "downloaded_at": datetime.date.today().isoformat()})
    print(f"✓ {dst}（{dst.stat().st_size / 1e6:.1f}MB）已登记 credits.json")


def cmd_add(a):
    if BAD_LIC.search(a.license):
        raise SystemExit(f"许可不可商用：{a.license}")
    proj = Path(a.project); raw = proj / "footage_raw"; raw.mkdir(parents=True, exist_ok=True)
    f = None
    if a.url:
        ext = Path(urllib.parse.urlparse(a.url).path).suffix or ".mp4"
        f = raw / f"{a.id}{ext}"; download(a.url, f)
    elif a.file:
        f = Path(a.file)
    credit(proj, {"id": a.id, "source": a.source, "title": a.title or a.id, "author": a.author, "page": a.page, "license": a.license,
                  "license_url": a.license_url, "download_url": a.url or "", "file": str(f) if f else "", "downloaded_at": datetime.date.today().isoformat()})
    print(f"✓ credits.json 已登记 {a.id}" + (f"，文件 {f}" if f else ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("search"); s.add_argument("zh"); s.add_argument("en"); s.add_argument("--kind", default="video", choices=["video", "image"])
    s.add_argument("--sources", default="wikimedia,pexels,pixabay,archive"); s.add_argument("--n", type=int, default=6); s.add_argument("--save")
    g = sp.add_parser("get"); g.add_argument("project"); g.add_argument("--hits", required=True); g.add_argument("--pick", type=int, required=True)
    g.add_argument("--id", required=True); g.add_argument("--kind", default="video")
    d = sp.add_parser("add"); d.add_argument("project"); d.add_argument("--id", required=True); d.add_argument("--source", required=True)
    d.add_argument("--author", required=True); d.add_argument("--page", required=True); d.add_argument("--license", required=True)
    d.add_argument("--license-url", required=True); d.add_argument("--url"); d.add_argument("--file"); d.add_argument("--title")
    a = ap.parse_args()
    {"search": cmd_search, "get": cmd_get, "add": cmd_add}[a.cmd](a)
