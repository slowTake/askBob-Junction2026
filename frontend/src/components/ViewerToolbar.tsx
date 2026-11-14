import { LAYERS, type LayerKey } from "../lib/planLayer";

interface Props {
  pageIndex: number;
  pageCount: number;
  pageLabel: string | null;
  onPage: (index: number) => void;
  layers: Set<LayerKey>;
  onToggleLayer: (key: LayerKey) => void;
}

/** Page navigation and layer toggles. Fixed height, so nothing below it ever shifts. */
export function ViewerToolbar(props: Props) {
  const { pageIndex, pageCount, pageLabel, onPage, layers, onToggleLayer } = props;
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
