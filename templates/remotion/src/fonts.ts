import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadNeucha } from "@remotion/google-fonts/Neucha";

const inter = loadInter("normal", {
  weights: ["700", "800", "900"],
  subsets: ["latin", "latin-ext", "cyrillic", "cyrillic-ext"],
});

const neucha = loadNeucha("normal", {
  weights: ["400"],
  subsets: ["latin", "cyrillic"],
});

export const fontHead = inter.fontFamily;
export const fontHand = neucha.fontFamily;
