// 数据驱动的通用图表卡。数字一律用镜头表里的 text 字符串原样上屏（必须与口播一致，不做滚动换算）。
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AMBER, BAD, CYAN, INK, MUTE, big, clamp, eo } from "../lib/theme";
import type { Chart } from "../lib/types";
import { Appear, Highlight, Pop } from "./Primitives";

export type R = (abs: number) => number; // 绝对秒 → 本镜头帧号（≥1）
const textW = (s: string) => Array.from(s).reduce((a, ch) => a + (/[\u0000-\u00ff]/.test(ch) ? 0.58 : 1), 0);
const fit = (s: string, w: number, max: number) => Math.max(24, Math.min(max, (w * 0.92) / Math.max(1, textW(s))));

const Title: React.FC<{ t?: string; at: number; w: number; size?: number }> = ({ t, at, w, size = 64 }) => t ?
  <Appear at={at} style={{ textAlign: "center", marginBottom: 24 }}><span style={{ ...big, fontSize: fit(t, w, size), color: INK }}>{t}</span></Appear> : null;

const BigNum: React.FC<{ c: Extract<Chart, { type: "bignum" }>; r: R; w: number; h: number }> = ({ c, r, w, h }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig(); const a = r(c.at);
  const sp = spring({ frame: fr - a, fps, config: { damping: 11, stiffness: 220 } });
  const size = fit(c.text, w, h * 0.42);
  return <div style={{ width: w, height: h, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
    {c.label ? <Appear at={Math.max(1, a - 4)}><div style={{ ...big, fontSize: fit(c.label, w, 64), color: MUTE }}>{c.label}</div></Appear> : null}
    <div style={{ ...big, fontWeight: 900, fontSize: size, lineHeight: 1.05, color: c.color ?? AMBER, opacity: fr < a ? 0 : 1, transform: `scale(${1.4 - 0.4 * sp})`, textShadow: `0 0 40px ${(c.color ?? AMBER)}55, 0 8px 40px rgba(0,0,0,.6)` }}>{c.text}</div>
    {c.sub ? <Appear at={a + 8}><div style={{ ...big, fontSize: fit(c.sub, w, 56), color: INK, marginTop: 16 }}>{c.sub}</div></Appear> : null}
  </div>;
};

const Bars: React.FC<{ c: Extract<Chart, { type: "bars" }>; r: R; w: number; h: number }> = ({ c, r, w, h }) => {
  const fr = useCurrentFrame(); const a = r(c.at);
  const n = c.bars.length, gap = Math.min(70, w * 0.06), bw = Math.min(180, (w - gap * (n - 1)) / n);
  const area = h - (c.title ? 110 : 20) - 70 - 80;
  const max = Math.max(...c.bars.map((b) => b.value), 1e-9);
  return <div style={{ width: w, height: h, display: "flex", flexDirection: "column" }}>
    <Title t={c.title} at={a} w={w} />
    <div style={{ flex: 1, display: "flex", alignItems: "flex-end", justifyContent: "center", gap }}>
      {c.bars.map((b, i) => {
        const t0 = b.at !== undefined ? r(b.at) : a + 4 + i * 5;
        const k = interpolate(fr, [t0, t0 + 12], [0, 1], eo); const col = b.color ?? (i === n - 1 ? AMBER : CYAN);
        return <div key={i} style={{ width: bw, display: "flex", flexDirection: "column", alignItems: "center" }}>
          <div style={{ ...big, fontSize: fit(b.text, bw * 1.3, 60), color: col, opacity: interpolate(fr, [t0 + 6, t0 + 12], [0, 1], clamp), whiteSpace: "nowrap", marginBottom: 10 }}>{b.text}</div>
          <div style={{ width: bw, height: Math.max(4, area * (b.value / max) * k), background: `linear-gradient(180deg, ${col}, ${col}66)`, borderRadius: "12px 12px 0 0", boxShadow: `0 0 24px ${col}44` }} />
          <div style={{ ...big, fontSize: fit(b.label, bw * 1.3, 40), color: INK, marginTop: 14, whiteSpace: "nowrap", opacity: fr >= t0 ? 1 : 0 }}>{b.label}</div>
        </div>;
      })}
    </div>
  </div>;
};

const Line: React.FC<{ c: Extract<Chart, { type: "line" }>; r: R; w: number; h: number }> = ({ c, r, w, h }) => {
  const fr = useCurrentFrame(); const a = r(c.at); const col = c.color ?? CYAN;
  const H = h - (c.title ? 110 : 20) - 60, pad = 60;
  const vs = c.points.map((p) => p.value); const lo = Math.min(...vs), hi = Math.max(...vs); const span = hi - lo || 1;
  const pts = c.points.map((p, i) => ({ x: pad + (i * (w - 2 * pad)) / Math.max(1, c.points.length - 1), y: 40 + (1 - (p.value - lo) / span) * (H - 90), p }));
  const prog = interpolate(fr, [a, a + 22], [0, 1], eo); const clipW = pad + prog * (w - pad);
  return <div style={{ width: w, height: h }}>
    <Title t={c.title} at={a} w={w} />
    <svg width={w} height={H + 60} style={{ overflow: "visible" }}>
      <defs><clipPath id={`lc${a}`}><rect x={0} y={-50} width={clipW} height={H + 120} /></clipPath></defs>
      <line x1={pad} x2={w - pad} y1={H - 20} y2={H - 20} stroke="rgba(255,255,255,.25)" strokeWidth={3} />
      <g clipPath={`url(#lc${a})`}>
        <polyline points={pts.map((q) => `${q.x},${q.y}`).join(" ")} fill="none" stroke={col} strokeWidth={8} strokeLinejoin="round" strokeLinecap="round" style={{ filter: `drop-shadow(0 0 10px ${col})` }} />
        {pts.map((q, i) => <circle key={i} cx={q.x} cy={q.y} r={i === pts.length - 1 ? 16 : 11} fill={i === pts.length - 1 ? AMBER : col} />)}
      </g>
      {pts.map((q, i) => <g key={"t" + i} opacity={clipW >= q.x ? 1 : 0}>
        {q.p.text ? <text x={q.x} y={q.y - 30} textAnchor="middle" style={{ ...big, fontSize: 40, fill: i === pts.length - 1 ? AMBER : INK } as React.CSSProperties}>{q.p.text}</text> : null}
        <text x={q.x} y={H + 30} textAnchor="middle" style={{ ...big, fontSize: 34, fill: MUTE } as React.CSSProperties}>{q.p.label}</text>
      </g>)}
    </svg>
  </div>;
};

const Compare: React.FC<{ c: Extract<Chart, { type: "compare" }>; r: R; w: number; h: number }> = ({ c, r, w, h }) => {
  const a = r(c.at); const cw = (w - 140) / 2;
  const Col: React.FC<{ s: typeof c.left; col: string; t0: number }> = ({ s, col, t0 }) => <div style={{ width: cw, display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center" }}>
    <Pop t={s.title} at={t0} color={s.color ?? col} size={fit(s.title, cw, 64)} />
    {s.lines.map((l, i) => <Appear key={i} at={t0 + 6 + i * 6}><div style={{ ...big, fontSize: fit(l, cw, 54), marginTop: 22, color: INK }}>{l}</div></Appear>)}
  </div>;
  return <div style={{ width: w, height: h, display: "flex", flexDirection: "column" }}>
    <Title t={c.title} at={a} w={w} />
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 0 }}>
      <Col s={c.left} col={CYAN} t0={c.left.at !== undefined ? r(c.left.at) : a} />
      <div style={{ width: 140, textAlign: "center", ...big, fontSize: 56, color: MUTE }}>{c.vs ?? "VS"}</div>
      <Col s={c.right} col={AMBER} t0={c.right.at !== undefined ? r(c.right.at) : a + 8} />
    </div>
  </div>;
};

const List: React.FC<{ c: Extract<Chart, { type: "list" }>; r: R; w: number; h: number }> = ({ c, r, w, h }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig(); const a = r(c.at);
  const size = Math.min(70, (h - (c.title ? 120 : 0)) / Math.max(1, c.rows.length) * 0.5);
  return <div style={{ width: w, height: h, display: "flex", flexDirection: "column", justifyContent: "center" }}>
    <Title t={c.title} at={a} w={w} />
    {c.rows.map((row, i) => { const t0 = r(row.at); const sp = spring({ frame: fr - t0, fps, config: { damping: 13, stiffness: 220 } });
      return <div key={i} style={{ display: "flex", alignItems: "center", gap: 28, margin: `${size * 0.3}px 0`, opacity: fr < t0 ? 0 : 1, transform: `translateX(${(1 - sp) * -40}px)` }}>
        <div style={{ ...big, fontSize: size * 0.9, color: "#0A1012", background: row.hl ? AMBER : CYAN, width: size * 1.5, height: size * 1.5, borderRadius: size, display: "flex", alignItems: "center", justifyContent: "center", textShadow: "none", flexShrink: 0 }}>{i + 1}</div>
        {row.hl ? <Highlight text={row.t} at={t0 + 4} size={fit(row.t, w - size * 2.5, size)} /> : <div style={{ ...big, fontSize: fit(row.t, w - size * 2.5, size) }}>{row.t}</div>}
      </div>; })}
  </div>;
};

const TimelineChart: React.FC<{ c: Extract<Chart, { type: "timeline" }>; r: R; w: number; h: number }> = ({ c, r, w, h }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig(); const a = r(c.at);
  const n = c.marks.length; const pad = 80; const step = (w - 2 * pad) / Math.max(1, n - 1);
  const lw = interpolate(fr, [a, a + 16], [0, w - 2 * pad], eo); const y = h * 0.6;
  return <div style={{ width: w, height: h, position: "relative" }}>
    <Title t={c.title} at={a} w={w} />
    <div style={{ position: "absolute", left: pad, top: y, width: lw, height: 6, background: "rgba(255,255,255,.4)", borderRadius: 3 }} />
    {c.marks.map((m, i) => { const t0 = r(m.at); const sp = spring({ frame: fr - t0, fps, config: { damping: 10, stiffness: 230 } }); const col = m.color ?? AMBER;
      const x = n === 1 ? w / 2 : pad + i * step; const mw = Math.max(140, step * 0.95);
      return <div key={i} style={{ position: "absolute", left: x - mw / 2, top: y - 130, width: mw, textAlign: "center", opacity: fr < t0 ? 0 : 1 }}>
        <div style={{ ...big, fontSize: fit(m.t, mw, 58), color: col, transform: `translateY(${(1 - sp) * -30}px)` }}>{m.t}</div>
        <div style={{ width: 32, height: 32, borderRadius: 16, background: col, margin: "34px auto 0", transform: `scale(${sp})`, boxShadow: `0 0 30px ${col}` }} />
      </div>; })}
  </div>;
};

export const ChartView: React.FC<{ c: Chart; r: R; w: number; h: number }> = ({ c, r, w, h }) => {
  switch (c.type) {
    case "bignum": return <BigNum c={c} r={r} w={w} h={h} />;
    case "bars": return <Bars c={c} r={r} w={w} h={h} />;
    case "line": return <Line c={c} r={r} w={w} h={h} />;
    case "compare": return <Compare c={c} r={r} w={w} h={h} />;
    case "list": return <List c={c} r={r} w={w} h={h} />;
    case "timeline": return <TimelineChart c={c} r={r} w={w} h={h} />;
    default: return null;
  }
};
export { BAD };
