import { useCallback, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { Answer, ApiErrorBody, AskStep } from "../api/types";

export interface Turn {
  id: string;
  question: string;
  steps: AskStep[];
  answer?: Answer;
  error?: ApiErrorBody;
  pending: boolean;
}

/** A conversation of independent questions; each streams steps, then a cited answer. */
export function useAsk() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const abort = useRef<AbortController | null>(null);

  const update = (id: string, change: (turn: Turn) => Turn) =>
    setTurns((all) => all.map((t) => (t.id === id ? change(t) : t)));

  const ask = useCallback(async (question: string, documentIds: string[]) => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    const id = crypto.randomUUID();
    setTurns((all) => [...all, { id, question, steps: [], pending: true }]);
    try {
      await api.ask(
        question,
        documentIds,
        {
          onStep: (step) => update(id, (t) => ({ ...t, steps: [...t.steps, step] })),
          onAnswer: (answer) => update(id, (t) => ({ ...t, answer })),
          onError: (error) => update(id, (t) => ({ ...t, error })),
        },
        controller.signal,
      );
    } catch (e) {
      if (!controller.signal.aborted) {
        const error =
          e instanceof ApiError
            ? { code: e.code, message: e.message }
            : { code: "network", message: "The connection to the server was lost." };
        update(id, (t) => ({ ...t, error }));
      }
    } finally {
      update(id, (t) => ({ ...t, pending: false }));
    }
  }, []);

  const clear = useCallback(() => {
    abort.current?.abort();
    setTurns([]);
  }, []);

  return { turns, ask, clear, busy: turns.some((t) => t.pending) };
}
