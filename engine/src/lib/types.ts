// 镜头表（build/film.json）类型。由 scripts/compile_shotlist.py 从 shotlist.yaml 生成。
// 约定：所有时间 = 整条 A-roll 的绝对秒（成片时间轴 = A-roll 时间轴，B-roll 跟着 A-roll 走）。
export type Pt = { x: number; y: number };
export type Framing = "native" | "wide" | "left" | "right" | "close";
export type Trans = "cut" | "punch" | "whip" | "wipe" | "iris" | "slam" | "sweep";
export type PresetMap = Partial<Record<Exclude<Framing, "native">, { zoom: number; pos: Pt }>>;

/** 面板/全屏卡片里的一行：m=灰色小字 p=胶囊 h=荧光笔 b=大字 x=划线 a=箭头 */
export type Item = { k: "m" | "p" | "h" | "b" | "x" | "a"; t: string; at: number; color?: string; size?: number; strikeAt?: number };
/** B-roll / 人物镜头上的叠字标签 */
export type TagT = { t: string; at: number; color?: string; size?: number; sub?: string };
export type MediaT = { src: string; start?: number; rate?: number; kb?: [number, number]; pos?: string; blur?: number };

export type Chart =
  | { type: "bignum"; at: number; text: string; label?: string; sub?: string; color?: string }
  | { type: "bars"; at: number; title?: string; bars: { label: string; value: number; text: string; color?: string; at?: number }[] }
  | { type: "line"; at: number; title?: string; points: { label: string; value: number; text?: string }[]; color?: string }
  | { type: "compare"; at: number; title?: string; vs?: string;
      left: { title: string; lines: string[]; at?: number; color?: string };
      right: { title: string; lines: string[]; at?: number; color?: string } }
  | { type: "list"; at: number; title?: string; rows: { t: string; at: number; hl?: boolean }[] }
  | { type: "timeline"; at: number; title?: string; marks: { t: string; at: number; color?: string }[] };

export type Shot = {
  id: string; from: number; to: number;
  kind: "person" | "broll" | "card" | "chapter";
  trans?: Trans; sweep?: boolean;
  // person：人物左/右/全景/近景 + 推镜；另一侧放面板（items 或 chart）
  framing?: Framing;
  push?: { at: number; factor: number; dur: number };
  panel?: { items?: Item[]; chart?: Chart };
  // broll：实拍/图片 + 叠字；pip=偶尔的圆形人物小窗
  media?: MediaT; shade?: number;
  pip?: { x: number; y: number; d?: number };
  tags?: TagT[];
  // card：深色底（模糊实拍）+ 居中 items 或 chart
  bg?: MediaT; items?: Item[]; chart?: Chart;
  // chapter：章节卡
  chapter?: { n: string; lines: { t: string; at: number; color?: string }[] };
};

export type Cover = {
  bg?: string; kicker?: string; title: string[]; highlight?: string; lines?: string[]; showSafe?: boolean;
};

export type Film = {
  meta: {
    title: string;              // 左上角栏目条文字（空串=不显示）
    fps: number; width: number; height: number; durationInFrames: number;
    grade?: "navy" | "warm" | "none";
    aiLabel?: string | null;    // 默认 null：不显示 AI 标
    progress?: boolean;         // 顶部全片进度条（默认 true）
  };
  aroll: {
    src: string;                // public 目录内相对路径
    subject: Pt;                // 素材里人物脸部中心（0–1）
    presets?: PresetMap;
    zones?: { from: number; subject?: Pt; presets?: PresetMap }[]; // 不同链机位不同时按时间覆盖
    drift?: number;
  };
  shots: Shot[];
  subs: { s: number; e: number; t: string }[];
  cover?: Cover;
  credits?: { title: string; lines: string[] };
};
