import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming, springTiming } from "@remotion/transitions";
import type { TransitionPresentation, TransitionTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { fade } from "@remotion/transitions/fade";
import { flip } from "@remotion/transitions/flip";
import { clockWipe } from "@remotion/transitions/clock-wipe";
import { iris } from "@remotion/transitions/iris";
import { timeline } from "./data";
import { SceneView } from "./Scene";
import { Captions } from "./Captions";
import { fontHead } from "./fonts";
import { flashCut, sliceBars, zoomThrough } from "./presentations";
import type { Scene, Transition } from "./timeline-types";

const SLIDE_DIR = { left: "from-right", right: "from-left", up: "from-bottom", down: "from-top" } as const;
const WIPE_DIR = { left: "from-right", right: "from-left", up: "from-bottom", down: "from-top" } as const;
const FLIP_DIR = { left: "from-right", right: "from-left", up: "from-bottom", down: "from-top" } as const;

// presentations carry different prop generics; the series only needs the erased shape
type AnyPresentation = TransitionPresentation<Record<string, unknown>>;
const erase = <T extends Record<string, unknown>>(p: TransitionPresentation<T>): AnyPresentation => p as unknown as AnyPresentation;

/** Map a storyboard transition onto an official (or custom) presentation + timing. */
const presentationFor = (tr: Transition, frames: number, width: number, height: number, accent: string): { presentation: AnyPresentation; timing: TransitionTiming } | null => {
  const spring: TransitionTiming = springTiming({ config: { damping: 200 }, durationInFrames: frames, durationRestThreshold: 0.001 });
  const linear: TransitionTiming = linearTiming({ durationInFrames: frames });
  switch (tr.type) {
    case "push":
      return { presentation: erase(slide({ direction: SLIDE_DIR[tr.dir] })), timing: spring };
    case "wipe":
      return { presentation: erase(wipe({ direction: WIPE_DIR[tr.dir] })), timing: linear };
    case "fade":
      return { presentation: erase(fade()), timing: linear };
    case "flip":
      return { presentation: erase(flip({ direction: FLIP_DIR[tr.dir] })), timing: spring };
    case "clock":
      return { presentation: erase(clockWipe({ width, height })), timing: linear };
    case "iris":
      return { presentation: erase(iris({ width, height })), timing: linear };
    case "zoom":
      return { presentation: erase(zoomThrough({ width, height })), timing: spring };
    case "flash":
      return { presentation: erase(flashCut({ width, height })), timing: linear };
    case "slice":
      return { presentation: erase(sliceBars({ width, height, accent })), timing: linear };
    case "none":
      return null;
    default: {
      const never: never = tr.type;
      return never;
    }
  }
};

/**
 * TransitionSeries layout: scene B's clock starts exactly at its first spoken word (timeline start),
 * so sequence A lasts (startB − startA) + τ and the transition occupies [startB, startB + τ].
 */
const layout = (scenes: Scene[], fps: number, total: number) => {
  const startF = scenes.map((s) => Math.round(s.start * fps));
  const tau = scenes.map((s, i) => {
    if (i === 0 || s.transition.type === "none") return 0;
    const base = Math.min(startF[i] - startF[i - 1], (i + 1 < scenes.length ? startF[i + 1] : total) - startF[i]);
    return Math.max(0, Math.min(Math.round(s.transition.dur * fps), base - 2));
  });
  const dur = scenes.map((_, i) => {
    const end = i + 1 < scenes.length ? startF[i + 1] : total;
    return Math.max(1, end - startF[i] + (i + 1 < scenes.length ? tau[i + 1] : 0));
  });
  return { tau, dur };
};

export const Reel: React.FC = () => {
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const tl = timeline;
  const style = tl.style;
  const { tau, dur } = layout(tl.scenes, fps, durationInFrames);

  const series: React.ReactNode[] = [];
  tl.scenes.forEach((scene, i) => {
    if (i > 0 && tau[i] > 0) {
      const pt = presentationFor(scene.transition, tau[i], width, height, style.accent);
      if (pt) series.push(<TransitionSeries.Transition key={`tr-${scene.id}`} presentation={pt.presentation} timing={pt.timing} />);
    }
    series.push(
      <TransitionSeries.Sequence key={scene.id} durationInFrames={dur[i]}>
        <SceneView scene={scene} />
      </TransitionSeries.Sequence>,
    );
  });

  return (
    <AbsoluteFill style={{ background: style.bg, fontFamily: fontHead, color: style.ink }}>
      <TransitionSeries>{series}</TransitionSeries>

      <Captions words={tl.words} cfg={tl.captions_cfg} style={style} />

      <Audio src={staticFile("vo.mp3")} />
      {tl.bgm ? <Audio src={staticFile(tl.bgm.src)} volume={() => tl.bgm?.vol ?? 0.35} /> : null}
      {tl.sfx.map((hit, i) => {
        const len = Math.min(hit.len, Math.max(0.2, tl.duration - hit.t));
        return (
          <Sequence key={`sfx-${i}`} from={Math.round(hit.t * fps)} durationInFrames={Math.max(1, Math.round(len * fps))} layout="none">
            <Audio src={staticFile(`audio/${hit.name}.mp3`)} volume={() => hit.vol} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
