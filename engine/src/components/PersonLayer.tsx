import React from "react";
import { AbsoluteFill, Easing, OffthreadVideo, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { src as toSrc } from "../lib/theme";
import type { Framing, PresetMap, Pt } from "../lib/types";

/**
 * 数字人图层：输入一条 A-roll，镜头（位置/裁切/缩放/过渡）全部由参数决定。
 * 坐标全用 0–1 归一化（素材与画面都是 16:9）：素材点 u 落在画面 p + zoom·(u − focus)。zoom=1 且 focus=p 时等于原样铺满。
 * A-roll 原速播放（口型不变速），startFrom = 本段成片起点（成片时间轴 = A-roll 时间轴）。
 */
export type Cam = { zoom: number; focus: Pt; pos: Pt };
export type Crop = { x: number; y: number; w: number; h: number };
export type PersonPresets = Record<Exclude<Framing, "native">, { zoom: number; pos: Pt }>;

// 默认预设：居中中景 A-roll；人物脸部中心落到 pos 上。左/右 = 人物偏一侧、另一侧留给图表/实拍。
export const DEFAULT_PRESETS: PersonPresets = {
  wide: { zoom: 1.0, pos: { x: 0.5, y: 0.42 } },
  left: { zoom: 1.4, pos: { x: 0.31, y: 0.40 } },
  right: { zoom: 1.4, pos: { x: 0.69, y: 0.40 } },
  close: { zoom: 1.6, pos: { x: 0.5, y: 0.38 } },
};

export type Key = {
  at: number;                      // 素材自身时间（秒）
  framing?: Framing;
  crop?: Crop;                     // 直接给裁切框（优先于 framing）
  push?: number;                   // 在该机位上再乘的推近倍数，如 1.1 盖跳剪
  trans?: "cut" | "ease";
  dur?: number;                    // ease 时长（秒）
};

export type PersonLayerProps = {
  src: string; offset?: number; subject?: Pt; keys: Key[]; presets?: PresetMap;
  drift?: number; clampEdges?: boolean; bottomShade?: boolean; style?: React.CSSProperties;
};

const ease = Easing.inOut(Easing.cubic);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export function keyToCam(k: Key, subject: Pt, presets: PersonPresets): Cam {
  let cam: Cam;
  if (k.crop) {
    const c = k.crop;
    cam = { zoom: Math.max(1 / c.w, 1 / c.h), focus: { x: c.x + c.w / 2, y: c.y + c.h / 2 }, pos: { x: 0.5, y: 0.5 } };
  } else if (!k.framing || k.framing === "native") {
    cam = { zoom: 1, focus: subject, pos: subject };
  } else {
    const p = presets[k.framing];
    cam = { zoom: p.zoom, focus: subject, pos: p.pos };
  }
  if (k.push && k.push !== 1) cam = { ...cam, zoom: cam.zoom * k.push }; // 以人物为中心推近
  return cam;
}

/** 不露边：zoom≥1 时把落点往里推到刚好铺满 */
export function clampCam(c: Cam): Cam {
  const fit = (pos: number, f: number) => {
    const lo = c.zoom * f, hi = 1 - c.zoom * (1 - f);
    return Math.min(lo, Math.max(hi, pos));
  };
  const zoom = Math.max(1, c.zoom);
  return { zoom, focus: c.focus, pos: { x: fit(c.pos.x, c.focus.x), y: fit(c.pos.y, c.focus.y) } };
}

export function camAt(t: number, keys: Key[], subject: Pt, presets: PersonPresets): Cam {
  let i = 0;
  for (let j = 0; j < keys.length; j++) if (t >= keys[j].at - 1e-6) i = j;
  const cur = keyToCam(keys[i], subject, presets);
  const k = keys[i];
  if (i === 0 || k.trans !== "ease") return cur;
  const prev = keyToCam(keys[i - 1], subject, presets);
  const u = ease(Math.min(1, (t - k.at) / (k.dur ?? 0.6)));
  return {
    zoom: lerp(prev.zoom, cur.zoom, u),
    focus: { x: lerp(prev.focus.x, cur.focus.x, u), y: lerp(prev.focus.y, cur.focus.y, u) },
    pos: { x: lerp(prev.pos.x, cur.pos.x, u), y: lerp(prev.pos.y, cur.pos.y, u) },
  };
}

export const PersonLayer: React.FC<PersonLayerProps> = ({
  src, offset = 0, subject = { x: 0.5, y: 0.4 }, keys, presets, drift = 0.02, clampEdges = true, bottomShade = true, style,
}) => {
  const fr = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const P = { ...DEFAULT_PRESETS, ...presets } as PersonPresets;
  const t = offset + fr / fps;
  let cam = camAt(t, keys, subject, P);
  cam = { ...cam, zoom: cam.zoom * interpolate(fr, [0, durationInFrames], [1, 1 + drift], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) };
  if (clampEdges) cam = clampCam(cam);
  const tx = (cam.pos.x - cam.zoom * cam.focus.x) * 100;
  const ty = (cam.pos.y - cam.zoom * cam.focus.y) * 100;
  return <AbsoluteFill style={{ overflow: "hidden", ...style }}>
    <OffthreadVideo muted src={toSrc(src)} startFrom={Math.round(offset * fps)}
      style={{ position: "absolute", left: 0, top: 0, width: "100%", height: "100%", objectFit: "cover", transformOrigin: "0 0", transform: `translate(${tx}%, ${ty}%) scale(${cam.zoom})` }} />
    {bottomShade && <AbsoluteFill style={{ background: "linear-gradient(180deg, transparent 78%, rgba(6,9,12,.55) 100%)" }} />}
  </AbsoluteFill>;
};
