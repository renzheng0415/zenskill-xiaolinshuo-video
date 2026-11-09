// 实拍/图片层 + 调色（B-roll 跟 A-roll 的海军蓝/青色场景对齐）+ 深色底 + 圆形人物小窗
import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { CYAN, clamp, isImage, src as toSrc } from "../lib/theme";
import type { Film, MediaT, Pt } from "../lib/types";

export type Grade = "navy" | "warm" | "none";
const FILTER: Record<Grade, string> = {
  navy: "saturate(.82) contrast(1.06) brightness(.96)",
  warm: "sepia(.14) saturate(1.05) contrast(1.04)",
  none: "",
};
/** 调色叠层：海军蓝压暗 + 青色提亮（同封面） */
export const GradeOverlay: React.FC<{ grade: Grade }> = ({ grade }) => grade !== "navy" ? null : <>
  <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(8,18,28,.30) 0%, rgba(8,22,32,.12) 45%, rgba(6,14,22,.38) 100%)", mixBlendMode: "multiply" }} />
  <AbsoluteFill style={{ background: "rgba(40,120,130,.08)", mixBlendMode: "screen" }} />
</>;

/**
 * 空镜：视频按 rate 播放（conform_footage.py 已把素材转成 24fps 整帧；rate 默认 1）。
 * 千万别把 30fps 素材原速塞进 24fps 时间线——会周期性跳帧；要么先 conform，要么 rate=0.8（25/50fps → 0.96）。
 */
export const Media: React.FC<{ m: MediaT; dur: number; grade: Grade }> = ({ m, dur, grade }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig();
  const kb = m.kb ?? [1.04, 1.14];
  const s = interpolate(fr, [0, Math.round(dur * fps)], kb, clamp);
  const st: React.CSSProperties = { position: "absolute", width: "100%", height: "100%", objectFit: "cover", objectPosition: m.pos ?? "50% 50%", transform: `scale(${s})`,
    filter: `${m.blur ? `blur(${m.blur}px) ` : ""}${FILTER[grade]}` };
  return <AbsoluteFill style={{ overflow: "hidden" }}>
    {isImage(m.src) ? <Img src={toSrc(m.src)} style={st} />
      : <OffthreadVideo muted src={toSrc(m.src)} startFrom={Math.round((m.start ?? 0) * fps)} playbackRate={m.rate ?? 1} style={st} />}
    <GradeOverlay grade={grade} />
  </AbsoluteFill>;
};

/** 深色网格底（图表卡、章节卡用），背景是模糊压暗的实拍 */
export const DarkBg: React.FC<{ m?: MediaT; dur: number; grade: Grade }> = ({ m, dur, grade }) => <>
  {m ? <Media m={{ kb: [1.1, 1.18], blur: 12, ...m }} dur={dur} grade={grade} /> : <AbsoluteFill style={{ background: "radial-gradient(circle at 28% 30%, #1F3E48 0%, #0E1C22 55%, #070D10 100%)" }} />}
  <AbsoluteFill style={{ background: "rgba(6,10,12,.72)" }} />
  <AbsoluteFill style={{ backgroundImage: "linear-gradient(rgba(95,211,201,.06) 1px, transparent 1px), linear-gradient(90deg, rgba(95,211,201,.06) 1px, transparent 1px)", backgroundSize: "80px 80px" }} />
</>;

export const subjectAt = (film: Film, t: number): { subject: Pt; presets: Film["aroll"]["presets"] } => {
  let subject = film.aroll.subject, presets = film.aroll.presets;
  for (const z of film.aroll.zones ?? []) if (t >= z.from - 0.01) { subject = z.subject ?? subject; presets = { ...presets, ...(z.presets ?? {}) }; }
  return { subject, presets };
};

/** 圆形人物小窗（偶尔用：数据句叠在实拍/图表上） */
export const Pip: React.FC<{ film: Film; from: number; x: number; y: number; d?: number }> = ({ film, from, x, y, d = 360 }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig();
  const { subject } = subjectAt(film, from);
  const vw = d / 0.32, vh = vw * 9 / 16;
  const sp = spring({ frame: fr - 2, fps, config: { damping: 14, stiffness: 200 } });
  return <div style={{ position: "absolute", left: x, top: y, width: d, height: d, borderRadius: "50%", overflow: "hidden", transform: `scale(${0.5 + 0.5 * sp})`, opacity: Math.min(1, sp * 1.5),
    border: `5px solid ${CYAN}`, boxShadow: "0 0 0 10px rgba(95,211,201,.12), 0 24px 70px rgba(0,0,0,.6)", background: "#222" }}>
    <OffthreadVideo muted src={toSrc(film.aroll.src)} startFrom={Math.round(from * fps)}
      style={{ position: "absolute", width: vw, height: vh, left: d / 2 - subject.x * vw, top: d * 0.45 - subject.y * vh, maxWidth: "none" }} />
  </div>;
};
