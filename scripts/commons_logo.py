#!/usr/bin/env python3
# Copyright (c) 2026 howoneai. Adapted from howoneai/xiaolin-explainer-packaging.
# Licensed under the MIT License. See NOTICE.md in the skill root.
# 合入本 skill 后：下载的素材仍须写入项目 credits.json；NC/ND 许可一律不用。

"""Fetch real brand / product logos from Wikimedia Commons as PNG (Commons renders the SVG server-side).

  python3 commons_logo.py <out_dir> "WhatsApp=File:WhatsApp.svg" "Slack=Slack icon 2019" ... [--w 512]

Each item is  name=<exact File: title | search words>. A "File:" title is used directly; anything else is a
search in the File namespace preferring .svg results whose title contains the name. Writes <out_dir>/<slug>.png
and appends title, license and URL to <out_dir>/CREDITS.txt. Prints MISSING for anything not found; then pass an
exact File: title (look it up on commons.wikimedia.org) or get the logo from the brand's press kit.

Logos are trademarks even when the file is public domain: use them only to name the product being discussed
(nominative / editorial use), never altered, recoloured or arranged to suggest endorsement.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://commons.wikimedia.org/w/api.php'
UA = {'User-Agent': 'xiaolin-explainer-packaging/1.0 (logo fetch for editorial video)'}


def get(url, timeout=30):
    # Commons rate-limits bursts (HTTP 429): back off and retry
    for i in range(5):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == 4:
                raise
            time.sleep(4 * (i + 1))


def api(**p):
    p.update(format='json')
    return json.loads(get(API + '?' + urllib.parse.urlencode(p)))


def info(title, w):
    d = api(action='query', titles=title, prop='imageinfo', iiprop='url|extmetadata', iiurlwidth=w)
    for pg in d['query']['pages'].values():
        if 'imageinfo' in pg:
            ii = pg['imageinfo'][0]
            md = ii.get('extmetadata', {})
            lic = md.get('LicenseShortName', {}).get('value', '?')
            return pg['title'], ii.get('thumburl') or ii['url'], lic, ii['descriptionurl']
    return None


def search(name, q, w):
    d = api(action='query', list='search', srsearch=q + ' logo', srnamespace=6, srlimit=20)
    hits = [h['title'] for h in d['query']['search']]
    key = re.sub(r'[^a-z0-9]', '', name.lower())
    def score(t):
        tl = re.sub(r'[^a-z0-9]', '', t.lower())
        return (key in tl) * 4 + t.lower().endswith('.svg') * 2 + ('logo' in t.lower() or 'icon' in t.lower())
    hits.sort(key=score, reverse=True)
    for t in hits:
        if score(t) >= 5:
            r = info(t, w)
            if r:
                return r
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    w = int(sys.argv[sys.argv.index('--w') + 1]) if '--w' in sys.argv else 512
    if '--w' in sys.argv:
        args.remove(str(w))
    out, items = args[0], args[1:]
    os.makedirs(out, exist_ok=True)
    for it in items:
        time.sleep(1.0)
        name, _, q = it.partition('=')
        q = q or name
        r = info(q, w) if q.startswith('File:') else search(name, q, w)
        if not r:
            print('MISSING', name)
            continue
        title, url, lic, page = r
        slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
        dst = os.path.join(out, slug + '.png')
        open(dst, 'wb').write(get(url, 60))
        with open(os.path.join(out, 'CREDITS.txt'), 'a') as f:
            f.write(f'{slug}.png\t{name}\t{title}\t{lic}\t{page}\n')
        print('ok', dst, '|', title, '|', lic)


if __name__ == '__main__':
    main()
