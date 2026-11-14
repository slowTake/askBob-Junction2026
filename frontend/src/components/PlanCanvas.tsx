import { useId, type CSSProperties, type ReactNode } from "react";
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
  selectedIds: ReadonlySet<string>;
  onHover: (el: ElementInfo | null) => void;
  onSelect: (el: ElementInfo | null, additive: boolean) => void; // null: the empty plan
  onLoad: () => void;
  /** The redrawn page (#82), drawn over the image and under the same overlay. */
  redraw: ReactNode | null;
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
      className={`plan-sheet${props.animated ? " is-animated" : ""}${props.redraw ? " is-redrawn" : ""}`}
      style={{
        width,
        height,
        transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})`,
        ["--u" as string]: u, // read by the overlay and the redraw
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
      {props.redraw}
      <svg
        className="sheet-overlay"
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        style={{ "--u": u } as CSSProperties}
        onClick={(e) => props.onSelect(null, e.shiftKey)}
      >
        <PlanLayer
          elements={props.elements}
          visible={props.layers}
          highlighted={props.highlighted}
          selectedIds={props.selectedIds}
          onHover={props.onHover}
          onSelect={props.onSelect}
        />
        {shown?.spotlight && (
          <Spotlight
            box={shown.spotlight}
            polygon={shown.spotlightPolygon}
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

interface SpotlightProps {
  box: BBox;
  polygon: number[][] | null; // a room's outline: cut out exactly, so neighbours stay dimmed
  pad: number;
  width: number;
  height: number;
}

function Spotlight({ box, polygon, pad, width, height }: SpotlightProps) {
  const mask = useId();
  const points = polygon?.map((p) => p.join(",")).join(" ");
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
          {points ? <polygon points={points} fill="black" /> : <rect {...ring} fill="black" />}
        </mask>
      </defs>
      <rect width={width} height={height} className="spotlight-dim" mask={`url(#${mask})`} />
      {points ? (
        <polygon points={points} className="spotlight-ring" strokeLinejoin="round" />
      ) : (
        <rect {...ring} className="spotlight-ring" />
      )}
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
