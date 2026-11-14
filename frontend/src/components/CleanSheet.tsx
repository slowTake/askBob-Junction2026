import type { CleanSheet as Sheet, ScaleBar } from "../lib/redraw";

interface Props {
  sheet: Sheet;
  width: number;
  height: number;
  bar: ScaleBar | null;
  pageNumber: number;
}

/** The clean redraw's base layer. Same viewBox as the page image, so the overlay fits both. */
export function CleanSheet({ sheet, width, height, bar, pageNumber }: Props) {
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="clean-sheet"
      style={{ aspectRatio: `${width} / ${height}` }}
      role="img"
      aria-label={`Clean redraw of page ${pageNumber}`}
    >
      <rect width={width} height={height} className="clean-bg" />
      {sheet.rooms.map((r) =>
        r.points ? <polygon key={r.id} points={r.points} className="clean-room" /> : null,
      )}
      {sheet.walls.map((w) => (
        <rect key={w.id} x={w.x} y={w.y} width={w.width} height={w.height} className="clean-wall" />
      ))}
      {sheet.labels.map((l) => (
        <text key={l.id} x={l.x} y={l.y} fontSize={l.size} className={`clean-text clean-${l.kind}`}>
          {l.text}
        </text>
      ))}
      {sheet.rooms.map((r) => (
        <g key={r.id} className="clean-room-label">
          <title>{r.title}</title>
          <text x={r.x} y={r.y} fontSize={r.size} className="clean-room-name">
            {r.name}
          </text>
          {r.area && (
            <text x={r.x} y={r.areaY} fontSize={r.areaSize} className="clean-room-area">
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
}
