// 基础动效件（取自实战项目 OpenV2/RestKit，去掉项目数据）。时间参数 at 均为「本镜头内帧号」。
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AMBER, BAD, CYAN, FONT, INK, MUTE, big, clamp, eo } from "../lib/theme";
import type { Trans } from "../lib/types";

export const enter = (t: Trans, fr: number): React.CSSProperties => {
  const p = interpolate(fr, [0, 7], [0, 1], eo);
  switch (t) {
    case "punch": return { transform: `scale(${1.3 - 0.3 * p})`, filter: `blur(${(1 - p) * 12}px) brightness(${1 + (1 - p) * 0.6})` };
    case "slam": return { transform: `scale(${1.6 - 0.6 * p})`, filter: `blur(${(1 - p) * 18}px)` };
    case "whip": return { transform: `translateX(${(1 - p) * 420}px)`, filter: `blur(${(1 - p) * 28}px)` };
    case "wipe": return { clipPath: `polygon(0 0, ${p * 140}% 0, ${p * 140 - 40}% 100%, 0 100%)` };
    case "iris": return { clipPath: `circle(${p * 120}% at 50% 50%)` };
    case "sweep": return { filter: `brightness(${1 + (1 - p) * 0.5})` };
    default: return {};
  }
};

export const LightSweep: React.FC = () => {
  const fr = useCurrentFrame();
  const x = interpolate(fr, [0, 12], [-60, 160], clamp);
  return <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "screen", background: `linear-gradient(105deg, transparent ${x - 16}%, rgba(200,250,245,.45) ${x}%, transparent ${x + 16}%)` }} />;
};
export const Flash: React.FC = () => { const fr = useCurrentFrame(); return <AbsoluteFill style={{ background: "#EFFFFD", opacity: [0.3, 0.12, 0][fr] ?? 0, mixBlendMode: "screen" }} />; };
export const Shade: React.FC<{ k?: number }> = ({ k = 0.4 }) => <AbsoluteFill style={{ background: `linear-gradient(180deg, rgba(0,0,0,${k * 0.8}) 0%, rgba(0,0,0,${k * 0.45}) 45%, rgba(0,0,0,${k + 0.15}) 100%)` }} />;
/** 人物另一半压暗，保证面板可读 */
export const SideDim: React.FC<{ side: "left" | "right" }> = ({ side }) => <AbsoluteFill style={{ background: `linear-gradient(${side === "right" ? 90 : 270}deg, transparent 38%, rgba(8,12,16,.42) 70%, rgba(8,12,16,.55) 100%)` }} />;

export const Appear: React.FC<{ at: number; children: React.ReactNode; dy?: number; style?: React.CSSProperties }> = ({ at, children, dy = 26, style }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig();
  const sp = spring({ frame: fr - at, fps, config: { damping: 15, stiffness: 190 } });
  return <div style={{ opacity: fr < at ? 0 : Math.min(1, sp * 1.4), transform: `translateY(${(1 - sp) * dy}px)`, ...style }}>{children}</div>;
};

export const Tag: React.FC<{ text: string; sub?: string; color?: string; at?: number; x: number; y: number; size?: number; ghost?: boolean }> = ({ text, sub, color = CYAN, at = 0, x, y, size = 92, ghost }) => {
  const fr = useCurrentFrame() - at; const { fps } = useVideoConfig();
  const sp = spring({ frame: fr, fps, config: { damping: 14, stiffness: 180 } });
  const clip = interpolate(fr, [0, 8], [0, 100], clamp);
  return <div style={{ position: "absolute", left: x, top: y, opacity: fr < 0 ? 0 : 1, transform: `translateY(${(1 - sp) * 36}px)` }}>
    <div style={{ display: "inline-block", fontFamily: FONT, fontWeight: 700, fontSize: size, lineHeight: 1.12, padding: "6px 26px", clipPath: `inset(0 ${100 - clip}% 0 0)`,
      ...(ghost ? { color: INK, background: "rgba(10,14,18,.6)", border: "1.5px solid rgba(255,255,255,.18)" } : { color: "#0A1012", background: color }) }}>{text}</div>
    {sub ? <div style={{ fontFamily: FONT, fontWeight: 700, color: INK, fontSize: size * 0.36, marginTop: 10, letterSpacing: 5, opacity: interpolate(fr, [6, 14], [0, 1], clamp), textShadow: "0 3px 12px #000" }}>{sub}</div> : null}
  </div>;
};

