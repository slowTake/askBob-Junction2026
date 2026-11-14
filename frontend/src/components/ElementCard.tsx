import type { ElementInfo } from "../api/types";
import { describe } from "../lib/planLayer";

interface Props {
  element: ElementInfo | null; // the pinned element, else the last one pointed at
  pinned: boolean;
  onClose: () => void;
  onAsk: () => void;
}

/**
 * What the plan knows about an element, in a fixed bar under the plan. The bar is always
 * there with the same height: pointing at another room only changes its text, and it
 * keeps the last room when the cursor crosses a wall, so nothing pops in and out.
 */
export function ElementCard({ element, pinned, onClose, onAsk }: Props) {
  if (element === null) {
    return (
      <div className="element-bar" role="status">
        <span className="hint">
          Point at a room to see its name and area. Click it to select it and ask about it.
        </span>
      </div>
    );
  }
  const { title, details } = describe(element);
  const kind = element.kind.replaceAll("_", " ");
  return (
    <div className={`element-bar${pinned ? " is-pinned" : ""}`} role="status">
      <span className="kind-tag">{kind}</span>
      <strong className="element-title">{title}</strong>
      <span className="element-details">{details.join(" · ")}</span>
      {pinned ? (
        <>
          <button type="button" className="btn btn-primary btn-sm" onClick={onAsk}>
            Ask about this {kind}
          </button>
          <button type="button" className="icon-btn" aria-label="Deselect" onClick={onClose}>
            ×
          </button>
        </>
      ) : (
        <span className="hint">Click to select</span>
      )}
    </div>
  );
}
