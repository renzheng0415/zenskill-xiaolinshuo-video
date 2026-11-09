// 封面：16:9（CoverH，替换成片前 3 帧）与 9:16（CoverV）。所有文字居中，且落在画面中央 3:4 安全区内
// （横版安全区 810×1080，竖版 1080×1440），这样各平台裁成 3:4 / 1:1 预览时字不被切。
import React from "react";
import { AbsoluteFill, Img, useVideoConfig } from "remotion";
import { AMBER, CYAN, FONT, INK, src as toSrc } from "./lib/theme";
import type { Film } from "./lib/types";

const textW = (s: string) => Array.from(s).reduce((a, ch) => a + (/[\u0000-\u00ff]/.test(ch) ? 0.58 : 1), 0);
const B: React.CSSProperties = { fontFamily: FONT, fontWeight: 900, color: INK, lineHeight: 1.08, textShadow: "0 6px 30px rgba(0,0,0,.7)", whiteSpace: "nowrap" };

export const Cover: React.FC<Film> = (film) => {
  const { width, height } = useVideoConfig();
  const v = height > width;
  const c = film.cover ?? { title: [film.meta.title || "标题"] };
  const safeW = v ? width : Math.round(height * 3 / 4), safeH = v ? Math.round(width * 4 / 3) : height;
  const s = v ? 1.27 : 1;
  const fit = (t: string, base: number, ls = 0) => Math.min(base * s, (safeW * 0.88) / Math.max(1, textW(t) * (1 + ls)));
  return <AbsoluteFill style={{ background: "#0A1219" }}>
    {c.bg ? <Img src={toSrc(c.bg)} style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover", filter: "saturate(.7) hue-rotate(-8deg) brightness(1.15) contrast(1.05)" }} /> : null}
    {/* 海军蓝/青调色 + 中心压暗，保证字可读 */}
    <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(8,18,28,.55) 0%, rgba(8,22,32,.35) 45%, rgba(6,14,22,.75) 100%)", mixBlendMode: "multiply" }} />
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, rgba(6,14,22,.5) 0%, rgba(6,14,22,.22) 55%, rgba(6,14,22,0) 100%)" }} />
    <AbsoluteFill style={{ background: "rgba(40,120,130,.10)", mixBlendMode: "screen" }} />
    {c.showSafe ? <div style={{ position: "absolute", left: (width - safeW) / 2, top: (height - safeH) / 2, width: safeW, height: safeH, border: "3px dashed rgba(255,80,80,.8)", boxSizing: "border-box" }} /> : null}
    <div style={{ position: "absolute", left: (width - safeW) / 2, top: (height - safeH) / 2, width: safeW, height: safeH, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", textAlign: "center" }}>
      {c.kicker ? <>
        <div style={{ ...B, fontWeight: 700, fontSize: fit(c.kicker, 60, 0.23), color: CYAN, letterSpacing: 14 * s }}>{c.kicker}</div>
        <div style={{ width: 120 * s, height: 6 * s, background: CYAN, margin: `${26 * s}px 0 ${30 * s}px`, boxShadow: `0 0 18px ${CYAN}` }} />
      </> : null}
      {c.title.map((t, i) => <div key={i} style={{ ...B, fontSize: fit(t, 110, 0.06), letterSpacing: 6 * s, marginTop: i ? 10 * s : 0 }}>{t}</div>)}
      {c.highlight ? <div style={{ ...B, fontSize: fit(c.highlight + "  ", 110, 0.06), letterSpacing: 6 * s, marginTop: 10 * s }}>
        <span style={{ color: "#0A1012", background: AMBER, padding: `0 ${22 * s}px`, textShadow: "none" }}>{c.highlight}</span></div> : null}
      {(c.lines ?? []).map((t, i) => <div key={"l" + i} style={{ ...B, fontWeight: 700, fontSize: fit(t, 44, 0.07), marginTop: (i ? 10 : 46) * s, color: "rgba(242,245,244,.9)", letterSpacing: 3 }}>{t}</div>)}
    </div>
  </AbsoluteFill>;
};

/** 可选片尾署名卡（默认不用：CC BY 署名放发布文案里） */
export const Credits: React.FC<Film> = (film) => {
  const cr = film.credits ?? { title: "素材署名", lines: [] };
  return <AbsoluteFill style={{ background: "#070a0c", alignItems: "center", justifyContent: "center", flexDirection: "column", fontFamily: FONT, color: INK }}>
    <div style={{ fontSize: 56, fontWeight: 700, color: CYAN, marginBottom: 30 }}>{cr.title}</div>
    {cr.lines.slice(0, 16).map((l, i) => <div key={i} style={{ fontSize: 28, opacity: 0.85, margin: "4px 0" }}>{l}</div>)}
  </AbsoluteFill>;
};
