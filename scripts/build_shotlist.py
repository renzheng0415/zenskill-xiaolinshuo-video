#!/usr/bin/env python3
"""步骤 3：从 SRT + 硬切断点 + 手势表（+ 句表口型）生成镜头表模板 shotlist.yaml，再人工/智能体精修。
用法：
  python scripts/build_shotlist.py <项目> --srt input/aroll.srt [--breakpoints input/breakpoints.tsv] [--gestures input/gestures.tsv]
        [--sentences input/sentence_table.tsv] [--weak 032,074] [--weak-ranges 12.3-15.0] [--title "栏目条文字"] [--force]

规则（用户已确认的小Lin说横屏版式）：
- 开场：人物在专业场景里 wide 全景（遇硬切先盖 B-roll）。
- 每个硬切断点（breakpoints.tsv，建议覆盖区间）→ 必须落在 B-roll/图表卡上。
- 口型弱的句子（--weak / 句表口型均差 ≥70ms 或 ≤1帧比例 <30%）→ 整句 B-roll。
- 手势（gestures.tsv 实测手部入画区间）→ 必须在人物镜头里，推镜关键帧放在手势起点（cut on gesture）。
- 其余：人物（左/右交替，偶尔近景推镜，另一侧放图表）与 B-roll（~2s 一切，实拍为主）交替，人物约 35–45%。
- 「第X条/第X章」开头的句子 → 章节卡。句中出现的数字 → 原样做叠字或大数字卡（数字必须与口播一致）。
输出：shotlist.yaml（模板，media 为 TODO，按 keywords 中英文搜素材）+ build/shotlist_review.md（审阅表）。
"""
import argparse
import json
import re
from pathlib import Path

from xl_common import FPS, Project, col, die, parse_ranges, parse_srt, parse_tsv, write_json

NUM_RE = re.compile(r"(?:约|近|超|超过)?\d+(?:[.,]\d+)?(?:%|％|万亿|万|亿|千|百|元|块|平米|平方米|平|年|个月|月|日|号|天|个|套|倍|成|折|米|岁|次|条|家|层|点)?")
CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百零\d]+[条章点个部节])")
PUNCT = "，。！？、；：,.!?;:…—"
B_TRANS = ["punch", "whip", "wipe", "cut", "iris", "whip", "cut"]


def numbers_in(text):
    return [(m.group(0), m.start()) for m in NUM_RE.finditer(text) if re.search(r"\d", m.group(0))]


