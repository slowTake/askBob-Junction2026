import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/client";
import type { DocumentDetail, ElementInfo, UpscaleResult } from "../api/types";
import { useCamera } from "../hooks/useCamera";
import { useInkBox } from "../hooks/useInkBox";
import { useUpscale } from "../hooks/useUpscale";
import { zoomPercent } from "../lib/camera";
import type { LayerKey } from "../lib/planLayer";
import { buildCleanSheet, type SheetMode } from "../lib/redraw";
import { exportFilename, standaloneSvg } from "../lib/sheetExport";
import {
  buildSketchSheet,
  isSketchDocument,
  planElements,
  redrawScaleBar,
  SKETCH_MODE,
} from "../lib/sketchSheet";
import { selectElement } from "../lib/selection";
import { onPage, type PlanTarget, type TargetOnPage } from "../lib/target";
import { CleanSheet, SketchSheetSvg } from "./CleanSheet";
import { ElementCard } from "./ElementCard";
import { PlanCanvas } from "./PlanCanvas";
import { UpscalePrompt } from "./UpscalePrompt";
import { ViewerToolbar } from "./ViewerToolbar";

const NO_ELEMENTS: ElementInfo[] = [];

interface Props {
  documentId: string;
  pageIndex: number;
  onPageChange: (index: number) => void;
  target: PlanTarget | null; // what the assistant or a citation asked to show
  onClearTarget: () => void;
  onAskAbout: (elements: ElementInfo[]) => void;
}

