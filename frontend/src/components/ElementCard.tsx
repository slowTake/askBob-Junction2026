import type { ElementInfo } from "../api/types";
import { describe } from "../lib/planLayer";

interface Props {
  elements: ElementInfo[]; // the selected elements, else the last one pointed at
  pinned: boolean; // true when `elements` are selected rather than pointed at
  onClose: () => void;
  onAsk: () => void;
}

/**
 * What the plan knows about an element, in a fixed bar under the plan. The bar is always
 * there with the same height: pointing at another room only changes its text, and it
 * keeps the last room when the cursor crosses a wall, so nothing pops in and out.
 * Several elements selected with Shift+click show as a count and their names.
 */
export function ElementCard({ elements, pinned, onClose, onAsk }: Props) {
  if (elements.length === 0) {
    return (
      <div className="element-bar" role="status">
        <span className="hint">
          Point at a room to see its name and area. Click to select it and ask about it; Shift+click
          to select several.
        </span>
      </div>
    );
  }
  if (elements.length > 1) {
    const names = elements.map((e) => describe(e).title).join(" · ");
    return (
      <div className="element-bar is-pinned" role="status">
        <span className="kind-tag">{elements.length} selected</span>
        <strong className="element-title">{names}</strong>
        <span className="element-details" />
        <button type="button" className="btn btn-primary btn-sm" onClick={onAsk}>
          Ask about these {elements.length}
        </button>
        <button type="button" className="icon-btn" aria-label="Deselect all" onClick={onClose}>
          ×
        </button>
      </div>
    );
  }
  const [element] = elements;
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
        <span className="hint">Click to select, Shift+click for more</span>
      )}
    </div>
  );
}
