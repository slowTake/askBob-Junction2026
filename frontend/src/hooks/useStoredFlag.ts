import { useState } from "react";

/** A boolean UI preference remembered in this browser (e.g. a collapsed panel). */
export function useStoredFlag(key: string, initial: boolean): [boolean, (next: boolean) => void] {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored === null ? initial : stored === "1";
    } catch {
      return initial; // storage blocked (private window, policy)
    }
  });
  const set = (next: boolean) => {
    setValue(next);
    try {
      localStorage.setItem(key, next ? "1" : "0");
    } catch {
      // not remembered; it still works for this visit
    }
  };
  return [value, set];
}
