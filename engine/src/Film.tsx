// 整片合成：按镜头表逐镜 <Sequence>，外加闪白、外框（全片进度条）、字幕。
// 分段渲染 = 同一合成按 --frames 渲染不同帧段，所以进度条/音乐/时间轴天然连续。
import React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { BG } from "./lib/theme";
import type { Film, Shot } from "./lib/types";
import { Key, PersonLayer } from "./components/PersonLayer";
import { DarkBg, Media, Pip, subjectAt } from "./components/Media";
import { Center, ChapterCard, Chrome, Panel, Subtitle, Tags } from "./components/Panel";
import { ChartView, R } from "./components/Charts";
import { Flash, LightSweep, Shade, SideDim, enter } from "./components/Primitives";

const ShotBody: React.FC<{ film: Film; s: Shot; r: R; d: number }> = ({ film, s, r, d }) => {
  const grade = film.meta.grade ?? "navy";
  switch (s.kind) {
    case "person": {
      const fr = s.framing ?? "wide";
      const { subject, presets } = subjectAt(film, s.from);
      const keys: Key[] = [{ at: s.from, framing: fr }];
      if (s.push) keys.push({ at: s.push.at, framing: fr, push: s.push.factor, trans: "ease", dur: s.push.dur });
      const side = fr === "left" ? "right" : "left";
      const panel = s.panel && (fr === "left" || fr === "right") && (s.panel.items?.length || s.panel.chart);
      return <>
        <PersonLayer src={film.aroll.src} offset={s.from} subject={subject} presets={presets} keys={keys} drift={film.aroll.drift ?? 0.015} />
        {panel ? <><SideDim side={side} /><Panel side={side} items={s.panel!.items} chart={s.panel!.chart} r={r} /></> : null}
        {s.tags?.length ? <Tags tags={s.tags} r={r} x={fr === "left" ? 1060 : fr === "right" ? 140 : 1300} y={280} /> : null}
      </>;
    }
    case "broll": return <>
      {s.media ? <Media m={s.media} dur={d} grade={grade} /> : <DarkBg dur={d} grade={grade} />}
      <Shade k={s.shade ?? 0.45} />
      {s.chart ? <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingBottom: 120 }}><ChartView c={s.chart} r={r} w={1500} h={700} /></AbsoluteFill> : null}
      {s.tags?.length ? <Tags tags={s.tags} r={r} /> : null}
      {s.pip ? <Pip film={film} from={s.from} x={s.pip.x} y={s.pip.y} d={s.pip.d} /> : null}
    </>;
    case "card": return <>
      <DarkBg m={s.bg} dur={d} grade={grade} />
      {s.chart ? <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingBottom: 120 }}><ChartView c={s.chart} r={r} w={1600} h={720} /></AbsoluteFill>
        : s.items?.length ? <Center items={s.items} r={r} /> : null}
      {s.tags?.length ? <Tags tags={s.tags} r={r} /> : null}
      {s.pip ? <Pip film={film} from={s.from} x={s.pip.x} y={s.pip.y} d={s.pip.d} /> : null}
    </>;
    case "chapter": return <ChapterCard n={s.chapter?.n ?? ""} nAt={s.from} lines={s.chapter?.lines ?? []} r={r} bg={s.bg ?? s.media} d={d} grade={grade} />;
    default: return null;
  }
};

const ShotLayer: React.FC<{ film: Film; s: Shot }> = ({ film, s }) => {
  const fr = useCurrentFrame(); const { fps } = useVideoConfig();
  const r: R = (abs) => Math.max(1, Math.round(abs * fps) - Math.round(s.from * fps));
  return <AbsoluteFill>
    <AbsoluteFill style={enter(s.trans ?? "cut", fr)}><ShotBody film={film} s={s} r={r} d={s.to - s.from} /></AbsoluteFill>
    {s.sweep ? <LightSweep /> : null}
  </AbsoluteFill>;
};

export const FilmComp: React.FC<Film> = (film) => {
  const { fps, durationInFrames } = useVideoConfig();
  const F = (t: number) => Math.round(t * fps);
  return <AbsoluteFill style={{ background: BG }}>
    {film.shots.map((s, i) => { const a = F(s.from), b = Math.min(durationInFrames, F(s.to)); return b > a ?
      <Sequence key={s.id ?? i} from={a} durationInFrames={b - a}><ShotLayer film={film} s={s} /></Sequence> : null; })}
    {film.shots.slice(1).filter((s) => (s.trans ?? "cut") !== "cut").map((s, i) =>
      <Sequence key={"fl" + i} from={F(s.from)} durationInFrames={3}><Flash /></Sequence>)}
    <Chrome film={film} />
    <Subtitle subs={film.subs ?? []} />
  </AbsoluteFill>;
};
