import React from "react";
import { spring } from "remotion";
import type { CustomLayerProps } from "../timeline-types";
import { fontHand } from "../fonts";

/**
 * Reference custom layer: a hand-drawn "NEW" badge that springs in and wobbles.
 * Storyboard usage: { "type": "custom", "component": "ExampleBadge", "x": 700, "y": 300, "at_word": "новый",
 *                     "props": { "text": "НОВОЕ", "size": 120 } }
 * Contract: read `now` (absolute seconds), start at `t`, colours from `pal`, anything else from `layer.props`.
 */
export const ExampleBadge: React.FC<CustomLayerProps> = ({ now, t, pal, layer, fps }) => {
  if (now < t) return null;
  const text = String(layer.props.text ?? "NEW");
  const size = Number(layer.props.size ?? 120);
  const s = spring({ frame: (now - t) * fps, fps, config: { damping: 9, stiffness: 160, mass: 0.7 } });
  const wobble = Math.sin((now - t) * 6) * 4;
  return (
    <div
      style={{
        position: "absolute",
        left: layer.x,
        top: layer.y,
        width: size * 1.6,
        height: size * 1.6,
        borderRadius: "50%",
        background: pal.accent,
        border: `8px solid ${pal.ink}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: fontHand,
        fontSize: size * 0.42,
        color: pal.ink,
        textTransform: "uppercase",
        transform: `scale(${s}) rotate(${-12 + wobble}deg)`,
        transformOrigin: "center",
      }}
    >
      {text}
    </div>
  );
};
