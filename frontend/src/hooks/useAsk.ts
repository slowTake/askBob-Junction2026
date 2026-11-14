import { useCallback, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { Answer, ApiErrorBody, AskContext, AskStep, PlanView } from "../api/types";
import {
  addTurn,
  dropConversation,
  isBusy,
  turnsOf,
  updateTurn,
  type Conversations,
} from "../lib/conversations";

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
 * One conversation per document (see lib/conversations.ts); each question streams steps,
 * then a cited answer, into the conversation it was asked in, even if the user opens
 * another document meanwhile. `onView` runs for every plan view the agent sends (live, or
 * replayed from a cached answer), with the key of the conversation it belongs to.
 */
export function useAsk(onView: (view: PlanView, key: string) => void) {
  const [all, setAll] = useState<Conversations<Turn>>({});
  const aborts = useRef(new Map<string, AbortController>()); // per conversation

  const update = (id: string, change: (turn: Turn) => Turn) =>
    setAll((current) => updateTurn(current, id, change));

  const ask = useCallback(
    async (key: string, question: string, options: AskOptions) => {
      aborts.current.get(key)?.abort(); // a new question replaces this conversation's last one
      const controller = new AbortController();
      aborts.current.set(key, controller);
      const id = crypto.randomUUID();
      const turn: Turn = {
        id,
        question,
        about: options.about,
        steps: [],
        views: [],
        pending: true,
      };
      setAll((current) => addTurn(current, key, turn));
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
              if (answer.cached) answer.views?.forEach((v) => onView(v, key));
            },
            onView: (view) => {
              update(id, (t) => ({ ...t, views: [...t.views, view] }));
              onView(view, key);
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
        if (aborts.current.get(key) === controller) aborts.current.delete(key);
      }
    },
    [onView],
  );

  /** Empty one document's conversation (Clear), or forget it (the document was deleted). */
  const clear = useCallback((key: string) => {
    aborts.current.get(key)?.abort();
    aborts.current.delete(key);
    setAll((current) => dropConversation(current, key));
  }, []);

  return {
    turnsFor: (key: string | null) => turnsOf(all, key),
    busyFor: (key: string | null) => isBusy(all, key),
    ask,
    clear,
  };
}
