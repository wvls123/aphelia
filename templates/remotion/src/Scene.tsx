import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { CameraMotionBlur } from "@remotion/motion-blur";
import { noise2D } from "@remotion/noise";
import type { CameraKey, Scene } from "./timeline-types";
import { expoOut, linear, mix, power1InOut, prog, yoyo } from "./ease";
import { HUD_TYPES, LayerView } from "./layers";

interface CamState {
  x: number;
  y: number;
  scale: number;
}

const camProps = (k: CameraKey): CamState => ({ x: 540 - k.x * k.zoom, y: 960 - k.y * k.zoom, scale: k.zoom });

const mixCam = (a: CamState, b: CamState, p: number): CamState => ({ x: mix(a.x, b.x, p), y: mix(a.y, b.y, p), scale: mix(a.scale, b.scale, p) });

/** Camera state at absolute time `now`: smooth keys ease between each other, crash keys hit 0.22 s before the word. */
export const cameraAt = (cam: CameraKey[], now: number, sceneEnd: number): CamState => {
  let state = camProps(cam[0]);
  for (let i = 1; i < cam.length; i++) {
    const prev = cam[i - 1];
    const k = cam[i];
    if (k.ease === "crash") {
      const d = 0.22;
      state = mixCam(state, camProps(k), prog(now, Math.max(prev.t, k.t - d), d, expoOut));
    } else {
      const d = Math.max(0.3, k.t - prev.t);
      state = mixCam(state, camProps(k), prog(now, prev.t, d, power1InOut));
    }
  }
  const last = cam[cam.length - 1];
  if (sceneEnd - last.t > 0.9) {
    const z2 = last.zoom * 1.03;
    state = mixCam(state, { x: 540 - last.x * z2, y: 960 - last.y * z2, scale: z2 }, prog(now, last.t + 0.05, sceneEnd - last.t - 0.05, linear));
  }
  return state;
};

/** Impact shake: 6 legs × 0.045 s. */
const shakeAt = (cam: CameraKey[], now: number): { x: number; y: number } => {
  let x = 0;
  let y = 0;
  for (const k of cam) {
    if (k.shake > 0 && now >= k.t && now < k.t + 0.28) {
      const j = yoyo(now, k.t, 0.045, 6, linear);
      x += k.shake * j;
      y += -k.shake * 0.6 * j;
    }
  }
  return { x, y };
};

/** Reads the frame itself so CameraMotionBlur's sub-frame offsets reach the camera math. */
const Stage: React.FC<{ scene: Scene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const now = scene.start + frame / fps;
  const pal = scene.palette;
  const cam = cameraAt(scene.camera, now, scene.end);
  const shake = shakeAt(scene.camera, now);
  // handheld: coherent noise drift, deterministic per scene id
  const hx = scene.handheld ? noise2D(scene.id, now * 0.35, 0) * scene.handheld : 0;
  const hy = scene.handheld ? noise2D(scene.id + "y", 0, now * 0.35) * scene.handheld : 0;
  const stage = scene.layers.filter((l) => !HUD_TYPES.has(l.type));
  return (
    <AbsoluteFill style={{ transform: `translate(${shake.x + hx}px, ${shake.y + hy}px)` }}>
      <div style={{ position: "absolute", inset: 0, transformOrigin: "0 0", transform: `translate(${cam.x}px, ${cam.y}px) scale(${cam.scale})` }}>
        <div
          style={{
            position: "absolute",
            left: -1000,
            top: -1000,
            width: 3080,
            height: 3920,
            backgroundImage: `radial-gradient(${pal.grid} 2.2px, transparent 2.6px)`,
            backgroundSize: "48px 48px",
            opacity: 0.9,
          }}
        />
        {stage.map((l, i) => (
          <LayerView key={i} l={l} pal={pal} now={now} sceneStart={scene.start} sceneEnd={scene.end} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

export const SceneView: React.FC<{ scene: Scene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const now = scene.start + frame / fps;
  const pal = scene.palette;
  const hud = scene.layers.filter((l) => HUD_TYPES.has(l.type));
  const inBlurWindow = scene.motion_blur && scene.camera.some((k) => (k.ease === "crash" || k.shake > 0) && now >= k.t - 0.3 && now <= k.t + 0.4);

  return (
    <AbsoluteFill style={{ background: pal.bg, overflow: "hidden" }}>
      {inBlurWindow ? (
        <CameraMotionBlur shutterAngle={200} samples={5}>
          <Stage scene={scene} />
        </CameraMotionBlur>
      ) : (
        <Stage scene={scene} />
      )}
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        {hud.map((l, i) => (
          <LayerView key={i} l={l} pal={pal} now={now} sceneStart={scene.start} sceneEnd={scene.end} />
        ))}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
