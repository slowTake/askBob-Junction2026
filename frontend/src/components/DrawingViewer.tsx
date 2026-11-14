import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { Citation, DocumentDetail, ElementInfo } from "../api/types";
import { focusBox, focusIsHere } from "../lib/focus";
import { buildCleanSheet, hasEnoughForClean, MIN_WALLS, scaleBar } from "../lib/redraw";
import { scrollToCenter } from "../lib/viewport";
import { focusZoom, stepZoom } from "../lib/zoom";
import { CleanSheet } from "./CleanSheet";

interface Props {
  documentId: string;
  pageIndex: number;
  onPageChange: (index: number) => void;
  focus: Citation | null;
  onClearFocus: () => void;
}

const FOCUS_PAD_PX = 12;

/**
 * A page as its image (Original) or as a redraw of its extracted elements (Clean), with
 * one SVG overlay in page-pixel coordinates over either: bboxes need no conversion.
 */
export function DrawingViewer(props: Props) {
  const { documentId, pageIndex, onPageChange, focus, onClearFocus } = props;
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [zoom, setZoom] = useState(1);
  const [zoomedFor, setZoomedFor] = useState<Citation | null>(null);
  const [showElements, setShowElements] = useState(false);
  const [loaded, setLoaded] = useState<{
    page: number;
    elements: ElementInfo[];
    failed: boolean;
  } | null>(null);
  const [cleanPages, setCleanPages] = useState<ReadonlySet<number>>(new Set());
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

  const clean = cleanPages.has(pageIndex);
  const needElements = showElements || clean;
  useEffect(() => {
    if (!needElements) return;
    let live = true;
    api.elements(documentId, pageIndex).then(
      (els) => live && setLoaded({ page: pageIndex, elements: els, failed: false }),
      () => live && setLoaded({ page: pageIndex, elements: [], failed: true }),
    );
    return () => {
      live = false;
    };
  }, [documentId, pageIndex, needElements]);
  // Elements of another page are never drawn while this page's are on their way.
  const here = loaded?.page === pageIndex ? loaded : null;
  const elements = here?.elements ?? null;
  const failed = here?.failed ?? false;
  const sheet = useMemo(
    () => (clean && elements && !failed ? buildCleanSheet(elements) : null),
    [clean, elements, failed],
  );
  const tooFew = sheet !== null && !hasEnoughForClean(sheet);
  // While the redraw loads the original stays in place, so the scroll position survives.
  // Only a failed load or a redraw with too little to show replaces the scroller with a note.
  const sheetShown = !(clean && (failed || tooFew));

  const setClean = (on: boolean) =>
    setCleanPages((pages) => {
      const next = new Set(pages);
      if (on) next.add(pageIndex);
      else next.delete(pageIndex);
      return next;
    });

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
  }, [focus, page, pageIndex, effectiveZoom, sheetShown]);

  if (!detail) return <div className="viewer-empty">Loading drawing…</div>;
  if (!page) return <div className="viewer-empty">This document has no drawing pages.</div>;

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
          <div className="segmented" role="group" aria-label="Page view">
            <button
              type="button"
              className={`chip chip-toggle${clean ? "" : " is-on"}`}
              aria-pressed={!clean}
              onClick={() => setClean(false)}
            >
              Original
            </button>
            <button
              type="button"
              className={`chip chip-toggle${clean ? " is-on" : ""}`}
              aria-pressed={clean}
              onClick={() => setClean(true)}
            >
              Clean
            </button>
          </div>
          <button
            type="button"
            className={`chip chip-toggle${showElements ? " is-on" : ""}`}
            aria-pressed={showElements}
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
      {!sheetShown ? (
        <div className="viewer-empty">
          <div className="clean-note">
            <p>
              {failed ? (
                "Couldn't load the extracted elements for a clean redraw."
              ) : (
                <>
                  Too little was extracted from this page for a clean redraw (walls found:{" "}
                  {sheet?.walls.length}, needed: {MIN_WALLS}).
                </>
              )}
            </p>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setClean(false)}
            >
              Show the original
            </button>
          </div>
        </div>
      ) : (
        <div className="sheet-scroller" ref={scroller}>
          <div
            className={`sheet${sheet ? " is-clean" : ""}`}
            style={{ width: `${effectiveZoom * 100}%` }}
          >
            {sheet ? (
              <CleanSheet
                sheet={sheet}
                width={w}
                height={h}
                bar={scaleBar({ width: w, height: h }, page.mm_per_px)}
                pageNumber={pageIndex + 1}
              />
            ) : (
              <img
                src={api.pageImageUrl(documentId, pageIndex)}
                alt={`Page ${pageIndex + 1}`}
                // Reserve the page's height before the image loads, so switching views keeps the scroll.
                style={{ aspectRatio: `${w} / ${h}` }}
              />
            )}
            <svg viewBox={`0 0 ${w} ${h}`} className="sheet-overlay" aria-hidden>
              {showElements &&
                elements?.map((el) =>
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
      )}
    </div>
  );
}
