import { useRef } from "react";
import type { RedrawConfidence } from "../api/types";
import { useDismiss } from "../hooks/useDismiss";
import { confidenceRows, percent } from "../lib/confidence";

interface Props {
  confidence: RedrawConfidence;
  open: boolean;
  onToggle: (open: boolean) => void;
}

/**
 * "Redraw confidence 86%" over the Redrawn view (#132). Clicking it opens the breakdown
 * per part and lights the missed and added patches on the plan (PlanCanvas draws them).
 * A click outside the panel, or Esc, closes it.
 */
export function ConfidenceBadge({ confidence, open, onToggle }: Props) {
  const box = useRef<HTMLDivElement>(null);
  useDismiss(box, () => onToggle(false), open);
  const rows = confidenceRows(confidence);
  return (
    <div className="confidence-badge" ref={box} data-no-pan>
      <button
        type="button"
        className={`btn btn-subtle btn-sm${open ? " is-on" : ""}`}
        aria-expanded={open}
        title="How much of the page's own line work the redraw accounts for"
        onClick={() => onToggle(!open)}
      >
        Redraw confidence {percent(confidence.score)}
      </button>
      {open && (
        <div className="confidence-panel" role="dialog" aria-label="Redraw confidence">
          <p className="body-sm">
            The share of the page&rsquo;s line work the redraw lies on, and of the redraw that lies
            on line work, without an answer key. It cannot tell a wall from a fixture drawn as one,
            or check what a label says.
          </p>
          <ul className="confidence-legend body-sm">
            <li>
              <span className="confidence-swatch is-missed" /> Missed ink{" "}
              {percent(1 - confidence.covered)}
            </li>
            <li>
              <span className="confidence-swatch is-added" /> Added on blank paper{" "}
              {percent(1 - confidence.on_ink)}
            </li>
          </ul>
          <table className="confidence-table body-sm">
            <thead>
              <tr>
                <th scope="col">Part</th>
                <th scope="col">Drawn</th>
                <th scope="col" title="Share of the part that lies on line work">
                  On ink
                </th>
                <th scope="col" title="Share of the page's line work this part lies on">
                  Covers
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <th scope="row">{r.label}</th>
                  <td>{r.count}</td>
                  <td>{r.onInk ?? "–"}</td>
                  <td>{r.covers}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
