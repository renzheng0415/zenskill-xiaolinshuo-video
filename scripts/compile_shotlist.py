#!/usr/bin/env python3
"""步骤 5：镜头表 shotlist.yaml → build/film.json（Remotion props）+ 规则检查。
用法：python scripts/compile_shotlist.py <项目> [--draft]
  --draft：允许 TODO 素材（用深色底占位，出审片版用），其余检查照常。

检查（ERROR 会退出 1）：
- 镜头首尾相接、从 0 到 A-roll 末帧、无空隙无重叠（24fps 帧格）
- 硬切断点 ±2 帧、弱口型句 —— 不能落在人物镜头上
- 屏幕上的每个数字都必须在附近口播（字幕）里原样出现（numbers exactly as spoken）；个别镜头可写 unspoken_ok: true
- 素材文件存在；public/footage 下每个素材都在 credits.json 登记 author/page/license/license_url；禁止 ND / NC 许可
- 30/25/50fps 素材未 conform 时自动给 playbackRate（并报警）
WARN：B-roll >3.5s、人物 >6s、手势被 B-roll 盖住、画中画过多、素材不够长、粉色系配色。
"""
import argparse
import colorsys
import json
import re
from pathlib import Path

from xl_common import FPS, H, W, Project, die, frac, load_yaml_or_json, parse_srt, probe, vstream, write_json

TRANS = {"cut", "punch", "whip", "wipe", "iris", "slam", "sweep"}
FRAMING = {"native", "wide", "left", "right", "close"}
KINDS = {"person", "broll", "card", "chapter"}
PUNCT = "，。！？、；：,.!?;:…"
BAD_LICENSE = re.compile(r"(\bND\b|NoDeriv|No ?Derivatives|\bNC\b|NonCommercial|Non-Commercial|Editorial)", re.I)


def split_subs(cues, max_chars=16):
    """SRT 句 → 屏幕字幕行：按标点断开、每行 ≤max_chars、按字数比例分配时间、去掉行尾标点。"""
    out = []
    for c in cues:
        t = c["t"].replace("\n", " ").strip()
        parts = [p for p in re.split(f"(?<=[{PUNCT}])", t) if p.strip()]
        chunks = []
        for p in parts:
            p = p.strip()
            while len(p.strip(PUNCT)) > max_chars:
                cut = max_chars
                while cut > 4 and (p[cut - 1].isdigit() and p[cut].isdigit()):
                    cut -= 1
                chunks.append(p[:cut]); p = p[cut:]
            if p.strip(PUNCT):
                chunks.append(p)
        tot = sum(len(x) for x in chunks) or 1
        s = c["s"]
        for x in chunks:
            e = s + (c["e"] - c["s"]) * len(x) / tot
            txt = x.strip().strip(PUNCT).strip()
            txt = re.sub(f"[{PUNCT}]", " ", txt)
            if txt:
                out.append({"s": round(s, 3), "e": round(e, 3), "t": txt})
            s = e
    return out


