// 面板条目 / 侧面板 / 全屏居中 / 叠字 / 章节卡 / 字幕 / 外框（进度条）
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AMBER, BAD, CYAN, FONT, INK, MUTE, big, clamp, eo } from "../lib/theme";
import type { Chart, Film, Item, TagT } from "../lib/types";
import { ChartView, R } from "./Charts";
import { Appear, Glass, Highlight, Pop, Strike, Tag } from "./Primitives";
import { DarkBg, Grade } from "./Media";
import type { MediaT } from "../lib/types";

export const ItemView: React.FC<{ it: Item; r: R }> = ({ it, r }) => {
  const a = r(it.at); const { k, t, color: c, size: s } = it;
  if (k === "m") return <Appear at={a}><div style={{ ...big, fontSize: s ?? 48, color: c ?? MUTE, margin: "8px 0" }}>{t}</div></Appear>;
  if (k === "p") return <div style={{ margin: "12px 0" }}><Pop t={t} at={a} color={c ?? CYAN} size={s ?? 72} /></div>;
  if (k === "h") return <div style={{ margin: "14px 0" }}><Highlight text={t} at={a} size={s ?? 96} color={INK} hl={c ?? AMBER} /></div>;
  if (k === "b") return <Appear at={a}><div style={{ ...big, fontSize: s ?? 120, color: c ?? AMBER, margin: "6px 0", lineHeight: 1.1 }}>{t}</div></Appear>;
  if (k === "x") return <div style={{ margin: "12px 0" }}><Strike text={t} at={a} strikeAt={r(it.strikeAt ?? it.at + 0.8)} size={s ?? 90} lineColor={c ?? BAD} /></div>;
  if (k === "a") return <Appear at={a}><div style={{ ...big, fontSize: s ?? 70, color: c ?? CYAN, margin: "0 0 0 12px" }}>{t || "↓"}</div></Appear>;
  return null;
};

/** 侧面板：人物在一侧，另一侧玻璃卡放 items 或图表（图表出现在人物旁边） */
export const Panel: React.FC<{ side: "left" | "right"; items?: Item[]; chart?: Chart; r: R }> = ({ side, items, chart, r }) => {
  const x = side === "right" ? 1000 : 90, w = side === "right" ? 830 : 860, y = 190, h = 620;
  return <Glass x={x} y={y} w={w} h={h} at={1}>
    {chart ? <ChartView c={chart} r={r} w={w - 112} h={h - 96} /> : (items ?? []).map((it, i) => <ItemView key={i} it={it} r={r} />)}
  </Glass>;
};

export const Center: React.FC<{ items: Item[]; r: R }> = ({ items, r }) => <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", textAlign: "center" }}>
  {items.map((it, i) => <ItemView key={i} it={it} r={r} />)}</AbsoluteFill>;

/** B-roll 左上叠字（人物镜头时放在右侧） */
export const Tags: React.FC<{ tags: TagT[]; r: R; x?: number; y?: number }> = ({ tags, r, x = 140, y = 270 }) => {
  let yy = y;
  return <>{tags.map((g, i) => { const size = g.size ?? 104; const el = <Tag key={i} text={g.t} sub={g.sub} color={g.color ?? (i % 2 ? AMBER : CYAN)} at={r(g.at)} x={x} y={yy} size={size} />; yy += size * 1.12 + 40 + (g.sub ? size * 0.5 : 0); return el; })}</>;
};

export const ChapterCard: React.FC<{ n: string; nAt: number; lines: { t: string; at: number; color?: string }[]; r: R; bg?: MediaT; d: number; grade: Grade }> = ({ n, nAt, lines, r, bg, d, grade }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig();
  const a = r(nAt);
  const sp = spring({ frame: fr - a, fps, config: { damping: 12, stiffness: 200 } });
  return <><DarkBg m={bg} dur={d} grade={grade} />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
      <div style={{ ...big, fontSize: 150, color: AMBER, letterSpacing: 30, opacity: fr < a ? 0 : 1, transform: `scale(${1.6 - 0.6 * sp})` }}>{n}</div>
      <div style={{ width: interpolate(fr, [a + 4, a + 16], [0, 900], eo), height: 6, background: CYAN, margin: "18px 0 30px", boxShadow: `0 0 20px ${CYAN}` }} />
      {lines.map((l, i) => <Appear key={i} at={r(l.at)}><div style={{ ...big, fontSize: 80, color: l.color ?? INK, margin: "6px 0" }}>{l.t}</div></Appear>)}
    </AbsoluteFill></>;
};

/** 字幕：底部居中、白字黑描边；按镜头表 subs（绝对秒） */
export const Subtitle: React.FC<{ subs: Film["subs"] }> = ({ subs }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig();
  const cur = subs.find((s) => fr >= Math.round(s.s * fps) && fr < Math.round(s.e * fps));
  if (!cur) return null;
  const pop = interpolate(fr - Math.round(cur.s * fps), [0, 4], [0.93, 1], clamp);
  return <div style={{ position: "absolute", left: 0, right: 0, bottom: 96, display: "flex", justifyContent: "center" }}>
    <div style={{ fontFamily: FONT, fontWeight: 700, fontSize: 62, color: "#FFFFFF", letterSpacing: 2, transform: `scale(${pop})`, WebkitTextStroke: "10px rgba(0,0,0,.85)", paintOrder: "stroke fill", textShadow: "0 6px 20px rgba(0,0,0,.6)" }}>{cur.t}</div>
  </div>;
};

/** 外框：暗角 + 左上栏目条 + 顶部全片进度条（按整片帧数，分段渲染也连续）+ 可选 AI 标（默认关） */
export const Chrome: React.FC<{ film: Film }> = ({ film }) => {
  const fr = useCurrentFrame(); const { durationInFrames } = useVideoConfig();
  const { title, progress = true, aiLabel } = film.meta;
  return <>
    <AbsoluteFill style={{ pointerEvents: "none", background: "radial-gradient(ellipse at center, transparent 62%, rgba(0,0,0,.32) 100%)" }} />
    {title ? <div style={{ position: "absolute", left: 60, top: 48, display: "flex", alignItems: "center", gap: 14, fontFamily: FONT, fontWeight: 700, fontSize: 30, color: INK, textShadow: "0 2px 10px #000" }}>
      <div style={{ width: 14, height: 14, borderRadius: 7, background: CYAN, opacity: 0.5 + 0.5 * Math.abs(Math.sin(fr / 8)) }} />{title}</div> : null}
    {aiLabel ? <div style={{ position: "absolute", right: 60, top: 50, fontFamily: FONT, fontWeight: 700, fontSize: 26, color: MUTE, textShadow: "0 2px 10px #000" }}>{aiLabel}</div> : null}
    {progress ? <div style={{ position: "absolute", left: 0, top: 0, height: 5, width: `${Math.min(1, (fr + 1) / durationInFrames) * 100}%`, background: `linear-gradient(90deg, ${CYAN}, ${AMBER})` }} /> : null}
  </>;
};
