import { LAYERS, type LayerKey } from "../lib/planLayer";
import type { UpscaleInfo } from "../api/types";
import type { SheetMode } from "../lib/redraw";

interface Props {
  pageIndex: number;
  pageCount: number;
  pageLabel: string | null;
  onPage: (index: number) => void;
  layers: Set<LayerKey>;
  onToggleLayer: (key: LayerKey) => void;
  sheet: SheetMode;
  onSheet: (mode: SheetMode) => void;
  upscale: UpscaleInfo | null; // how the page was redrawn, once it was
  onDownload: (() => void) | null; // set while the redrawn sheet is on screen
  onPrint: (() => void) | null;
}

const SHEETS: { mode: SheetMode; label: string }[] = [
  { mode: "original", label: "Original" },
  { mode: "redrawn", label: "Redrawn" },
];

/** Page navigation, Original / Redrawn and layer toggles. Fixed height, so nothing below it ever shifts. */
export function ViewerToolbar(props: Props) {
  const { pageIndex, pageCount, pageLabel, onPage, layers, onToggleLayer, sheet, onSheet } = props;
  return (
    <div className="viewer-toolbar">
      <div className="chip-row">
        <button
          type="button"
          className="btn btn-subtle btn-sm"
          aria-label="Previous page"
          disabled={pageIndex === 0}
          onClick={() => onPage(pageIndex - 1)}
        >
          ‹
        </button>
        <span className="body-sm page-label">
          {pageLabel ? `${pageLabel} · ` : ""}Page {pageIndex + 1} of {pageCount}
        </span>
        <button
          type="button"
          className="btn btn-subtle btn-sm"
          aria-label="Next page"
          disabled={pageIndex >= pageCount - 1}
          onClick={() => onPage(pageIndex + 1)}
        >
          ›
        </button>
      </div>
      <div className="chip-row" role="tablist" aria-label="Page view">
        {SHEETS.map(({ mode, label }) => (
          <button
            key={mode}
            type="button"
            role="tab"
            aria-selected={sheet === mode}
            className={`chip chip-toggle${sheet === mode ? " is-on" : ""}`}
            onClick={() => onSheet(mode)}
          >
            {label}
          </button>
        ))}
        {sheet === "redrawn" && props.upscale && <RedrawNote upscale={props.upscale} />}
        {sheet === "redrawn" && props.onDownload && (
          <button type="button" className="btn btn-subtle btn-sm" onClick={props.onDownload}>
            Download SVG
          </button>
        )}
        {sheet === "redrawn" && props.onPrint && (
          <button type="button" className="btn btn-subtle btn-sm" onClick={props.onPrint}>
            Print
          </button>
        )}
      </div>
      <div className="chip-row" role="group" aria-label="Show on the plan">
        <span className="body-sm muted">Show</span>
        {LAYERS.map((layer) => (
          <button
            key={layer.key}
            type="button"
            aria-pressed={layers.has(layer.key)}
            className={`chip chip-toggle${layers.has(layer.key) ? " is-on" : ""}`}
            onClick={() => onToggleLayer(layer.key)}
          >
            {layer.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function RedrawNote({ upscale }: { upscale: UpscaleInfo }) {
  if (upscale.mode === "sketch") {
    const rounds = upscale.rounds ?? 1;
    return (
      <span
        className="body-sm muted"
        title="Drawn by a vision model, then checked against the photo"
      >
        Drawn by {upscale.model} · {rounds} {rounds === 1 ? "round" : "rounds"}
      </span>
    );
  }
  return (
    <span className="body-sm muted" title="Elements the upscale pass added to this page">
      +{upscale.added} found
    </span>
  );
}
