import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Citation, DocumentDetail, ElementInfo } from "../api/types";
import { LAYERS, type LayerKey } from "../lib/planLayer";
import { ElementCard } from "./ElementCard";
import { PlanLayer } from "./PlanLayer";
import { focusBox, focusIsHere } from "../lib/focus";
import { scrollToCenter } from "../lib/viewport";
import { focusZoom, stepZoom } from "../lib/zoom";

interface Props {
  documentId: string;
  pageIndex: number;
  onPageChange: (index: number) => void;
  focus: Citation | null;
  onClearFocus: () => void;
  highlightIds?: string[]; // elements to light up (agent or citation)
}

const DEFAULT_LAYERS: LayerKey[] = ["openings", "fixtures"];

const FOCUS_PAD_PX = 12;

/** Page image with an SVG overlay in page-pixel coordinates: bboxes need no conversion. */
export function DrawingViewer(props: Props) {
  const { documentId, pageIndex, onPageChange, focus, onClearFocus, highlightIds } = props;
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [zoom, setZoom] = useState(1);
  const [zoomedFor, setZoomedFor] = useState<Citation | null>(null);
  const [layers, setLayers] = useState<Set<LayerKey>>(() => new Set(DEFAULT_LAYERS));
  const [elements, setElements] = useState<ElementInfo[]>([]);
  const [hovered, setHovered] = useState<ElementInfo | null>(null);
  const [selected, setSelected] = useState<ElementInfo | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let live = true;
    api.getDocument(documentId).then(
      (d) => live && setDetail(d),
      () => live && setDetail(null),
    );
    return () => {
      live = false;
    };
  }, [documentId]);

  useEffect(() => {
    let live = true;
    api.elements(documentId, pageIndex).then(
      (els) => live && setElements(els),
      () => live && setElements([]),
    );
    return () => {
      live = false;
    };
  }, [documentId, pageIndex]);

  const page = detail?.pages.find((p) => p.index === pageIndex) ?? null;
  // A newly focused citation zooms in once; after that − and + move freely.
  if (focus !== zoomedFor) {
    setZoomedFor(focus);
    if (focus?.bbox) setZoom(focusZoom);
  }
  const effectiveZoom = zoom;

  useEffect(() => {
    const el = scroller.current;
    const cited = focusBox(focus, pageIndex);
    if (!el || !page || !cited) return;
    const target = scrollToCenter(
      cited,
      { width: page.width_px, height: page.height_px },
      el.clientWidth * effectiveZoom,
      { width: el.clientWidth, height: el.clientHeight },
    );
    el.scrollTo({ ...target, behavior: "smooth" });
  }, [focus, page, pageIndex, effectiveZoom]);

  if (!detail) return <div className="viewer-empty">Loading drawing…</div>;
  if (!page) return <div className="viewer-empty">This document has no drawing pages.</div>;

  // A pinned card belongs to its page; switching pages hides it.
  const pinned = selected && selected.page_id === page.id ? selected : null;
  const shown = pinned ?? hovered;
  const w = page.width_px;
  const h = page.height_px;
  const box = focusBox(focus, pageIndex);

  return (
    <div className="viewer">
      <div className="viewer-toolbar">
        <div className="chip-row">
          <button
            type="button"
            className="btn btn-subtle btn-sm"
            disabled={pageIndex === 0}
            onClick={() => onPageChange(pageIndex - 1)}
          >
            ‹
          </button>
          <span className="body-sm">
            {page.label ?? `Page ${pageIndex + 1}`} ({pageIndex + 1} of {detail.pages.length})
          </span>
          <button
            type="button"
            className="btn btn-subtle btn-sm"
            disabled={pageIndex >= detail.pages.length - 1}
            onClick={() => onPageChange(pageIndex + 1)}
          >
            ›
          </button>
        </div>
        <div className="chip-row">
          {LAYERS.map((layer) => (
            <button
              key={layer.key}
              type="button"
              className={`chip chip-toggle${layers.has(layer.key) ? " is-on" : ""}`}
              onClick={() => setLayers((current) => toggled(current, layer.key))}
            >
              {layer.label}
            </button>
          ))}
          <button
            type="button"
            className="btn btn-subtle btn-sm"
            onClick={() => setZoom(stepZoom(effectiveZoom, -1))}
          >
            −
          </button>
          <span className="body-sm">{Math.round(effectiveZoom * 100)}%</span>
          <button
            type="button"
            className="btn btn-subtle btn-sm"
            onClick={() => setZoom(stepZoom(effectiveZoom, 1))}
          >
            +
          </button>
        </div>
      </div>
      {focus && focusIsHere(focus, pageIndex) && (
        <div className="focus-banner">
          <span className={`badge ${focus.verified ? "badge-ok" : "badge-warn"}`}>
            {focus.verified ? "Verified source" : "Unverified"}
          </span>
          <span className="body-sm">{focus.note}</span>
          <button type="button" className="btn btn-subtle btn-sm" onClick={onClearFocus}>
            Clear
          </button>
        </div>
      )}
      {shown && (
        <ElementCard element={shown} pinned={pinned !== null} onClose={() => setSelected(null)} />
      )}
      <div className="sheet-scroller" ref={scroller}>
        <div className="sheet" style={{ width: `${effectiveZoom * 100}%` }}>
          <img src={api.pageImageUrl(documentId, pageIndex)} alt={`Page ${pageIndex + 1}`} />
          <svg
            viewBox={`0 0 ${w} ${h}`}
            className="sheet-overlay"
            onClick={() => setSelected(null)}
          >
            <PlanLayer
              elements={elements}
              visible={layers}
              highlighted={new Set(highlightIds ?? [])}
              selectedId={pinned?.id ?? null}
              onHover={setHovered}
              onSelect={setSelected}
            />
            {box && (
              <>
                <defs>
                  <mask id="spotlight">
                    <rect width={w} height={h} fill="white" />
                    <rect
                      x={box[0] - FOCUS_PAD_PX}
                      y={box[1] - FOCUS_PAD_PX}
                      width={box[2] - box[0] + 2 * FOCUS_PAD_PX}
                      height={box[3] - box[1] + 2 * FOCUS_PAD_PX}
                      rx={8}
                      fill="black"
                    />
                  </mask>
                </defs>
                <rect width={w} height={h} className="spotlight-dim" mask="url(#spotlight)" />
                <rect
                  className="spotlight-ring"
                  x={box[0] - FOCUS_PAD_PX}
                  y={box[1] - FOCUS_PAD_PX}
                  width={box[2] - box[0] + 2 * FOCUS_PAD_PX}
                  height={box[3] - box[1] + 2 * FOCUS_PAD_PX}
                  rx={8}
                  vectorEffect="non-scaling-stroke"
                />
              </>
            )}
          </svg>
        </div>
      </div>
    </div>
  );
}

function toggled(current: Set<LayerKey>, key: LayerKey): Set<LayerKey> {
  const next = new Set(current);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}
