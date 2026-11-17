/**
 * The API of the static demo build (D-059): reads the snapshot that
 * `scripts/demo_snapshot.py` recorded from a real local run, and replays recorded answers.
 * Nothing here talks to a backend; writes are refused with a message saying why.
 */

import type { Api, AskHandlers } from "../api/client";
import { ApiError } from "../api/errors";
import type {
  Answer,
  ApiErrorBody,
  AskContext,
  AskStep,
  DocumentDetail,
  ElementInfo,
  MeshData,
  PlanView,
  UpscaleResult,
} from "../api/types";
import { assetPath, findRecording, type Asset, type Snapshot } from "./snapshot";

type Load = (url: string) => Promise<Response>;
type Pause = (ms: number) => Promise<void>;

/** Between replayed events, so an answer arrives step by step as it did live. */
const STEP_MS = 350;

const READ_ONLY =
  "This is a recorded demo, so it can't change anything. Clone the repo and run `make up` to use it live.";

const readOnly = (): Promise<never> =>
  Promise.reject(new ApiError("demo_read_only", READ_ONLY));

const wait: Pause = (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms));

export function createDemoApi(base: string, load: Load = fetch, pause: Pause = wait): Api {
  let snapshot: Promise<Snapshot> | null = null;

  async function json<T>(path: string): Promise<T> {
    let response: Response;
    try {
      response = await load(`${base}${path}`);
    } catch {
      throw new ApiError("network", "Cannot load the recorded demo.");
    }
    if (!response.ok) throw new ApiError("not_found", "This was not recorded in the demo.");
    return (await response.json()) as T;
  }

  const recorded = () => (snapshot ??= json<Snapshot>("snapshot.json"));
  const file = (id: string, asset: Asset) => `${base}${assetPath(id, asset)}`;

  async function document(id: string): Promise<DocumentDetail> {
    const doc = (await recorded()).documents.find((d) => d.id === id);
    if (!doc) throw new ApiError("not_found", "This document is not in the recorded demo.");
    return doc;
  }

  return {
    health: async () => (await recorded()).health,
    session: () => Promise.resolve({ required: false, authenticated: true }),
    login: readOnly,
    listDocuments: async () => (await recorded()).documents,
    getDocument: document,
    elements: (id: string, page: number) => json<ElementInfo[]>(assetPath(id, { elements: page })),
    deleteDocument: readOnly,
    reingest: readOnly,
    uploadDocument: readOnly,

    async upscale(id: string, index: number): Promise<UpscaleResult> {
      if (!(await recorded()).upscales[id]?.includes(index)) return readOnly();
      return json<UpscaleResult>(assetPath(id, { upscale: index }));
    },

    pageImageUrl: (id: string, index: number) => file(id, { page: index }),
    modelIfcUrl: (id: string) => file(id, "ifc"),
    mesh: (id: string) => json<MeshData>(assetPath(id, "mesh")),

    async ask(
      question: string,
      documentIds: string[],
      handlers: AskHandlers,
      signal?: AbortSignal,
      context?: AskContext,
    ): Promise<void> {
      const { recordings } = await recorded();
      const found = findRecording(
        recordings,
        question,
        documentIds,
        context?.document_id ?? null,
      );
      if (!found) {
        const asked = [...new Set(recordings.map((r) => r.question))];
        handlers.onError({
          code: "demo_not_recorded",
          message: `This demo replays answers recorded from real runs. Try: ${asked.join(" · ")}`,
        });
        return;
      }
      for (const { event, data } of found.events) {
        await pause(STEP_MS);
        if (signal?.aborted) return;
        if (event === "step") handlers.onStep(JSON.parse(data) as AskStep);
        else if (event === "answer") handlers.onAnswer(JSON.parse(data) as Answer);
        else if (event === "error") handlers.onError(JSON.parse(data) as ApiErrorBody);
        else if (event === "view") handlers.onView(JSON.parse(data) as PlanView);
      }
    },
  };
}
