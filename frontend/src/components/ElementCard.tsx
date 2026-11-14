import type { ElementInfo } from "../api/types";
import { describe } from "../lib/planLayer";

interface Props {
  element: ElementInfo;
  pinned: boolean;
  onClose: () => void;
}

/** What the plan knows about the hovered or selected element. */
export function ElementCard({ element, pinned, onClose }: Props) {
  const { title, details } = describe(element);
  return (
    <div className="element-card" role="status">
      <span className="kind-tag">{element.kind.replace("_", " ")}</span>
      <strong>{title}</strong>
      <span className="body-sm muted">{details.join(" · ")}</span>
      {pinned && (
        <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>
          ×
        </button>
      )}
    </div>
  );
}
