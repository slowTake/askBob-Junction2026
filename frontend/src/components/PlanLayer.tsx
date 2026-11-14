import type { ElementInfo } from "../api/types";
import { drawOrder, layerOf, shapeOf, type LayerKey } from "../lib/planLayer";

interface Props {
  elements: ElementInfo[];
  visible: Set<LayerKey>;
  highlighted: Set<string>; // element ids lit up by the agent or a citation
  selectedId: string | null;
  onHover: (el: ElementInfo | null) => void;
  onSelect: (el: ElementInfo | null) => void;
}

/**
 * The interactive layer over a plan page, in page-pixel coordinates.
 * Rooms are always hoverable (an invisible hit area) even when their layer is hidden,
 * so the plan stays clean but still answers "what is this?".
 */
export function PlanLayer({
  elements,
  visible,
  highlighted,
  selectedId,
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
        if (!shown && layer !== "rooms" && !highlighted.has(el.id)) return null;
        const className = [
          "plan-el",
          `plan-${layer}`,
          shown ? "is-shown" : "is-hit-area",
          highlighted.has(el.id) ? "is-highlighted" : "",
          el.id === selectedId ? "is-selected" : "",
        ].join(" ");
        const handlers = {
          className,
          onMouseEnter: () => onHover(el),
          onMouseLeave: () => onHover(null),
          onClick: (e: React.MouseEvent) => {
            e.stopPropagation();
            onSelect(el.id === selectedId ? null : el);
          },
          vectorEffect: "non-scaling-stroke" as const,
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
}
