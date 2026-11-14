import { memo } from "react";
import type { CleanSheet as Sheet, ScaleBar } from "../lib/redraw";

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
      {sheet.openings.map((o) => (
        <rect
          key={o.id}
          x={o.x}
          y={o.y}
          width={o.width}
          height={o.height}
          className={`clean-${o.kind}${added(o.added)}`}
        />
      ))}
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
