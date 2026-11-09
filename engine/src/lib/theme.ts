import type React from "react";
import { Easing, continueRender, delayRender, staticFile } from "remotion";

// 海军蓝 / 青色主题（与「专业场景」A-roll 对齐）。禁止粉色丝印风。
export const CYAN = "#5FD3C9", AMBER = "#E8B060", INK = "#F2F5F4", MUTE = "rgba(242,245,244,.62)", BAD = "#E07A5F", GOOD = "#4CD38F";
export const BG = "#070a0c";
export const FONT_FAMILY = "XLSans";
export const FONT = `"${FONT_FAMILY}","Noto Sans CJK SC","Noto Sans SC","Source Han Sans SC","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif`;
export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const eo = { ...clamp, easing: Easing.out(Easing.cubic) };

export const big: React.CSSProperties = { fontFamily: FONT, fontWeight: 700, color: INK, textShadow: "0 8px 40px rgba(0,0,0,.6)" };

/** public 内相对路径 → URL（http/https 原样） */
export const src = (p: string) => (/^(https?:)?\/\//.test(p) ? p : staticFile(p.replace(/^\/+/, "")));
export const isImage = (p: string) => /\.(jpe?g|png|webp|gif|avif)$/i.test(p);

// 字体：install.sh 把 Noto Sans SC（SIL OFL）放进 engine/public/fonts，init_project 复制到项目 public/fonts。
// 缺字体文件时 load 失败也继续渲染（回落系统 CJK 字体）。
let fontsRequested = false;
export const ensureFonts = () => {
  if (fontsRequested || typeof document === "undefined" || typeof FontFace === "undefined") return;
  fontsRequested = true;
  const h = delayRender("load CJK fonts", { timeoutInMilliseconds: 30000 });
  const faces: [string, string][] = [["fonts/NotoSansSC-Bold.otf", "700"], ["fonts/NotoSansSC-Black.otf", "900"]];
  Promise.allSettled(faces.map(([f, w]) => new FontFace(FONT_FAMILY, `url('${staticFile(f)}')`, { weight: w }).load().then((ff) => { (document.fonts as unknown as { add: (f: FontFace) => void }).add(ff); })))
    .then(() => continueRender(h));
};
