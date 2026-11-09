import React from "react";
import { CalculateMetadataFunction, Composition } from "remotion";
import { FilmComp } from "./Film";
import { Cover, Credits } from "./Cover";
import { ensureFonts } from "./lib/theme";
import type { Film } from "./lib/types";

ensureFonts();

// 没传 --props 时（如直接开 Studio）用的占位片：一张 2 秒文字卡
const PLACEHOLDER: Film = {
  meta: { title: "xiaolinshuo engine", fps: 24, width: 1920, height: 1080, durationInFrames: 48, grade: "navy", aiLabel: null, progress: true },
  aroll: { src: "assets/aroll.mp4", subject: { x: 0.5, y: 0.4 } },
  shots: [{ id: "s1", from: 0, to: 2, kind: "card", items: [{ k: "h", t: "用 --props=build/film.json 渲染", at: 0.1 }] }],
  subs: [],
  cover: { kicker: "DEMO", title: ["小Lin说式"], highlight: "横屏口播", lines: ["--props=build/film.json"] },
};

const filmMeta: CalculateMetadataFunction<Film> = ({ props }) => ({
  durationInFrames: Math.max(1, props.meta.durationInFrames), fps: props.meta.fps, width: props.meta.width, height: props.meta.height,
});
const stillMeta = (w: number, h: number, n: number): CalculateMetadataFunction<Film> => ({ props }) => ({ durationInFrames: n, fps: props.meta.fps, width: w, height: h });

export const Root: React.FC = () => <>
  <Composition id="Film" component={FilmComp} defaultProps={PLACEHOLDER} calculateMetadata={filmMeta} fps={24} width={1920} height={1080} durationInFrames={48} />
  <Composition id="CoverH" component={Cover} defaultProps={PLACEHOLDER} calculateMetadata={stillMeta(1920, 1080, 3)} fps={24} width={1920} height={1080} durationInFrames={3} />
  <Composition id="CoverV" component={Cover} defaultProps={PLACEHOLDER} calculateMetadata={stillMeta(1080, 1920, 1)} fps={24} width={1080} height={1920} durationInFrames={1} />
  <Composition id="Credits" component={Credits} defaultProps={PLACEHOLDER} calculateMetadata={stillMeta(1920, 1080, 120)} fps={24} width={1920} height={1080} durationInFrames={120} />
</>;
