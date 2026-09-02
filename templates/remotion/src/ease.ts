// GSAP-compatible easing curves so Remotion and HyperFrames move identically.

export type Ease = (p: number) => number;

const clamp01 = (p: number) => (p < 0 ? 0 : p > 1 ? 1 : p);

export const linear: Ease = (p) => clamp01(p);
export const power1InOut: Ease = (p) => {
  p = clamp01(p);
  return p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
};
export const power2Out: Ease = (p) => 1 - Math.pow(1 - clamp01(p), 3);
export const power2InOut: Ease = (p) => {
  p = clamp01(p);
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
};
export const power3Out: Ease = (p) => 1 - Math.pow(1 - clamp01(p), 4);
export const power4Out: Ease = (p) => 1 - Math.pow(1 - clamp01(p), 5);
export const expoOut: Ease = (p) => (p >= 1 ? 1 : p <= 0 ? 0 : 1 - Math.pow(2, -10 * p));
export const sineInOut: Ease = (p) => -(Math.cos(Math.PI * clamp01(p)) - 1) / 2;
export const backOut =
  (overshoot = 1.70158): Ease =>
  (p) => {
    p = clamp01(p) - 1;
    return p * p * ((overshoot + 1) * p + overshoot) + 1;
  };

export const power2In: Ease = (p) => Math.pow(clamp01(p), 3);
export const power3In: Ease = (p) => Math.pow(clamp01(p), 4);
/** gsap elastic.out(1, 0.4) */
export const elasticOut: Ease = (p) => {
  p = clamp01(p);
  if (p === 0 || p === 1) return p;
  const period = 0.4;
  return Math.pow(2, -10 * p) * Math.sin(((p - period / 4) * (2 * Math.PI)) / period) + 1;
};
/** gsap bounce.out */
export const bounceOut: Ease = (p) => {
  p = clamp01(p);
  if (p < 1 / 2.75) return 7.5625 * p * p;
  if (p < 2 / 2.75) return 7.5625 * (p -= 1.5 / 2.75) * p + 0.75;
  if (p < 2.5 / 2.75) return 7.5625 * (p -= 2.25 / 2.75) * p + 0.9375;
  return 7.5625 * (p -= 2.625 / 2.75) * p + 0.984375;
};

/** Progress of a tween that starts at `at` and lasts `dur` seconds, evaluated at time `t`. */
export const prog = (t: number, at: number, dur: number, ease: Ease = linear): number => {
  if (dur <= 0) return t >= at ? 1 : 0;
  return ease((t - at) / dur);
};

export const mix = (a: number, b: number, p: number) => a + (b - a) * p;

/** Yoyo oscillation like gsap `yoyo: true, repeat: n`: 0 → 1 → 0 … over `half` seconds per leg. */
export const yoyo = (t: number, at: number, half: number, legs: number, ease: Ease = sineInOut): number => {
  if (t < at) return 0;
  const leg = Math.floor((t - at) / half);
  if (leg >= legs) return legs % 2 === 0 ? 0 : 1;
  const p = ((t - at) % half) / half;
  return leg % 2 === 0 ? ease(p) : 1 - ease(p);
};
