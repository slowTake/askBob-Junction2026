import { useId, useMemo, type CSSProperties, type ReactNode } from "react";
import type {
  ElementInfo,
  PlanLabel as PlanLabelData,
  PlanPath,
  PlanView,
  RedrawConfidence,
} from "../api/types";
import type { BBox, Camera } from "../lib/camera";
import { markPoints } from "../lib/confidence";
import type { LayerKey } from "../lib/planLayer";
import { readingOrder, type TargetOnPage } from "../lib/target";
import { PlanLayer } from "./PlanLayer";
import { highlightColors } from "../lib/highlightColors";

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
  onError: () => void;
  /** The redrawn page (#82), drawn over the image and under the same overlay. */
  redraw: ReactNode | null;
  /** The redraw's missed and added patches (#132), lit while the breakdown is open. */
  marks: RedrawConfidence | null;
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
  const colors = useMemo(() => highlightColors(props.elements), [props.elements]);
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
        onError={props.onError}
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
          highlightColors={colors}
          selectedIds={props.selectedIds}
          onHover={props.onHover}
          onSelect={props.onSelect}
        />
        {props.marks && <ConfidenceMarks marks={props.marks} />}
        {shown?.spotlight && (
          <Spotlight
            box={shown.spotlight}
            polygon={shown.spotlightPolygon}
            pad={SPOTLIGHT_PAD_PX * u}
            width={width}
            height={height}
          />
        )}
        {shown?.path && <RoutePath path={shown.path} u={u} />}
        {shown?.line && <MeasureLine line={shown.line} u={u} />}
        {shown?.labels.map((label, i) => (
          <PlanText key={i} label={label} u={u} />
        ))}
        {numbered.map((el, i) => (
          <Badge key={el.id} box={el.bbox as BBox} n={i + 1} u={u} color={colors.get(el.id)} />
        ))}
      </svg>
    </div>
  );
}

/** Ink the redraw missed, and redraw on blank paper, outlined as citations are. */
function ConfidenceMarks({ marks }: { marks: RedrawConfidence }) {
  const patches = (list: RedrawConfidence["missed"], kind: "missed" | "added") =>
    list.map((mark, i) => {
      const points = markPoints(mark);
      return points ? (
        <polygon key={`${kind}:${i}`} points={points} className={`confidence-mark is-${kind}`} />
      ) : null;
    });
  return (
    <g className="confidence-marks">
      {patches(marks.missed, "missed")}
      {patches(marks.added, "added")}
    </g>
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

/** A walked route: the line, a dot where it starts, an arrowhead where it arrives. */
function RoutePath({ path, u }: { path: PlanPath; u: number }) {
  const pts = path.points;
  if (pts.length < 2) return null;
  const [ex, ey] = pts[pts.length - 1];
  const [px, py] = pts[pts.length - 2];
  const angle = (Math.atan2(ey - py, ex - px) * 180) / Math.PI;
  const mid = pts[Math.floor((pts.length - 1) / 2)];
  const next = pts[Math.floor((pts.length - 1) / 2) + 1];
  return (
    <g className="route">
      <polyline points={pts.map((p) => p.join(",")).join(" ")} strokeLinejoin="round" />
      <circle cx={pts[0][0]} cy={pts[0][1]} r={5 * u} />
      <path
        d={`M 0 0 L ${-14 * u} ${-7 * u} L ${-14 * u} ${7 * u} Z`}
        transform={`translate(${ex} ${ey}) rotate(${angle})`}
      />
      <text x={(mid[0] + next[0]) / 2} y={(mid[1] + next[1]) / 2 - 10 * u} fontSize={14 * u}>
        {path.label}
      </text>
    </g>
  );
}

/** Text over the plan, e.g. an apartment's area at its centre. */
function PlanText({ label, u }: { label: PlanLabelData; u: number }) {
  return (
    <text className="plan-text" x={label.at[0]} y={label.at[1]} fontSize={16 * u}>
      {label.text}
    </text>
  );
}

function Badge({ box, n, u, color }: { box: BBox; n: number; u: number; color?: string }) {
  return (
    <g
      className="plan-badge"
      transform={`translate(${box[0]} ${box[1]})`}
      style={{ "--highlight-color": color } as CSSProperties}
    >
      <circle r={9 * u} />
      <text fontSize={11 * u} dy={4 * u}>
        {n}
      </text>
    </g>
  );
}
