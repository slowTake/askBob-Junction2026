import { memo } from "react";
import type { CleanSheet as Sheet, ScaleBar } from "../lib/redraw";
import type { SketchSheet } from "../lib/sketchSheet";

interface Props {
  sheet: Sheet;
  width: number;
  height: number;
  bar: ScaleBar | null;
}

/**
 * The redrawn page (#82): same viewBox as the page image and drawn under the same overlay,
 * so citations, highlights and the plan layer fit both views. Memoised: panning must not
 * redraw hundreds of shapes.
 */
export const CleanSheet = memo(function CleanSheet({ sheet, width, height, bar }: Props) {
  const added = (yes: boolean) => (yes ? " is-added" : "");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className="clean-sheet"
      aria-hidden="true"
    >
      <rect width={width} height={height} className="clean-bg" />
      {sheet.rooms.map((r) =>
        r.points ? (
          <polygon key={r.id} points={r.points} className={`clean-room${added(r.added)}`} />
        ) : null,
      )}
      {sheet.walls.map((w) => (
        <polygon key={w.id} points={w.points} className={`clean-wall${added(w.added)}`} />
      ))}
      {sheet.fixtures.map((f) => (
        <polygon key={f.id} points={f.points} className={`clean-fixture${added(f.added)}`} />
      ))}
      {sheet.openings.map((o) => {
        const cls = `clean-${o.kind}${added(o.added)}`;
        if (o.leaf && o.arc) {
          return (
            <g key={o.id} className={cls}>
              <path d={o.leaf} className="clean-leaf" />
              <path d={o.arc} className="clean-arc" />
            </g>
          );
        }
        if (o.frame) return <polygon key={o.id} points={o.frame} className={cls} />;
        if (o.gap) return <path key={o.id} d={o.gap} className={`clean-gap${added(o.added)}`} />;
        return (
          <rect key={o.id} x={o.x} y={o.y} width={o.width} height={o.height} className={cls} />
        );
      })}
      {sheet.labels.map((l) => (
        <text key={l.id} x={l.x} y={l.y} fontSize={l.size} className={`clean-text clean-${l.kind}`}>
          {l.text}
        </text>
      ))}
      {sheet.rooms.map((r) => (
        <g key={r.id}>
          <text x={r.x} y={r.y} fontSize={r.size} className="clean-text clean-room-name">
            {r.name}
          </text>
          {r.area && (
            <text x={r.x} y={r.areaY} fontSize={r.areaSize} className="clean-text clean-room-area">
              {r.area}
            </text>
          )}
        </g>
      ))}
      {bar && (
        <g className="clean-scale">
          <path
            d={`M${bar.x} ${bar.y}h${bar.length}M${bar.x} ${bar.y - bar.size / 2}v${bar.size}M${bar.x + bar.length} ${bar.y - bar.size / 2}v${bar.size}`}
            strokeWidth={bar.size / 8}
          />
          <text x={bar.x + bar.length + bar.size} y={bar.y} fontSize={bar.size}>
            {bar.label} · redrawn from extracted elements
          </text>
        </g>
      )}
    </svg>
  );
});

interface SketchProps {
  sheet: SketchSheet;
  width: number;
  height: number;
}

/**
 * The redrawn sketch (#82): the model's plan only, drawn from the shapes the server
 * rendered for the model's own check. Same viewBox as the page image, so the overlay fits.
 * No scale bar and no areas: a sketch has no scale.
 */
export const SketchSheetSvg = memo(function SketchSheetSvg({ sheet, width, height }: SketchProps) {
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className="clean-sheet is-sketch"
      aria-hidden="true"
    >
      <rect width={width} height={height} className="clean-bg" />
      {sheet.walls.map((w) =>
        w.pieces.map((points, i) => (
          <polygon key={`${w.id}:${i}`} points={points} className="clean-wall sketch-wall" />
        )),
      )}
      {sheet.windows.map((w) =>
        w.lines.map((points, i) => (
          <polyline key={`${w.id}:${i}`} points={points} className="sketch-window" />
        )),
      )}
      {sheet.doors.map((d) => (
        <g key={d.id}>
          <polyline points={d.leaf} className="sketch-leaf" />
          <polyline points={d.arc} className="sketch-arc" />
        </g>
      ))}
      {sheet.rooms.map((r) => (
        <text key={r.id} x={r.x} y={r.y} fontSize={r.size} className="clean-text clean-room-name">
          {r.name}
        </text>
      ))}
      {sheet.texts.map((t) => (
        <text key={t.id} x={t.x} y={t.y} fontSize={t.size} className="clean-text">
          {t.text}
        </text>
      ))}
    </svg>
  );
});
