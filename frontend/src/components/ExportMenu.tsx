import { useCallback, useRef, useState } from "react";
import { useDismiss } from "../hooks/useDismiss";

/** What the plan viewer can export while the redrawn sheet is on screen. */
export interface SheetExport {
  download: () => void; // the sheet as a standalone SVG file
  print: () => void; // only the sheet, fitted to the paper
}

/** What the Export menu offers for the open document. */
export interface Exports {
  ifcUrl: string | null; // null: this document has no IFC
  sheet: SheetExport | null; // null: no redrawn sheet on screen
}

interface Props {
  exports: Exports;
  /** "bar": in the app bar, opens downward. "panel": the documents panel's footer, opens upward. */
  variant: "bar" | "panel";
}

/** One menu for everything that leaves the app: the IFC model, the redrawn sheet as SVG,
 * and a print of it. SVG and Print stay greyed out until the redrawn sheet is on screen.
 * A click outside or Esc closes it. */
export function ExportMenu({ exports, variant }: Props) {
  const { ifcUrl, sheet } = exports;
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(root, close, open);

  const run = (action: () => void) => () => {
    close();
    action();
  };

  return (
    <div className={`export-menu is-${variant}`} ref={root}>
      <button
        type="button"
        className={variant === "bar" ? "btn btn-bar" : "btn btn-secondary btn-sm"}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        Export
        <svg className="export-caret" viewBox="0 0 10 6" aria-hidden>
          <path d="M0 0h10L5 6z" />
        </svg>
      </button>
      {open && (
        <div className="export-list" role="menu">
          {ifcUrl ? (
            <a className="export-item" role="menuitem" href={ifcUrl} onClick={close}>
              Download IFC
            </a>
          ) : (
            <span className="export-item" role="menuitem" aria-disabled="true">
              Download IFC
            </span>
          )}
          <button
            type="button"
            className="export-item"
            role="menuitem"
            disabled={!sheet}
            onClick={sheet ? run(sheet.download) : undefined}
          >
            Download SVG
          </button>
          <button
            type="button"
            className="export-item"
            role="menuitem"
            disabled={!sheet}
            onClick={sheet ? run(sheet.print) : undefined}
          >
            Print
          </button>
        </div>
      )}
    </div>
  );
}
