import { useId, type CSSProperties } from "react";
import type { ElementInfo, PlanView } from "../api/types";
import type { BBox, Camera } from "../lib/camera";
import type { LayerKey } from "../lib/planLayer";
import { readingOrder, type TargetOnPage } from "../lib/target";
import { PlanLayer } from "./PlanLayer";

interface Props {
  src: string;
  alt: string;
  width: number;
  height: number;
  camera: Camera;
  animated: boolean;
  elements: ElementInfo[];
  layers: Set<LayerKey>;
  highlighted: Set<string>;
  shown: TargetOnPage | null;
  selectedId: string | null;
  onHover: (el: ElementInfo | null) => void;
  onSelect: (el: ElementInfo | null) => void;
  onLoad: () => void;
}

const SPOTLIGHT_PAD_PX = 10;

/**
 * The page image and its overlay, moved by one CSS transform. Overlay sizes that should
 * look the same at every zoom (lines, badges, labels) are multiplied by `u`, one screen
 * pixel in page pixels; the stylesheet reads it as the --u custom property.
 */
export function PlanCanvas(props: Props) {
  const { camera, width, height, shown } = props;
  const u = 1 / camera.scale;
  const numbered =
    shown && shown.highlightIds.length > 1 ? readingOrder(props.elements, props.highlighted) : [];
  return (
    <div
      className={`plan-sheet${props.animated ? " is-animated" : ""}`}
      style={{
        width,
        height,
        transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})`,
      }}
    >
      <img
        src={props.src}
        alt={props.alt}
        width={width}
        height={height}
        draggable={false}
        onLoad={props.onLoad}
      />
      <svg
        className="sheet-overlay"
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        style={{ "--u": u } as CSSProperties}
        onClick={() => props.onSelect(null)}
      >
        <PlanLayer
          elements={props.elements}
          visible={props.layers}
          highlighted={props.highlighted}
          selectedId={props.selectedId}
          onHover={props.onHover}
          onSelect={props.onSelect}
        />
        {shown?.spotlight && (
          <Spotlight
            box={shown.spotlight}
            pad={SPOTLIGHT_PAD_PX * u}
            width={width}
            height={height}
          />
        )}
        {shown?.line && <MeasureLine line={shown.line} u={u} />}
        {numbered.map((el, i) => (
          <Badge key={el.id} box={el.bbox as BBox} n={i + 1} u={u} />
        ))}
      </svg>
    </div>
  );
}

function Spotlight(props: { box: BBox; pad: number; width: number; height: number }) {
  const { box, pad, width, height } = props;
  const mask = useId();
  const ring = {
    x: box[0] - pad,
    y: box[1] - pad,
    width: box[2] - box[0] + 2 * pad,
    height: box[3] - box[1] + 2 * pad,
  };
  return (
    <g className="spotlight">
      <defs>
        <mask id={mask}>
          <rect width={width} height={height} fill="white" />
          <rect {...ring} fill="black" />
        </mask>
      </defs>
      <rect width={width} height={height} className="spotlight-dim" mask={`url(#${mask})`} />
      <rect {...ring} className="spotlight-ring" />
    </g>
  );
}

function MeasureLine({ line, u }: { line: NonNullable<PlanView["line"]>; u: number }) {
  const [x1, y1] = line.from;
  const [x2, y2] = line.to;
  return (
    <g className="measure">
      <line x1={x1} y1={y1} x2={x2} y2={y2} />
      <circle cx={x1} cy={y1} r={4 * u} />
      <circle cx={x2} cy={y2} r={4 * u} />
      <text x={(x1 + x2) / 2} y={(y1 + y2) / 2} fontSize={14 * u}>
        {line.label}
      </text>
    </g>
  );
}

function Badge({ box, n, u }: { box: BBox; n: number; u: number }) {
  return (
    <g className="plan-badge" transform={`translate(${box[0]} ${box[1]})`}>
      <circle r={9 * u} />
      <text fontSize={11 * u} dy={4 * u}>
        {n}
      </text>
    </g>
  );
}