/** One plan page: pan and zoom, an interactive element layer, and what the agent shows. */
export function DrawingViewer(props: Props) {
  const { documentId, pageIndex, onPageChange, target, onClearTarget, onAskAbout } = props;
  const [detail, setDetail] = useState<DocumentDetail | null | "missing">(null);
  const [loaded, setLoaded] = useState<{ page: number; elements: ElementInfo[] } | null>(null);
  const [layers, setLayers] = useState<Set<LayerKey>>(() => new Set());
  const [hovered, setHovered] = useState<ElementInfo | null>(null);
  const [selected, setSelected] = useState<ElementInfo[]>([]); // click, or Shift+click for more
  const [imageLoaded, setImageLoaded] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState<string | null>(null);
  const [imageAttempt, setImageAttempt] = useState(0);
  const [framed, setFramed] = useState<PlanTarget | null>(null);
  const [sheetMode, setSheetMode] = useState<SheetMode>("original");
  const [elementsVersion, setElementsVersion] = useState(0); // bumped when upscale adds some
  const [printing, setPrinting] = useState<string | null>(null); // the sheet being printed

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
  }, [documentId, pageIndex, elementsVersion]);

  const upscaled = useCallback((result: UpscaleResult) => {
    setDetail((d) =>
      d && d !== "missing"
        ? { ...d, pages: d.pages.map((p) => (p.index === result.page.index ? result.page : p)) }
        : d,
    );
    if (!result.cached) setElementsVersion((v) => v + 1); // a rerun also drops old ones
  }, []);
  const upscale = useUpscale(documentId, pageIndex, upscaled);

  const doc = detail && detail !== "missing" ? detail : null;
  const page = doc?.pages.find((p) => p.index === pageIndex) ?? null;
  const w = page?.width_px ?? 0;
  const h = page?.height_px ?? 0;
  const size = useMemo(() => (w && h ? { width: w, height: h } : null), [w, h]);
  const src = `${api.pageImageUrl(documentId, pageIndex)}?attempt=${imageAttempt}`;
  useEffect(() => {
    if (imageLoaded === src || imageFailed === src) return;
    const timer = window.setTimeout(() => setImageFailed(src), 30_000);
    return () => window.clearTimeout(timer);
  }, [src, imageLoaded, imageFailed]);
  // Fit frames the drawing's ink, not the sheet's paper margins (#83).
  const content = useInkBox(src, size);
  const {
    viewportRef,
    camera,
    ready: laidOut,
    animated,
    dragging,
    pointerFocus,
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
  const added = page?.upscale?.added ?? null;
  const cadRooms = doc?.meta.companion_status === "matched";
  const availableRedraw = cadRooms || added !== null;
  const redrawn = sheetMode === "redrawn" && availableRedraw;
  const mmPerPx = page?.mm_per_px ?? null;
  // A raster image is redrawn whole by the model; its redraw shows only the model's plan.
  const sketchDoc = doc ? isSketchDocument(doc.kind, cadRooms) : false;
  const sketch = redrawn && !cadRooms && page?.upscale?.mode === SKETCH_MODE;
  const redraw = useMemo(() => {
    if (!redrawn || !ready || !w || !h) return null;
    if (sketch) return <SketchSheetSvg sheet={buildSketchSheet(elements)} width={w} height={h} />;
    return (
      <CleanSheet
        sheet={buildCleanSheet(elements, { width: w, height: h })}
        width={w}
        height={h}
        bar={redrawScaleBar({ width: w, height: h }, mmPerPx, sketch)}
      />
    );
  }, [redrawn, sketch, ready, elements, w, h, mmPerPx]);
  const layerElements = useMemo(() => planElements(elements, sketch), [elements, sketch]);

  useEffect(() => {
    if (printing === null) return;
    const done = () => setPrinting(null);
    window.addEventListener("afterprint", done, { once: true });
    window.print(); // the print stylesheet shows only .print-sheet
    return () => window.removeEventListener("afterprint", done);
  }, [printing]);
  const litKey = (shown?.highlightIds ?? []).join(" ");
  // One Set per change of highlight, not per render: the element layer is memoised, and
  // panning must not redraw hundreds of shapes.
  const [lit, setLit] = useState({ key: "", ids: new Set<string>() });
  if (lit.key !== litKey) setLit({ key: litKey, ids: new Set(litKey ? litKey.split(" ") : []) });
  const highlighted = lit.ids;

  // React to a new target once: when the page is laid out and, for agent views, its elements
  // are known. Adjusting state while rendering, so there is no frame in between.
  // A cited source the user clicked is flown to; the agent's highlights don't zoom: the plan
  // stays fitted with the highlight drawn on it (⌖ zooms to it on demand).
  const frameable = shown?.frame && (target?.kind === "citation" || ready);
  if (target !== framed && laidOut && (target === null || frameable)) {
    setFramed(target);
    if (target?.kind === "citation" && shown?.frame) frame(shown.frame);
    else if (target?.kind === "view") fit();
  }

  const select = useCallback(
    (el: ElementInfo | null, additive: boolean) =>
      setSelected((current) => selectElement(current, el, additive)),
    [],
  );

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

  const pinned = useMemo(
    () => (page ? selected.filter((e) => e.page_id === page.id) : []),
    [selected, page],
  );
  // One Set per change of selection: the element layer is memoised.
  const selectedIds = useMemo(() => new Set(pinned.map((e) => e.id)), [pinned]);
  const hover = hovered && page && hovered.page_id === page.id ? hovered : null;
  const shownInBar = pinned.length > 0 ? pinned : hover ? [hover] : [];
  const percent = camera && fitted ? zoomPercent(camera, fitted) : 100;

  return (
    <div className="viewer">
      {doc && (
        <ViewerToolbar
          pageIndex={pageIndex}
          pageCount={doc.pages.length}
          pageLabel={page?.label ?? null}
          onPage={(i) => {
            setSelected([]);
            onPageChange(i);
          }}
          layers={layers}
          onToggleLayer={toggleLayer}
          sheet={sheetMode}
          onSheet={setSheetMode}
          onDownload={
            redraw ? () => downloadSheet(viewportRef.current, w, h, doc.filename, pageIndex) : null
          }
          onPrint={redraw ? () => setPrinting(sheetFile(viewportRef.current, w, h)) : null}
        />
      )}
      <div
        ref={viewportRef}
        className={`plan-viewport${dragging ? " is-dragging" : ""}${pointerFocus ? " is-pointer-focus" : ""}`}
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
            elements={layerElements}
            layers={layers}
            highlighted={highlighted}
            shown={shown}
            selectedIds={selectedIds}
            onHover={pointAt}
            onSelect={select}
            onLoad={() => {
              setImageFailed(null);
              setImageLoaded(src);
            }}
            onError={() => setImageFailed(src)}
            redraw={redraw}
          />
        )}
        {sheetMode === "redrawn" && page && !availableRedraw && (
          <UpscalePrompt
            busy={upscale.busy}
            error={upscale.error}
            sketch={sketchDoc}
            onUpscale={upscale.run}
          />
        )}
        {detail === "missing" ? (
          <div className="viewer-note">The drawing could not be loaded.</div>
        ) : doc && !page ? (
          <div className="viewer-note">This document has no drawing pages.</div>
        ) : imageFailed === src ? (
          <div className="viewer-note" role="alert">
            The drawing image could not be loaded.{" "}
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setImageAttempt((attempt) => attempt + 1)}
            >
              Retry
            </button>
          </div>
        ) : (
          imageLoaded !== src && <div className="viewer-note is-loading">Loading drawing…</div>
        )}
        {shown && shown.verified !== null && <TargetBanner shown={shown} onClear={onClearTarget} />}
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
          {shown && shown.verified === null && (
            // The agent's highlight has no banner; this clears it (a clicked source's
            // banner has its own Clear).
            <button
              type="button"
              className="btn btn-subtle btn-sm"
              title="Clear the assistant's highlight"
              onClick={onClearTarget}
            >
              Clear
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
        elements={shownInBar}
        pinned={pinned.length > 0}
        onClose={() => setSelected([])}
        onAsk={() => onAskAbout(pinned)}
      />
      {printing &&
        createPortal(
          // Our own serialized svg: element text was escaped by XMLSerializer.
          <div className="print-sheet" dangerouslySetInnerHTML={{ __html: printing }} />,
          document.body,
        )}
    </div>
  );
}

/** The redrawn sheet as drawn on screen, made into a file that stands alone. */
function sheetFile(viewport: HTMLElement | null, width: number, height: number): string | null {
  const svg = viewport?.querySelector("svg.clean-sheet");
  return svg ? standaloneSvg(new XMLSerializer().serializeToString(svg), { width, height }) : null;
}

function downloadSheet(
  viewport: HTMLElement | null,
  width: number,
  height: number,
  filename: string,
  index: number,
) {
  const file = sheetFile(viewport, width, height);
  if (!file) return;
  const url = URL.createObjectURL(new Blob([file], { type: "image/svg+xml" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = exportFilename(filename, index);
  link.click();
  URL.revokeObjectURL(url);
}

/** For a source the user clicked: whether it's verified, and a way to clear it. */
function TargetBanner({ shown, onClear }: { shown: TargetOnPage; onClear: () => void }) {
  return (
    <div className="target-banner" data-no-pan>
      <span className={`badge ${shown.verified ? "badge-ok" : "badge-warn"}`}>
        {shown.verified ? "✓ Verified source" : "! Unverified source"}
      </span>
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