/** 带划线的字（划线是独立的绝对定位层，在字上面） */
export const Strike: React.FC<{ text: string; at: number; strikeAt: number; size?: number; color?: string; lineColor?: string }> = ({ text, at, strikeAt, size = 84, color = INK, lineColor = AMBER }) => {
  const fr = useCurrentFrame();
  const show = interpolate(fr, [at, at + 6], [0, 1], clamp);
  const w = interpolate(fr, [strikeAt, strikeAt + 8], [0, 100], eo);
  const dim = interpolate(fr, [strikeAt, strikeAt + 8], [1, 0.55], clamp);
  return <div style={{ position: "relative", display: "inline-block", opacity: show, transform: `translateX(${(1 - show) * -30}px)` }}>
    <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: size, color, opacity: dim, textShadow: "0 4px 20px rgba(0,0,0,.6)" }}>{text}</span>
    <div style={{ position: "absolute", left: -8, top: "54%", height: Math.round(size * 0.13), width: `calc(${w}% + 16px)`, background: lineColor, borderRadius: 4, boxShadow: `0 0 18px ${lineColor}aa`, transform: "translateY(-50%) rotate(-2deg)", zIndex: 2 }} />
  </div>;
};

/** 荧光笔划线（字下面一条半透明色条） */
export const Highlight: React.FC<{ text: string; at: number; size?: number; color?: string; hl?: string }> = ({ text, at, size = 84, color = INK, hl = AMBER }) => {
  const fr = useCurrentFrame();
  const w = interpolate(fr, [at, at + 9], [0, 100], eo);
  return <div style={{ position: "relative", display: "inline-block", opacity: fr < at - 6 ? 0 : 1 }}>
    <div style={{ position: "absolute", left: -10, bottom: size * 0.08, height: size * 0.42, width: `calc(${w}% + 20px)`, background: hl, opacity: 0.55, borderRadius: 6, transform: "skewX(-8deg)" }} />
    <span style={{ position: "relative", fontFamily: FONT, fontWeight: 700, fontSize: size, color, textShadow: "0 4px 20px rgba(0,0,0,.5)" }}>{text}</span>
  </div>;
};

/** 玻璃卡片（图表放在人物旁边） */
export const Glass: React.FC<{ x: number; y: number; w: number; h: number; at?: number; children?: React.ReactNode }> = ({ x, y, w, h, at = 0, children }) => {
  const fr = useCurrentFrame() - at;
  const p = interpolate(fr, [0, 9], [0, 1], eo);
  return <div style={{ position: "absolute", left: x, top: y, width: w, height: h, opacity: p, transform: `translateY(${(1 - p) * 24}px)`, borderRadius: 26,
    background: "linear-gradient(160deg, rgba(14,18,22,.72), rgba(14,18,22,.58))", border: "1.5px solid rgba(255,255,255,.14)",
    boxShadow: "0 30px 80px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.10)", backdropFilter: "blur(16px)", padding: "48px 56px", boxSizing: "border-box", overflow: "hidden" }}>{children}</div>;
};

export const Pop: React.FC<{ t: string; at: number; color?: string; size?: number; w?: number }> = ({ t, at, color = CYAN, size = 60, w }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig();
  const sp = spring({ frame: fr - at, fps, config: { damping: 11, stiffness: 240 } });
  return <div style={{ display: "inline-block", opacity: fr < at ? 0 : 1, transform: `scale(${0.6 + 0.4 * sp})`, fontFamily: FONT, fontWeight: 700, fontSize: size, color: INK, padding: "12px 28px", textAlign: "center", width: w,
    border: `2px solid ${color}88`, borderRadius: 16, background: `linear-gradient(180deg, ${color}22, rgba(255,255,255,.03))` }}>{t}</div>;
};

export { AMBER, BAD, CYAN, INK, MUTE, big };
