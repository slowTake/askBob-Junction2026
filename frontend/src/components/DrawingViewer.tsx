import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Citation, DocumentDetail, ElementInfo } from "../api/types";
import { scrollToCenter } from "../lib/viewport";
import { focusZoom, stepZoom } from "../lib/zoom";

interface Props {
  documentId: string;
  pageIndex: number;
  onPageChange: (index: number) => void;
  focus: Citation | null;
  onClearFocus: () => void;
}

const FOCUS_PAD_PX = 12;

/** Page image with an SVG overlay in page-pixel coordinates: bboxes need no conversion. */
export function DrawingViewer(props: Props) {
  const { documentId, pageIndex, onPageChange, focus, onClearFocus } = props;
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [zoom, setZoom] = useState(1);
  const [zoomedFor, setZoomedFor] = useState<Citation | null>(null);
  const [showElements, setShowElements] = useState(false);
  const [elements, setElements] = useState<ElementInfo[]>([]);
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
    if (!showElements) return;
    let live = true;
    api.elements(documentId, pageIndex).then(
      (els) => live && setElements(els),
      () => live && setElements([]),
    );
    return () => {
      live = false;
    };
  }, [documentId, pageIndex, showElements]);

  const page = detail?.pages.find((p) => p.index === pageIndex) ?? null;
  // A newly focused citation zooms in once; after that − and + move freely.
  if (focus !== zoomedFor) {
    setZoomedFor(focus);
    if (focus?.bbox) setZoom(focusZoom);
  }
  const effectiveZoom = zoom;

  useEffect(() => {
    const el = scroller.current;
    if (!el || !page || !focus?.bbox) return;
    const target = scrollToCenter(
      focus.bbox,
      { width: page.width_px, height: page.height_px },
      el.clientWidth * effectiveZoom,
      { width: el.clientWidth, height: el.clientHeight },
    );
    el.scrollTo({ ...target, behavior: "smooth" });
  }, [focus, page, effectiveZoom]);

  if (!detail) return <div className="viewer-empty">Loading drawing…</div>;
  if (!page) return <div className="viewer-empty">This document has no drawing pages.</div>;

  const w = page.width_px;
  const h = page.height_px;
  const box = focus?.bbox ?? null;

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
            Page {pageIndex + 1} of {detail.pages.length}
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
          <button
            type="button"
            className={`chip chip-toggle${showElements ? " is-on" : ""}`}
            onClick={() => setShowElements((s) => !s)}
          >
            Extracted elements
          </button>
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
      {focus && (
        <div className="focus-banner">
          <span className={`badge ${focus.verified ? "badge-dark" : "badge-light"}`}>
            {focus.verified ? "Verified source" : "Unverified"}
          </span>
          <span className="body-sm">{focus.note}</span>
          <button type="button" className="btn btn-subtle btn-sm" onClick={onClearFocus}>
            Clear
          </button>
        </div>
      )}
      <div className="sheet-scroller" ref={scroller}>
        <div className="sheet" style={{ width: `${effectiveZoom * 100}%` }}>
          <img src={api.pageImageUrl(documentId, pageIndex)} alt={`Page ${pageIndex + 1}`} />
          <svg viewBox={`0 0 ${w} ${h}`} className="sheet-overlay" aria-hidden>
            {showElements &&
              elements.map((el) =>
                el.bbox ? (
                  <rect
                    key={el.id}
                    className={`el el-${el.kind}`}
                    x={el.bbox[0]}
                    y={el.bbox[1]}
                    width={el.bbox[2] - el.bbox[0]}
                    height={el.bbox[3] - el.bbox[1]}
                    vectorEffect="non-scaling-stroke"
                  >
                    <title>{`${el.kind}: ${el.name ?? el.label ?? ""} (${el.source})`}</title>
                  </rect>
                ) : null,
              )}
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
