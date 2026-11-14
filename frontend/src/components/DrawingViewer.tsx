import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { DocumentDetail, ElementInfo } from "../api/types";
import { useCamera } from "../hooks/useCamera";
import { useInkBox } from "../hooks/useInkBox";
import { zoomPercent } from "../lib/camera";
import type { LayerKey } from "../lib/planLayer";
import { onPage, type PlanTarget, type TargetOnPage } from "../lib/target";
import { ElementCard } from "./ElementCard";
import { PlanCanvas } from "./PlanCanvas";
import { ViewerToolbar } from "./ViewerToolbar";

const NO_ELEMENTS: ElementInfo[] = [];

interface Props {
  documentId: string;
  pageIndex: number;
  onPageChange: (index: number) => void;
  target: PlanTarget | null; // what the assistant or a citation asked to show
  onClearTarget: () => void;
  onAskAbout: (element: ElementInfo) => void;
}

/** One plan page: pan and zoom, an interactive element layer, and what the agent shows. */
export function DrawingViewer(props: Props) {
  const { documentId, pageIndex, onPageChange, target, onClearTarget, onAskAbout } = props;
  const [detail, setDetail] = useState<DocumentDetail | null | "missing">(null);
  const [loaded, setLoaded] = useState<{ page: number; elements: ElementInfo[] } | null>(null);
  const [layers, setLayers] = useState<Set<LayerKey>>(() => new Set());
  const [hovered, setHovered] = useState<ElementInfo | null>(null);
  const [selected, setSelected] = useState<ElementInfo | null>(null);
  const [imageLoaded, setImageLoaded] = useState<string | null>(null);
  const [framed, setFramed] = useState<PlanTarget | null>(null);

  useEffect(() => {
    let live = true;
    api.getDocument(documentId).then(
      (d) => live && setDetail(d),
      () => live && setDetail("missing"),
    );
    return () => {
      live = false;
    };
  }, [documentId]);

  useEffect(() => {
    let live = true;
    api.elements(documentId, pageIndex).then(
      (elements) => live && setLoaded({ page: pageIndex, elements }),
      () => live && setLoaded({ page: pageIndex, elements: [] }),
    );
    return () => {
      live = false;
    };
  }, [documentId, pageIndex]);

  const doc = detail && detail !== "missing" ? detail : null;
  const page = doc?.pages.find((p) => p.index === pageIndex) ?? null;
  const w = page?.width_px ?? 0;
  const h = page?.height_px ?? 0;
  const size = useMemo(() => (w && h ? { width: w, height: h } : null), [w, h]);
  const src = api.pageImageUrl(documentId, pageIndex);
  // Fit frames the drawing's ink, not the sheet's paper margins (#83).
  const content = useInkBox(src, size);
  const {
    viewportRef,
    camera,
    ready: laidOut,
    animated,
    dragging,
    handlers,
    zoomIn,
    zoomOut,
    fit,
    fitted,
    frame,
  } = useCamera(size, `${documentId}:${pageIndex}`, content);

  // Elements of another page never show on this one, even for a moment.
  const ready = loaded?.page === pageIndex;
  const elements = ready && loaded ? loaded.elements : NO_ELEMENTS;
  const shown = onPage(target, pageIndex, elements);
  const litKey = (shown?.highlightIds ?? []).join(" ");
  // One Set per change of highlight, not per render: the element layer is memoised, and
  // panning must not redraw hundreds of shapes.
  const [lit, setLit] = useState({ key: "", ids: new Set<string>() });
  if (lit.key !== litKey) setLit({ key: litKey, ids: new Set(litKey ? litKey.split(" ") : []) });
  const highlighted = lit.ids;

  // Fly to a new target once: when the page is laid out and, for agent views, its elements
  // are known. Adjusting state while rendering, so there is no frame in between.
  const frameable = shown?.frame && (target?.kind === "citation" || ready);
  if (target !== framed && laidOut && (target === null || frameable)) {
    setFramed(target);
    if (shown?.frame) frame(shown.frame);
  }

  // Pointing at nothing (a wall, a gap between rooms) keeps the last element in the bar.
  const pointAt = useCallback((el: ElementInfo | null) => {
    if (el) setHovered(el);
  }, []);

  const toggleLayer = useCallback(
    (key: LayerKey) =>
      setLayers((current) => {
        const next = new Set(current);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      }),
    [],
  );

  const pinned = selected && page && selected.page_id === page.id ? selected : null;
  const hover = hovered && page && hovered.page_id === page.id ? hovered : null;
  const card = pinned ?? hover;
  const percent = camera && fitted ? zoomPercent(camera, fitted) : 100;

  return (
    <div className="viewer">
      {doc && (
        <ViewerToolbar
          pageIndex={pageIndex}
          pageCount={doc.pages.length}
          pageLabel={page?.label ?? null}
          onPage={(i) => {
            setSelected(null);
            onPageChange(i);
          }}
          layers={layers}
          onToggleLayer={toggleLayer}
        />
      )}
      <div
        ref={viewportRef}
        className={`plan-viewport${dragging ? " is-dragging" : ""}`}
        tabIndex={0}
        aria-label="Plan. Drag to pan, scroll to zoom, + and - keys zoom, 0 fits the page."
        {...handlers}
      >
        {page && camera && (
          <PlanCanvas
            src={src}
            alt={page.label ?? `Page ${pageIndex + 1}`}
            width={w}
            height={h}
            camera={camera}
            animated={animated}
            elements={elements}
            layers={layers}
            highlighted={highlighted}
            shown={shown}
            selectedId={pinned?.id ?? null}
            onHover={pointAt}
            onSelect={setSelected}
            onLoad={() => setImageLoaded(src)}
          />
        )}
        {detail === "missing" ? (
          <div className="viewer-note">The drawing could not be loaded.</div>
        ) : doc && !page ? (
          <div className="viewer-note">This document has no drawing pages.</div>
        ) : (
          imageLoaded !== src && <div className="viewer-note is-loading">Loading drawing…</div>
        )}
        {shown && <TargetBanner shown={shown} onClear={onClearTarget} />}
        <div className="zoom-controls" data-no-pan>
          {shown?.frame && (
            <button
              type="button"
              className="btn btn-subtle btn-sm"
              title="Show what the assistant pointed at"
              onClick={() => shown.frame && frame(shown.frame)}
            >
              ⌖
            </button>
          )}
          <button
            type="button"
            className="btn btn-subtle btn-sm"
            aria-label="Zoom out"
            onClick={zoomOut}
          >
            −
          </button>
          <span className="zoom-value">{percent}%</span>
          <button
            type="button"
            className="btn btn-subtle btn-sm"
            aria-label="Zoom in"
            onClick={zoomIn}
          >
            +
          </button>
          <button type="button" className="btn btn-subtle btn-sm" onClick={fit}>
            Fit
          </button>
        </div>
      </div>
      <ElementCard
        element={card}
        pinned={card !== null && card === pinned}
        onClose={() => setSelected(null)}
        onAsk={() => card && onAskAbout(card)}
      />
    </div>
  );
}

function TargetBanner({ shown, onClear }: { shown: TargetOnPage; onClear: () => void }) {
  return (
    <div className="target-banner" data-no-pan>
      {shown.verified === null ? (
        <span className="badge badge-accent">Shown by the assistant</span>
      ) : (
        <span className={`badge ${shown.verified ? "badge-ok" : "badge-warn"}`}>
          {shown.verified ? "✓ Verified source" : "! Unverified source"}
        </span>
      )}
      {shown.labelOnly && (
        <span
          className="badge badge-plain"
          title="The room's outline wasn't found on the drawing, so only its name is marked"
        >
          Label only
        </span>
      )}
      <span className="target-caption">{shown.caption}</span>
      <button type="button" className="btn btn-subtle btn-sm" onClick={onClear}>
        Clear
      </button>
    </div>
  );
}
