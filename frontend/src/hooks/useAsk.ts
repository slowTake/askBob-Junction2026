import { useCallback, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { Answer, ApiErrorBody, AskStep, PlanView } from "../api/types";

export interface Turn {
  id: string;
  question: string;
  steps: AskStep[];
  views: PlanView[];
  answer?: Answer;
  error?: ApiErrorBody;
  pending: boolean;
}

/** A conversation of independent questions; each streams steps, then a cited answer. */
/** `onView` runs for every plan view the agent sends (live, or replayed from a cached answer). */
export function useAsk(onView: (view: PlanView) => void) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const abort = useRef<AbortController | null>(null);

  const update = (id: string, change: (turn: Turn) => Turn) =>
    setTurns((all) => all.map((t) => (t.id === id ? change(t) : t)));

  const ask = useCallback(
    async (question: string, documentIds: string[]) => {
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      const id = crypto.randomUUID();
      setTurns((all) => [...all, { id, question, steps: [], views: [], pending: true }]);
      try {
        await api.ask(
          question,
          documentIds,
          {
            onStep: (step) => update(id, (t) => ({ ...t, steps: [...t.steps, step] })),
            onAnswer: (answer) => {
              update(id, (t) => ({
                ...t,
                answer,
                views: t.views.length ? t.views : (answer.views ?? []),
              }));
              if (answer.cached) answer.views?.forEach(onView);
            },
            onView: (view) => {
              update(id, (t) => ({ ...t, views: [...t.views, view] }));
              onView(view);
            },
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
    },
    [onView],
  );

  const clear = useCallback(() => {
    abort.current?.abort();
    setTurns([]);
  }, []);

  return { turns, ask, clear, busy: turns.some((t) => t.pending) };
}
