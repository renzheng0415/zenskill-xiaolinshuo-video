#!/usr/bin/env python3
# Copyright (c) 2026 howoneai. Adapted from howoneai/xiaolin-explainer-packaging.
# Licensed under the MIT License. See NOTICE.md in the skill root.
# 合入本 skill 后：下载的素材仍须写入项目 credits.json；NC/ND 许可一律不用。

"""Find and download freely licensed photos from Wikimedia Commons, with the credit line.

  commons_photo.py search "<query>" [--n 8] [--all]
      Print candidates: index, title, license, size, author, page URL.
      Only public domain / CC0 / CC BY / CC BY-SA are shown unless --all is given (NC and ND are never usable).
  commons_photo.py get "<File:Title.jpg>" <out_path> [--width 2000]
      Download the image (scaled to --width) and write <out_path>.json with title, license, author, page and a
      ready-to-use Chinese credit line. Refuses files that are not freely licensed.

Put the result in public/photos/ and copy the credit line into the facts file.
"""
import html, json, re, sys, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "explainer-packaging-skill/1.0 (research; https://commons.wikimedia.org/wiki/Commons:API)"


def call(params):
    q = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def is_free(lic):
    l = lic.lower()
    if re.search(r"(^|[\s-])(nc|nd)([\s-]|$)", l):
        return False
    return "public domain" in l or l.startswith("pd") or "cc0" in l or l.startswith(("cc by", "cc-by"))


def describe(p):
    ii = (p.get("imageinfo") or [{}])[0]
    m = ii.get("extmetadata", {})
    g = lambda k: clean(m.get(k, {}).get("value", ""))
    lic = g("LicenseShortName")
    author = g("Artist") or "佚名"
    pd = "public domain" in lic.lower() or lic.lower().startswith("pd") or "cc0" in lic.lower()
    credit = f"{author}（公有领域）/ Wikimedia Commons" if pd else f"{author} / {lic} / Wikimedia Commons"
    return dict(title=p.get("title"), license=lic, license_url=g("LicenseUrl"), author=author, credit_raw=g("Credit"),
                date=g("DateTimeOriginal"), width=ii.get("width"), height=ii.get("height"), mime=ii.get("mime"),
                url=ii.get("thumburl") or ii.get("url"), page=ii.get("descriptionurl"), free=is_free(lic),
                attribution_required=not pd, credit=credit)


def props(width):
    return dict(prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=str(width))


def search(query, n=8, show_all=False, width=2000):
    d = call(dict(action="query", generator="search", gsrsearch=f"{query} filetype:bitmap", gsrnamespace="6",
                  gsrlimit=str(min(50, n * 4)), **props(width)))
    pages = sorted(d.get("query", {}).get("pages", []), key=lambda p: p.get("index", 0))
    rows = [describe(p) for p in pages]
    rows = [r for r in rows if show_all or r["free"]][:n]
    for i, r in enumerate(rows):
        print(f"[{i}] {r['title']}\n    {r['license'] or '?'} | {r['width']}x{r['height']} | {r['author'][:70]}\n    {r['page']}")
    if not rows:
        print("no freely licensed results; try English keywords or a more specific query")
    return rows


def get(title, out, width=2000):
    if not title.startswith("File:"):
        title = "File:" + title
    d = call(dict(action="query", titles=title, **props(width)))
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        sys.exit(f"not found: {title}")
    r = describe(pages[0])
    if not r["free"]:
        sys.exit(f"refused: license '{r['license']}' is not free to reuse ({r['page']})")
    req = urllib.request.Request(r["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp, open(out, "wb") as f:
        f.write(resp.read())
    json.dump(r, open(out + ".json", "w"), ensure_ascii=False, indent=1)
    print(f"saved {out}\n  license: {r['license']}\n  credit: {r['credit']}\n  page: {r['page']}")
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    if len(a) >= 2 and a[0] == "search":
        search(a[1], n=opt("--n", 8), show_all="--all" in a)
    elif len(a) >= 3 and a[0] == "get":
        get(a[1], a[2], width=opt("--width", 2000))
    else:
        print(__doc__)
        sys.exit(1)
