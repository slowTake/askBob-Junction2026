import { memo, type CSSProperties } from "react";
import type { ElementInfo } from "../api/types";
import { drawOrder, layerOf, shapeOf, type LayerKey } from "../lib/planLayer";

interface Props {
  elements: ElementInfo[];
  visible: Set<LayerKey>;
  highlighted: Set<string>; // element ids lit up by the agent or a citation
  highlightColors: ReadonlyMap<string, string>;
  selectedIds: ReadonlySet<string>; // keep its identity while it doesn't change (memo)
  onHover: (el: ElementInfo | null) => void;
  onSelect: (el: ElementInfo, additive: boolean) => void; // additive: Shift held
}

/**
 * The interactive layer over a plan page, in page-pixel coordinates.
 * Rooms are always hoverable (an invisible hit area) even when their layer is hidden,
 * so the plan stays clean but still answers "what is this?".
 * Memoised: panning and zooming re-render the page, never these hundreds of shapes.
 */
export const PlanLayer = memo(function PlanLayer({
  elements,
  visible,
  highlighted,
  highlightColors,
  selectedIds,
  onHover,
  onSelect,
}: Props) {
  return (
    <g className="plan-layer">
      {drawOrder(elements).map((el) => {
        const layer = layerOf(el.kind);
        const shape = shapeOf(el);
        if (!layer || !shape) return null;
        const shown = visible.has(layer);
        const lit = highlighted.has(el.id);
        if (!shown && layer !== "rooms" && !lit) return null;
        const className = [
          "plan-el",
          `plan-${layer}`,
          shown ? "is-shown" : "is-hit-area",
          lit ? "is-highlighted" : "",
          selectedIds.has(el.id) ? "is-selected" : "",
        ].join(" ");
        const handlers = {
          className,
          style: lit
            ? ({ "--highlight-color": highlightColors.get(el.id) } as CSSProperties)
            : undefined,
          onMouseEnter: () => onHover(el),
          onMouseLeave: () => onHover(null),
          onClick: (e: React.MouseEvent) => {
            e.stopPropagation();
            onSelect(el, e.shiftKey);
          },
        };
        return shape.type === "polygon" ? (
          <polygon key={el.id} points={shape.points} {...handlers} />
        ) : (
          <rect
            key={el.id}
            x={shape.x}
            y={shape.y}
            width={shape.width}
            height={shape.height}
            {...handlers}
          />
        );
      })}
    </g>
  );
});
