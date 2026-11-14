import { useEffect, type RefObject } from "react";

/** Close a popover on a click anywhere outside `ref`, or on Esc, while `active`. */
export function useDismiss(
  ref: RefObject<HTMLElement | null>,
  onClose: () => void,
  active = true,
): void {
  useEffect(() => {
    if (!active) return;
    const outside = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [ref, onClose, active]);
}
