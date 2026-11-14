import { useEffect, useState } from "react";
import type { BBox, Size } from "../lib/camera";
import { inkBox, luminance, toPageBox } from "../lib/ink";

const SAMPLE_PX = 1024; // longest side of the sampled image: fast, and thin lines survive

/**
 * Where the drawing is on the page image at `src`, in page pixels, for Fit (#83).
 * Null until the image is sampled, and when it can't be (blank page, no canvas).
 * The box keeps its identity until `src` or `page` changes.
 */
export function useInkBox(src: string, page: Size | null): BBox | null {
  const [found, setFound] = useState<{ src: string; box: BBox | null } | null>(null);

  useEffect(() => {
    if (!page) return;
    let live = true;
    const img = new Image(); // same origin as the app, so the canvas can be read
    img.onload = () => {
      if (!live) return;
      let box: BBox | null = null;
      try {
        box = sample(img, page);
      } catch {
        // e.g. SecurityError: an image from another origin taints the canvas. Fit then
        // frames the whole sheet.
      }
      setFound({ src, box });
    };
    img.onerror = () => live && setFound({ src, box: null });
    img.src = src;
    return () => {
      live = false;
    };
  }, [src, page]);

  return found?.src === src ? found.box : null;
}

function sample(img: HTMLImageElement, page: Size): BBox | null {
  const k = Math.min(1, SAMPLE_PX / Math.max(img.naturalWidth, img.naturalHeight));
  const size = {
    width: Math.max(1, Math.round(img.naturalWidth * k)),
    height: Math.max(1, Math.round(img.naturalHeight * k)),
  };
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(img, 0, 0, size.width, size.height);
  const { data } = ctx.getImageData(0, 0, size.width, size.height);
  const box = inkBox(luminance(data), size.width, size.height);
  return box ? toPageBox(box, size, page) : null;
}
