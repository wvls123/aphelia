// Custom transition presentations (official @remotion/transitions extension API) for effects the
// stock presentations don't cover: zoom-through, white flash cut, sliced bars.
import React from "react";
import { AbsoluteFill } from "remotion";
import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";

type Props = { width: number; height: number; accent?: string };

const Zoom: React.FC<TransitionPresentationComponentProps<Props>> = ({ children, presentationDirection, presentationProgress }) => {
  const p = presentationProgress;
  const style: React.CSSProperties =
    presentationDirection === "exiting"
      ? { transform: `scale(${1 + 0.6 * p})`, opacity: 1 - p, transformOrigin: "50% 50%" }
      : { transform: `scale(${0.72 + 0.28 * p})`, opacity: p, transformOrigin: "50% 50%" };
  return <AbsoluteFill style={style}>{children}</AbsoluteFill>;
};

const Flash: React.FC<TransitionPresentationComponentProps<Props>> = ({ children, presentationDirection, presentationProgress }) => {
  const p = presentationProgress;
  // hard cut at 30 % of the transition, white flash peaks there and decays
  const showEntering = p >= 0.3;
  const visible = presentationDirection === "entering" ? showEntering : !showEntering;
  const flash = p < 0.3 ? p / 0.3 : Math.max(0, 1 - (p - 0.3) / 0.7);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ opacity: visible ? 1 : 0 }}>{children}</AbsoluteFill>
      {presentationDirection === "entering" ? <AbsoluteFill style={{ background: "#fff", opacity: flash, pointerEvents: "none" }} /> : null}
    </AbsoluteFill>
  );
};

const Slice: React.FC<TransitionPresentationComponentProps<Props>> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const p = presentationProgress;
  const bars = 6;
  const { width, height, accent } = passedProps;
  if (presentationDirection === "exiting") return <AbsoluteFill>{children}</AbsoluteFill>;
  // entering scene revealed under accent bars that sweep left→right with a stagger
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ opacity: p >= 0.45 ? 1 : 0 }}>{children}</AbsoluteFill>
      {Array.from({ length: bars }, (_, k) => {
        const local = Math.min(1, Math.max(0, (p - k * 0.06) / 0.7));
        const eased = local < 0.5 ? 4 * local ** 3 : 1 - Math.pow(-2 * local + 2, 3) / 2;
        const x = -width + eased * width * 2.15;
        return <div key={k} style={{ position: "absolute", left: 0, top: (k * height) / bars, width, height: height / bars + 2, background: accent ?? "#C8FF3D", transform: `translateX(${x}px)` }} />;
      })}
    </AbsoluteFill>
  );
};

export const zoomThrough = (props: Props): TransitionPresentation<Props> => ({ component: Zoom, props });
export const flashCut = (props: Props): TransitionPresentation<Props> => ({ component: Flash, props });
export const sliceBars = (props: Props): TransitionPresentation<Props> => ({ component: Slice, props });
