import { useCallback, useState } from "react";
import { api, ApiError } from "../api/client";
import type { UpscaleResult } from "../api/types";

interface State {
  key: string; // the page it belongs to: another page never shows this one's progress
  busy: boolean;
  error: string | null;
}

/** Run the upscale vision pass (#82) for one page, on demand. The server caches it. */
export function useUpscale(
  documentId: string,
  pageIndex: number,
  onDone: (result: UpscaleResult) => void,
) {
  const key = `${documentId}:${pageIndex}`;
  const [state, setState] = useState<State | null>(null);

  const run = useCallback(() => {
    setState({ key, busy: true, error: null });
    api.upscale(documentId, pageIndex).then(
      (result) => {
        setState((s) => (s?.key === key ? null : s));
        onDone(result);
      },
      (e: unknown) => {
        const error = e instanceof ApiError ? e.message : "The page could not be upscaled.";
        setState((s) => (s?.key === key ? { key, busy: false, error } : s));
      },
    );
  }, [documentId, pageIndex, key, onDone]);

  const mine = state?.key === key ? state : null;
  return { busy: mine?.busy ?? false, error: mine?.error ?? null, run };
}