def is_pink(c):
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?", str(c or ""))
    if not m:
        return False
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return 0.80 <= h <= 0.97 and s > 0.35 and l > 0.45


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--shotlist", help="默认 <项目>/shotlist.yaml")
    ap.add_argument("--film-out", help="默认 <项目>/build/film.json")
    a = ap.parse_args()
    P = Project(a.project)
    doc = load_yaml_or_json(Path(a.shotlist).resolve() if a.shotlist else P.shotlist_path())
    film_out = Path(a.film_out).resolve() if a.film_out else P.film_json
    errors, warns = [], []
    E = errors.append; Wn = warns.append
    meta = doc.get("meta", {})
    ar_info = json.loads((P.build / "aroll.json").read_text()) if (P.build / "aroll.json").exists() else None
    N = ar_info["frames"] if ar_info else round(float(meta.get("duration") or 0) * FPS)
    if meta.get("duration") and ar_info and abs(round(float(meta["duration"]) * FPS) - N) > 1:
        Wn(f"meta.duration={meta['duration']} 与 A-roll {N} 帧不一致，以 A-roll 为准")
    if N <= 0:
        die("不知道片长：先跑 prepare_aroll.py 或在 meta.duration 写秒数")
    f = lambda t: int(round(float(t) * FPS))

    footage_db = json.loads((P.build / "footage.json").read_text()) if (P.build / "footage.json").exists() else {}
    conformed = {v["src"] for v in footage_db.values()}
    credits = {c.get("id"): c for c in P.credits()}
    used_media = set()
    probe_cache = {}

    def media(m, sid, where):
        if m is None:
            return None
        if isinstance(m, str):
            m = {"src": m}
        m = dict(m)
        srcp = str(m.get("src") or "")
        if not srcp or srcp.startswith("TODO"):
            (Wn if a.draft else E)(f"{sid}: {where} 素材还是 TODO")
            return None
        fp = P.public / srcp
        if not fp.exists():
            (Wn if a.draft else E)(f"{sid}: {where} 素材不存在 public/{srcp}")
            return None
        used_media.add(srcp)
        if fp.suffix.lower() in (".mp4", ".mov", ".webm", ".m4v", ".mkv"):
            if srcp not in probe_cache:
                p = probe(fp); v = vstream(p)
                probe_cache[srcp] = (frac(v.get("avg_frame_rate")) or frac(v.get("r_frame_rate")), float(p["format"]["duration"]))
            fps, d = probe_cache[srcp]
            if "rate" not in m:
                if srcp in conformed or abs(fps - FPS) < 0.01:
                    m["rate"] = 1
                else:
                    k = max(1, round(fps / FPS)); m["rate"] = round(k * FPS / fps, 6)
                    Wn(f"{sid}: {srcp} 是 {fps:.2f}fps 且没 conform，临时用 playbackRate={m['rate']}（建议跑 conform_footage.py）")
            m["_avail"] = (d - float(m.get("start", 0))) / float(m["rate"])
        return m

    def items(lst):
        out = []
        for it in lst or []:
            if isinstance(it, (list, tuple)):
                keys = ["k", "t", "at", "color", "size", "strikeAt"]
                it = {keys[i]: v for i, v in enumerate(it) if v is not None}
            out.append(it)
        return out

    def tags(lst):
        out = []
        for g in lst or []:
            if isinstance(g, (list, tuple)):
                keys = ["t", "at", "color", "size", "sub"]
                g = {keys[i]: v for i, v in enumerate(g) if v is not None}
            out.append(g)
        return out

    shots = []
    for i, s in enumerate(sorted(doc.get("shots", []), key=lambda x: float(x["from"]))):
        sid = s.get("id") or f"s{i + 1:03d}"
        o = {"id": sid, "from": round(f(s["from"]) / FPS, 6), "to": round(f(s["to"]) / FPS, 6), "kind": s.get("kind", "broll")}
        if o["kind"] not in KINDS:
            E(f"{sid}: kind={o['kind']} 不认识（person/broll/card/chapter）")
        if s.get("trans", "cut") not in TRANS:
            E(f"{sid}: trans={s.get('trans')} 不认识 {sorted(TRANS)}")
        for k in ("trans", "sweep", "framing", "push", "shade", "pip", "chapter"):
            if s.get(k) is not None:
                o[k] = s[k]
        if o["kind"] == "person" and o.get("framing", "wide") not in FRAMING:
            E(f"{sid}: framing={o.get('framing')} 不认识")
        if s.get("panel"):
            o["panel"] = {"items": items(s["panel"].get("items")), **({"chart": s["panel"]["chart"]} if s["panel"].get("chart") else {})}
        if s.get("items"):
            o["items"] = items(s["items"])
        if s.get("chart"):
            o["chart"] = s["chart"]
        if s.get("tags"):
            o["tags"] = tags(s["tags"])
        for k in ("media", "bg"):
            if s.get(k) is not None:
                m = media(s[k], sid, k)
                if m:
                    avail = m.pop("_avail", None)
                    if k == "media" and avail is not None and avail + 1e-3 < o["to"] - o["from"]:
                        Wn(f"{sid}: {m['src']} 从 {m.get('start', 0)}s 起只够 {avail:.2f}s，镜头 {o['to'] - o['from']:.2f}s（最后会定格）")
                    o[k] = m
        if o.get("push") and not (o["from"] - 0.01 <= float(o["push"]["at"]) <= o["to"]):
            Wn(f"{sid}: push.at={o['push']['at']} 不在镜头内")
        o["_unspoken_ok"] = bool(s.get("unspoken_ok"))
        shots.append(o)

    # 连续性
    if not shots:
        die("镜头表没有镜头")
    if f(shots[0]["from"]) != 0:
        E(f"第一镜从 {shots[0]['from']}s 开始，必须从 0 开始")
    for x, y in zip(shots, shots[1:]):
        if f(x["to"]) < f(y["from"]):
            E(f"{x['id']}→{y['id']}: {x['to']}–{y['from']}s 有空隙（黑帧）")
        if f(x["to"]) > f(y["from"]):
            E(f"{x['id']}→{y['id']}: 重叠 {y['from']}–{x['to']}s")
    if f(shots[-1]["to"]) != N:
        E(f"最后一镜到 {shots[-1]['to']}s（{f(shots[-1]['to'])} 帧），A-roll 是 {N} 帧 = {N / FPS:.3f}s")
    for s in shots:
        if f(s["to"]) <= f(s["from"]):
            E(f"{s['id']}: 时长 ≤0")

    def shot_at(fr):
        for s in shots:
            if f(s["from"]) <= fr < f(s["to"]):
                return s
        return None

    ck = doc.get("checks", {}) or {}
    for h in ck.get("hard_cuts", []):
        t = float(h["t"] if isinstance(h, dict) else h)
        for fr in range(f(t) - 2, f(t) + 3):
            s = shot_at(fr)
            if s and s["kind"] == "person":
                E(f"硬切 {t:.3f}s 落在人物镜头 {s['id']}（{s['from']}–{s['to']}），必须用 B-roll 盖住"); break
    for w in ck.get("weak", []):
        w0, w1 = float(w["from"]) + 0.1, float(w["to"]) - 0.1
        for s in shots:
            if s["kind"] == "person" and s["from"] < w1 and s["to"] > w0:
                E(f"弱口型 {w0 - 0.1:.2f}–{w1 + 0.1:.2f}s 与人物镜头 {s['id']} 重叠（{w.get('note', '')}）")
    for g in ck.get("gestures", []):
        g0, g1 = float(g["from"]), float(g["to"])
        if not any(s["kind"] == "person" and s["from"] < g1 and s["to"] > g0 for s in shots):
            Wn(f"手势 {g0:.2f}–{g1:.2f}s 完全被 B-roll 盖住（最好让手势露在人物镜头里）")

    # 字幕
    sub_cfg = doc.get("subs") or {}
    subs, cues = [], []
    if isinstance(sub_cfg, list):
        subs = [x if isinstance(x, dict) else {"s": x[0], "e": x[1], "t": x[2]} for x in sub_cfg]
        cues = [{"s": x["s"], "e": x["e"], "t": x["t"]} for x in subs]
    elif sub_cfg.get("srt"):
        sp = Path(sub_cfg["srt"]); sp = sp if sp.is_absolute() else P.root / sp
        if not sp.exists():
            E(f"字幕 SRT 不存在：{sp}")
        else:
            cues = parse_srt(sp); subs = split_subs(cues, int(sub_cfg.get("max_chars", 16)))
    # 数字与口播一致
    def norm(x):
        return re.sub(r"[,，\s]", "", x)
    for s in shots:
        texts = [it.get("t", "") for it in (s.get("items") or []) + ((s.get("panel") or {}).get("items") or [])]
        texts += [g.get("t", "") + " " + str(g.get("sub", "")) for g in s.get("tags") or []]
        texts += [l.get("t", "") for l in (s.get("chapter") or {}).get("lines", [])]
        for c in [s.get("chart"), (s.get("panel") or {}).get("chart")]:
            if not c:
                continue
            texts += [str(c.get(k, "")) for k in ("text", "label", "sub", "title")]
            texts += [b.get("text", "") + b.get("label", "") for b in c.get("bars", [])]
            texts += [str(p.get("text", "")) + str(p.get("label", "")) for p in c.get("points", [])]
            texts += [r.get("t", "") for r in c.get("rows", []) + c.get("marks", [])]
            for side in ("left", "right"):
                if c.get(side):
                    texts += [c[side].get("title", "")] + c[side].get("lines", [])
            for col_ in [c.get("color")] + [b.get("color") for b in c.get("bars", [])]:
                if is_pink(col_):
                    Wn(f"{s['id']}: 粉色系配色 {col_}（禁止粉色丝印风）")
        for it in (s.get("items") or []) + (s.get("tags") or []):
            if is_pink(it.get("color")):
                Wn(f"{s['id']}: 粉色系配色 {it.get('color')}（禁止粉色丝印风）")
        if s["_unspoken_ok"] or not cues:
            continue
        near = norm("".join(c["t"] for c in cues if c["e"] > s["from"] - 3 and c["s"] < s["to"] + 3))
        for t in texts:
            for tok in re.findall(r"\d+(?:[.,]\d+)*", t):
                if norm(tok) not in near:
                    E(f"{s['id']}: 屏幕数字「{tok}」（{t}）不在附近口播里——数字必须与口播一致（确实要放可写 unspoken_ok: true）")
    # 节奏
    pip_n = sum(1 for s in shots if s.get("pip"))
    if pip_n > max(2, len(shots) * 0.1):
        Wn(f"画中画 {pip_n} 次，偏多（小Lin说式只偶尔用）")
    for s in shots:
        d = s["to"] - s["from"]
        if s["kind"] in ("broll",) and d > 3.5:
            Wn(f"{s['id']}: B-roll {d:.2f}s 偏长（~2s 一切，快节奏）")
        if s["kind"] == "person" and d > 6:
            Wn(f"{s['id']}: 人物镜头 {d:.2f}s 偏长")
    # 署名
    for srcp in sorted(used_media):
        if not srcp.startswith("footage/"):
            continue
        fid = Path(srcp).stem
        c = credits.get(fid)
        if not c:
            E(f"{srcp}: credits.json 没有 id={fid}（必须登记 author/page/license/license_url）"); continue
        miss = [k for k in ("author", "page", "license", "license_url") if not c.get(k)]
        if miss:
            (Wn if c.get("source", "").lower().startswith("synthetic") else E)(f"{srcp}: credits 缺 {miss}")
        if BAD_LICENSE.search(str(c.get("license", ""))):
            E(f"{srcp}: 许可「{c.get('license')}」含 ND/NC/Editorial，不可商用改编")
    # 分段
    parts = []
    for p in doc.get("parts") or [{"name": "full", "from": 0, "to": N / FPS}]:
        parts.append({"name": p["name"], "start": f(p["from"]), "end": min(N, f(p["to"])) - 1})
    for x, y in zip(parts, parts[1:]):
        if x["end"] + 1 != y["start"]:
            E(f"分段 {x['name']}→{y['name']} 不连续（{x['end']}→{y['start']}）")
    if parts and (parts[0]["start"] != 0 or parts[-1]["end"] != N - 1):
        E(f"分段要覆盖 0–{N - 1} 帧，现在是 {parts[0]['start']}–{parts[-1]['end']}")

    for s in shots:
        s.pop("_unspoken_ok", None)
    aroll = doc.get("aroll", {})
    film = {
        "meta": {"title": meta.get("title", ""), "fps": FPS, "width": W, "height": H, "durationInFrames": N,
                 "grade": meta.get("grade", "navy"), "aiLabel": meta.get("aiLabel"), "progress": meta.get("progress", True)},
        "aroll": {"src": aroll.get("src", "assets/aroll.mp4"), "subject": aroll.get("subject", {"x": 0.5, "y": 0.4}),
                  **({"presets": aroll["presets"]} if aroll.get("presets") else {}), **({"zones": aroll["zones"]} if aroll.get("zones") else {}),
                  "drift": aroll.get("drift", 0.015)},
        "shots": shots, "subs": subs,
        "cover": {k: v for k, v in (doc.get("cover") or {}).items() if v not in (None, "", [])} or None,
        "parts": parts, "music": doc.get("music") or {}, "sfx": doc.get("sfx") or {"auto": True, "extra": []},
        "checks": ck,
    }
    if film["cover"] is None:
        film.pop("cover")
    elif "title" not in film["cover"]:
        film["cover"]["title"] = [meta.get("title") or ""]
    if not (P.public / film["aroll"]["src"]).exists():
        E(f"A-roll 不存在：public/{film['aroll']['src']}（先跑 prepare_aroll.py）")
    write_json(film_out, film)
    ps = sum(s["to"] - s["from"] for s in shots if s["kind"] == "person") / (N / FPS)
    for w in warns:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{'✓' if not errors else '✗'} {film_out.name}：{len(shots)} 镜，{N} 帧 = {N / FPS:.3f}s，人物 {ps:.0%}，字幕 {len(subs)} 行，分段 {[p['name'] for p in parts]}；"
          f"{len(errors)} error / {len(warns)} warn")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