def clean(t):
    return t.strip().strip(PUNCT).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--srt", required=True)
    ap.add_argument("--breakpoints")
    ap.add_argument("--gestures")
    ap.add_argument("--sentences", help="句表 tsv（句号/语音起/语音止/口型均差ms/≤1帧），用于定位弱口型句")
    ap.add_argument("--weak", default="", help="弱口型句号，逗号分隔（有句表时按句号，否则按 SRT 序号）")
    ap.add_argument("--weak-ranges", default="", help="直接给弱口型区间：12.3-15.0,40-42.5")
    ap.add_argument("--lip-mean-ms", type=float, default=70)
    ap.add_argument("--lip-in1f", type=float, default=0.30)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--title", default="")
    ap.add_argument("--out", default="shotlist.yaml")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    out = P.root / a.out
    if out.exists() and not a.force:
        die(f"{out} 已存在（精修过的镜头表别被覆盖）；确实要重建加 --force")
    cues = parse_srt(a.srt)
    if not cues:
        die("SRT 是空的")
    dur = a.duration
    ar = P.build / "aroll.json"
    if not dur and ar.exists():
        dur = json.loads(ar.read_text())["duration"]
    dur = dur or cues[-1]["e"] + 0.5
    N = round(dur * FPS)
    f = lambda t: max(0, min(N, round(t * FPS)))

    # ---------- 必须区间 ----------
    PRI = {"O": 1, "P": 2, "B": 3, "C": 4}
    lab = [None] * N; why = [""] * N
    def paint(a_, b_, k, reason):
        for i in range(f(a_), f(b_)):
            if lab[i] is None or PRI[k] >= PRI[lab[i]]:
                if lab[i] == "P" and k == "B":
                    pass
                lab[i] = k; why[i] = reason
    first_end = min(cues[0]["e"], 4.0)
    paint(0, max(first_end, 2.0), "O", "开场·专业场景全景")
    gestures = []
    if a.gestures:
        for r in parse_tsv(a.gestures):
            for g0, g1 in parse_ranges(col(r, "实测手部入画区间", "hand", "gesture_ranges")):
                gestures.append((g0, g1, col(r, "重音词", "stress")))
        for g0, g1, w in gestures:
            paint(g0 - 0.3, g1 + 0.3, "P", f"手势 {g0:.2f}-{g1:.2f}{('（' + w + '）') if w else ''}")
    hard = []
    if a.breakpoints:
        for r in parse_tsv(a.breakpoints):
            t = float(col(r, "时间", "time", "t") or 0)
            m = re.search(r"(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)s", col(r, "建议", "suggest"))
            w0, w1 = (float(m.group(1)), float(m.group(2))) if m else (t - 0.5, t + 0.8)
            w0, w1 = min(w0, t - 0.4), max(w1, t + 0.6)
            hard.append((t, w0, w1, col(r, "类型", "type")))
            paint(w0, w1, "B", f"盖硬切 #{col(r, '断点', 'id')} {t:.3f}s")
    weak = []
    ids = [x.strip() for x in a.weak.split(",") if x.strip()]
    if a.sentences:
        for r in parse_tsv(a.sentences):
            sid = col(r, "句号", "句", "id")
            s0 = float(col(r, "语音起", "speech_start", "句起") or 0); s1 = float(col(r, "语音止", "speech_end", "句止") or 0)
            lm = float(col(r, "口型均差ms", "lip_mean_ms") or 0)
            i1 = col(r, "≤1帧", "in1f")
            ratio = (lambda x: int(x[0]) / max(1, int(x[1])))(i1.split("/")) if "/" in i1 else 1.0
            if sid in ids or lm >= a.lip_mean_ms or ratio < a.lip_in1f:
                weak.append((s0, s1, f"弱口型句 {sid}（均差 {lm:.0f}ms，≤1帧 {ratio:.0%}）"))
    else:
        for c in cues:
            if c["i"] in ids:
                weak.append((c["s"], c["e"], f"弱口型句 SRT#{c['i']}"))
    for w0, w1 in parse_ranges(a.weak_ranges):
        weak.append((w0, w1, f"弱口型 {w0}-{w1}"))
    for w0, w1, r in weak:
        paint(w0 - 0.1, w1 + 0.1, "B", r)
    chapters = []
    for c in cues:
        m = CHAPTER_RE.match(c["t"])
        if m:
            d = min(max(c["e"] - c["s"], 1.6), 3.2)
            chapters.append((c["s"], c["s"] + d, m.group(1), clean(c["t"][len(m.group(1)):])))
            paint(c["s"], c["s"] + d, "C", f"章节 {m.group(1)}")

    # ---------- 切点候选 ----------
    cand = set()
    for c in cues:
        cand.add(f(c["s"])); cand.add(f(c["e"]))
        n = len(c["t"])
        for k, ch in enumerate(c["t"]):
            if ch in PUNCT and 0 < k < n - 1:
                cand.add(f(c["s"] + (c["e"] - c["s"]) * (k + 1) / n))
    for g0, _, _ in gestures:
        cand.add(f(g0 - 0.3))
    cand = sorted(cand)

    # ---------- 把必须区间切成段，空白区交替填 ----------
    segs = []  # [a, b, kind, reason]
    i = 0
    while i < N:
        j = i
        while j < N and lab[j] == lab[i] and why[j] == why[i]:
            j += 1
        segs.append([i, j, lab[i], why[i]]); i = j
    # 人物手势段太短 → 向空白区扩到 ≥2s
    for k, s in enumerate(segs):
        if s[2] == "P" and s[1] - s[0] < 2 * FPS:
            need = 2 * FPS - (s[1] - s[0])
            if k + 1 < len(segs) and segs[k + 1][2] is None:
                take = min(need, segs[k + 1][1] - segs[k + 1][0]); s[1] += take; segs[k + 1][0] += take; need -= take
            if need > 0 and k > 0 and segs[k - 1][2] is None:
                take = min(need, segs[k - 1][1] - segs[k - 1][0]); s[0] -= take; segs[k - 1][1] -= take
    segs = [s for s in segs if s[1] > s[0]]
    filled = []
    LEN = {"B": (1.2 * FPS, 2.0 * FPS, 2.8 * FPS), "P": (2.0 * FPS, 3.0 * FPS, 4.5 * FPS)}
    for s in segs:
        if s[2] is not None:
            filled.append(s); continue
        prev = filled[-1][2] if filled else "B"
        kind = "B" if prev in ("P", "O") else "P"
        t = s[0]
        while t < s[1]:
            lo, tg, hi = LEN[kind]
            if s[1] - t < lo:
                if filled and filled[-1][1] == t:
                    filled[-1][1] = s[1]
                else:
                    filled.append([t, s[1], kind, "节奏"])
                break
            options = [c for c in cand if t + lo <= c <= min(s[1], t + hi)]
            e = min(options, key=lambda c: abs(c - (t + tg))) if options else min(s[1], round(t + tg))
            if s[1] - e < LEN["B"][0] * 0.8:
                e = s[1]
            filled.append([t, e, kind, "节奏"]); t = e
            kind = "B" if kind == "P" else "P"
    # 相邻人物段合并（≤5s），"O" 视作人物
    merged = []
    for s in filled:
        if merged and merged[-1][2] in ("P", "O") and s[2] in ("P", "O") and (s[1] - merged[-1][0]) <= 5 * FPS:
            merged[-1][1] = s[1]; merged[-1][3] = "；".join(x for x in (merged[-1][3], s[3]) if x)
            continue
        merged.append(s)
    # 太碎的人物段（<0.75s，且不是手势）并进相邻 B-roll，避免一闪而过的人物镜头
    k = 0
    while k < len(merged):
        s = merged[k]
        if s[2] in ("P", "O") and s[1] - s[0] < 0.75 * FPS and not s[3].startswith("手势") and len(merged) > 1:
            nb = [j for j in (k - 1, k + 1) if 0 <= j < len(merged) and merged[j][2] in ("B", "C")]
            j = nb[0] if nb else (k - 1 if k > 0 else k + 1)
            if j < k:
                merged[j][1] = s[1]
            else:
                merged[j][0] = s[0]
            merged.pop(k); continue
        k += 1

    # ---------- 生成镜头 ----------
    def cue_text(t0, t1):
        return [c for c in cues if c["e"] > t0 + 0.05 and c["s"] < t1 - 0.05]
    def nums(t0, t1):
        out_ = []
        for c in cue_text(t0, t1):
            for tok, pos in numbers_in(c["t"]):
                at = c["s"] + (c["e"] - c["s"]) * pos / max(1, len(c["t"]))
                if t0 - 0.05 <= at < t1:
                    out_.append((tok, round(at, 3), c["t"]))
        return out_
    shots = []
    pn = 0; bn = 0
    for k, (fa, fb, kind, reason) in enumerate(merged):
        t0, t1 = round(fa / FPS, 3), round(fb / FPS, 3)
        txt = " / ".join(clean(c["t"]) for c in cue_text(t0, t1))
        sid = f"s{k + 1:03d}"
        if kind == "C":
            ch = next(c for c in chapters if abs(c[0] - t0) < 0.3 or c[0] <= t0 < c[1])
            shots.append({"id": sid, "from": t0, "to": t1, "kind": "chapter", "trans": "slam", "why": reason,
                          "chapter": {"n": ch[2], "lines": [{"t": ch[3][:14] or "TODO 副标题", "at": round(t0 + 0.6, 3)}]},
                          "bg": {"src": "TODO 背景实拍/图片"}, "keywords": {"zh": [ch[3][:14]], "en": ["TODO"]}})
        elif kind in ("P", "O"):
            pn += 1
            fr = "wide" if kind == "O" else ("close" if pn % 3 == 0 else ("right" if pn % 2 == 0 else "left"))
            sh = {"id": sid, "from": t0, "to": t1, "kind": "person", "framing": fr, "trans": "cut", "why": reason or "节奏"}
            gs = [g for g in gestures if t0 <= g[0] < t1]
            if gs:
                sh["push"] = {"at": round(gs[0][0], 3), "factor": 1.08, "dur": 0.6}
            elif fr in ("close", "wide"):
                sh["push"] = {"at": round(t0 + 0.4, 3), "factor": 1.06, "dur": 1.2}
            if fr in ("left", "right"):
                ns = nums(t0, t1)
                items = []
                cs = cue_text(t0, t1)
                if cs:
                    first = clean(re.split(f"[{PUNCT}]", cs[0]["t"])[0])[:10]
                    items.append({"k": "p", "t": first or "TODO", "at": round(max(t0, cs[0]["s"]) + 0.1, 3)})
                for tok, at, _ in ns[:2]:
                    items.append({"k": "b", "t": tok, "at": at})
                sh["panel"] = {"items": items}
            shots.append(sh)
        else:
            bn += 1
            ns = nums(t0, t1)
            sh = {"id": sid, "from": t0, "to": t1, "kind": "broll", "trans": B_TRANS[bn % len(B_TRANS)], "why": reason or "节奏"}
            if ns and bn % 2 == 0:
                tok, at, line = ns[0]
                sh.update({"kind": "card", "chart": {"type": "bignum", "at": at, "text": tok, "label": clean(line.split(tok)[0])[-12:] or None},
                           "bg": {"src": "TODO 背景实拍/图片"}})
                if not sh["chart"]["label"]:
                    sh["chart"].pop("label")
            else:
                sh["media"] = {"src": "TODO footage/xxx.mp4", "start": 0}
                if ns:
                    sh["tags"] = [{"t": tok, "at": at} for tok, at, _ in ns[:2]]
            sh["keywords"] = {"zh": [txt[:30]] if txt else [], "en": ["TODO english keywords"]}
            shots.append(sh)
    for s in shots:
        if not s.get("why"):
            s.pop("why", None)

    # 分段：按章节切；没有章节就整片一段
    parts = []
    starts = [0.0] + [s["from"] for s in shots if s["kind"] == "chapter" and s["from"] > 0.5]
    for k, s0 in enumerate(starts):
        parts.append({"name": "open" if k == 0 else f"ch{k}", "from": s0, "to": starts[k + 1] if k + 1 < len(starts) else round(N / FPS, 3)})

    doc = {
        "meta": {"title": a.title, "grade": "navy", "aiLabel": None, "progress": True, "duration": round(N / FPS, 3)},
        "aroll": {"src": "assets/aroll.mp4", "subject": {"x": 0.5, "y": 0.4}, "drift": 0.015,
                  "presets": {"wide": {"zoom": 1.0, "pos": {"x": 0.5, "y": 0.42}}, "left": {"zoom": 1.4, "pos": {"x": 0.31, "y": 0.40}},
                              "right": {"zoom": 1.4, "pos": {"x": 0.69, "y": 0.40}}, "close": {"zoom": 1.6, "pos": {"x": 0.5, "y": 0.38}}}},
        "subs": {"srt": str(Path(a.srt).resolve()), "max_chars": 16},
        "checks": {"hard_cuts": [{"t": t, "cover": [round(w0, 3), round(w1, 3)]} for t, w0, w1, _ in hard],
                   "weak": [{"from": round(w0, 3), "to": round(w1, 3), "note": r} for w0, w1, r in weak],
                   "gestures": [{"from": g0, "to": g1} for g0, g1, _ in gestures]},
        "parts": parts,
        "music": {"src": "music/bed.mp3", "gain_db": -18, "bpm": None, "loop_beats": 64},
        "sfx": {"auto": True, "extra": []},
        "cover": {"bg": None, "kicker": "", "title": [a.title or "TODO 标题"], "highlight": "", "lines": []},
        "shots": shots,
    }
    import yaml
    head = ("# 镜头表模板（build_shotlist.py 生成）。时间 = A-roll 绝对秒，24fps。\n"
            "# 要做的事：每个 TODO 换成真实素材（public/ 内相对路径，如 footage/xxx.mp4），按 keywords 中英文搜 Pexels/Pixabay/Mixkit/Wikimedia…\n"
            "# 改完运行 compile_shotlist.py（会检查：硬切/弱口型全被 B-roll 盖住、手势在人物镜头里、数字与口播一致、素材已登记 credits）。\n")
    out.write_text(head + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=220), encoding="utf-8")
    # 审阅表
    md = ["# 镜头表审阅", "", f"时长 {N / FPS:.3f}s，{len(shots)} 镜；人物 {sum(s['to'] - s['from'] for s in shots if s['kind'] == 'person') / (N / FPS):.0%}", "",
          "| # | 时间 | 时长 | 类型 | 转场 | 机位/素材 | 原因 | 口播 |", "|---|---|---|---|---|---|---|---|"]
    for k, s in enumerate(shots):
        pic = s.get("framing") or (s.get("media") or s.get("bg") or {}).get("src", "")
        if s.get("chart"):
            pic = f"大数字 {s['chart']['text']}"
        md.append(f"| {k + 1} | {s['from']:.2f}–{s['to']:.2f} | {s['to'] - s['from']:.2f} | {s['kind']} | {s.get('trans', 'cut')} | {pic} | {s.get('why', '')} | "
                  f"{' / '.join(clean(c['t']) for c in cue_text(s['from'], s['to']))[:60]} |")
    (P.build / "shotlist_review.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    write_json(P.build / "shotlist_template_stats.json", {"shots": len(shots), "hard_cuts": len(hard), "weak": len(weak), "gestures": len(gestures), "chapters": len(chapters)})
    print(f"✓ {out}：{len(shots)} 镜（硬切 {len(hard)}、弱口型 {len(weak)}、手势 {len(gestures)}、章节 {len(chapters)}）")
    print(f"  审阅表 {P.build / 'shotlist_review.md'}")


if __name__ == "__main__":
    main()
