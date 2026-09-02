import "./index.css";
import { Composition } from "remotion";
import { timeline } from "./data";
import { Reel } from "./Reel";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Reel"
      component={Reel}
      durationInFrames={Math.round(timeline.duration * timeline.fps)}
      fps={timeline.fps}
      width={timeline.width}
      height={timeline.height}
    />
  );
};
