import { useEffect, useRef, useState } from "react";
import type React from "react";
import {
  clampPan,
  fitContent,
  frameBox,
  limits,
  resize,
  zoomAt,
  type BBox,
  type Camera,
  type Size,
} from "../lib/camera";

const WHEEL_ZOOM = 0.0015; // zoom factor per wheel pixel: one mouse notch (100 px) is ~16 %
const STEP = 1.25; // zoom buttons and keys
const DRAG_THRESHOLD_PX = 4; // less than this is a click, not a pan

interface Drag {
  x: number;
  y: number;
  from: Camera;
  moved: boolean;
}

/**
 * Pan and zoom for one page: wheel zooms at the cursor, dragging pans, + - 0 keys.
 * `pageKey` identifies the page; a new page starts fitted to the viewport.
 * `content` is the part of the page the drawing covers (see useInkBox); fitting frames
 * it, or the whole page while it is null. Its identity must only change with its value.
 */
export function useCamera(page: Size | null, pageKey: string, content: BBox | null = null) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<Size | null>(null);
  const [camera, setCamera] = useState<Camera | null>(null);
  const [fittedFor, setFittedFor] = useState<string | null>(null);
  const [animated, setAnimated] = useState(false);
  // While nobody has panned or zoomed, the page stays fitted as the panels settle or resize.
  const [autoFit, setAutoFit] = useState(true);
  const [fitSize, setFitSize] = useState<Size | null>(null);
  const [fitBox, setFitBox] = useState<BBox | null>(null);
  const [dragging, setDragging] = useState(false);
  const [pointerFocus, setPointerFocus] = useState(false);
  const drag = useRef<Drag | null>(null);
  const swallowClick = useRef(false);

  // A new page starts fitted (adjusting state while rendering, not in an effect).
  if (page && viewport && fittedFor !== pageKey) {
    setFittedFor(pageKey);
    setAutoFit(true);
    setFitSize(viewport);
    setFitBox(content);
    setAnimated(false);
    setCamera(fitContent(content, page, viewport));
  } else if (page && viewport && autoFit && (fitSize !== viewport || fitBox !== content)) {
    // The panels resized, or the drawing's extent was found after the page showed:
    // still fitted, so refit.
    // Glide when only the content changed, so the view doesn't jump.
    setAnimated(fitSize === viewport);
    setFitSize(viewport);
    setFitBox(content);
    setCamera(fitContent(content, page, viewport));
  }

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    let last: Size | null = null;
    const observer = new ResizeObserver(([entry]) => {
      const next = { width: entry.contentRect.width, height: entry.contentRect.height };
      if (next.width === 0 || next.height === 0) return; // hidden
      const from = last;
      if (from) setCamera((c) => (c ? resize(c, from, next) : c));
      last = next;
      setViewport(next);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // The Fit scale: 100 % on the zoom label, and the zoom limits are relative to it.
  const fitted = page && viewport ? fitContent(content, page, viewport).scale : null;

  useEffect(() => {
    const el = viewportRef.current;
    if (!el || !page || !viewport || fitted === null) return;
    const lim = limits(page, viewport, fitted);
    const onWheel = (e: WheelEvent) => {
      e.preventDefault(); // also stops a trackpad pinch from zooming the whole browser page
      const rect = el.getBoundingClientRect();
      const at = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      const delta = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY; // lines -> pixels
      setAutoFit(false);
      setAnimated(false);
      setCamera((c) =>
        c ? clampPan(zoomAt(c, Math.exp(-delta * WHEEL_ZOOM), at, lim), page, viewport) : c,
      );
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [page, viewport, fitted]);

  const ready = page !== null && viewport !== null && camera !== null;

  const zoomBy = (factor: number) => {
    if (!page || !viewport || fitted === null) return;
    const centre = { x: viewport.width / 2, y: viewport.height / 2 };
    setAutoFit(false);
    setAnimated(true);
    setCamera((c) => (c ? zoomAt(c, factor, centre, limits(page, viewport, fitted)) : c));
  };

  const fit = () => {
    if (!page || !viewport) return;
    setAutoFit(true);
    setFitSize(viewport);
    setFitBox(content);
    setAnimated(true);
    setCamera(fitContent(content, page, viewport));
  };

  const frame = (box: BBox) => {
    if (!page || !viewport) return;
    setAutoFit(false);
    setAnimated(true);
    setCamera(frameBox(box, page, viewport));
  };

  const endDrag = () => {
    if (drag.current?.moved) {
      swallowClick.current = true; // the click that ends a drag selects nothing
      setDragging(false);
    }
    drag.current = null;
  };

  const handlers = {
    onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => {
      swallowClick.current = false;
      // Focused by a click, not the keyboard: no focus ring. Chrome would show one for a
      // Shift+click, as Shift counts as keyboard use; Tab still shows it.
      setPointerFocus(true);
      if (e.button !== 0 || !camera) return;
      if ((e.target as HTMLElement).closest("[data-no-pan]")) return; // cards, buttons
      drag.current = { x: e.clientX, y: e.clientY, from: camera, moved: false };
    },
    onPointerMove: (e: React.PointerEvent<HTMLDivElement>) => {
      const d = drag.current;
      if (!d || !page || !viewport) return;
      const dx = e.clientX - d.x;
      const dy = e.clientY - d.y;
      if (!d.moved) {
        if (Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;
        d.moved = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        setDragging(true);
        setAutoFit(false);
      }
      setAnimated(false);
      setCamera(clampPan({ ...d.from, x: d.from.x + dx, y: d.from.y + dy }, page, viewport));
    },
    onPointerUp: endDrag,
    onPointerCancel: endDrag,
    onClickCapture: (e: React.MouseEvent) => {
      if (!swallowClick.current) return;
      swallowClick.current = false;
      e.stopPropagation();
    },
    onBlur: () => setPointerFocus(false),
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "+" || e.key === "=") zoomBy(STEP);
      else if (e.key === "-") zoomBy(1 / STEP);
      else if (e.key === "0") fit();
      else return;
      e.preventDefault();
    },
  };

  return {
    viewportRef,
    viewport,
    camera,
    ready,
    animated,
    dragging,
    pointerFocus,
    handlers,
    zoomIn: () => zoomBy(STEP),
    zoomOut: () => zoomBy(1 / STEP),
    fit,
    fitted,
    frame,
  };
}
