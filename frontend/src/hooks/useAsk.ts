import { useCallback, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { Answer, ApiErrorBody, AskContext, AskStep, PlanView } from "../api/types";

export interface Turn {
  id: string;
  question: string;
  about: string | null; // the element the question was asked about, e.g. "room Kitchen"
  steps: AskStep[];
  views: PlanView[];
  answer?: Answer;
  error?: ApiErrorBody;
  pending: boolean;
}

export interface AskOptions {
  documentIds: string[];
  context: AskContext | null;
  about: string | null;
}

/**
 * A conversation of independent questions; each streams steps, then a cited answer.
 * `onView` runs for every plan view the agent sends (live, or replayed from a cached answer).
 */
export function useAsk(onView: (view: PlanView) => void) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const abort = useRef<AbortController | null>(null);

  const update = (id: string, change: (turn: Turn) => Turn) =>
    setTurns((all) => all.map((t) => (t.id === id ? change(t) : t)));

  const ask = useCallback(
    async (question: string, options: AskOptions) => {
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      const id = crypto.randomUUID();
      const turn: Turn = {
        id,
        question,
        about: options.about,
        steps: [],
        views: [],
        pending: true,
      };
      setTurns((all) => [...all, turn]);
      try {
        await api.ask(
          question,
          options.documentIds,
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
          options.context ?? undefined,
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
