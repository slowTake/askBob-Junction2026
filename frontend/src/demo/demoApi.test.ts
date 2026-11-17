import { describe, expect, it } from "vitest";
import type { Answer, ApiErrorBody, AskStep, DocumentDetail, PlanView } from "../api/types";
import { ApiError } from "../api/errors";
import { createDemoApi } from "./demoApi";
import type { Snapshot } from "./snapshot";

const doc = { id: "d1", filename: "flat.png", pages: [] } as unknown as DocumentDetail;
const answer = { answer: "Four rooms.", citations: [] } as unknown as Answer;
const snapshot: Snapshot = {
  recorded_at: "2026-11-17",
  health: { postgres: true, valkey: true, ingest_workers: 1 },
  documents: [doc],
  upscales: { d1: [0] },
  recordings: [
    {
      question: "How many rooms?",
      document_ids: ["d1"],
      events: [
        { event: "step", data: JSON.stringify({ tool: "find_elements", input: {} }) },
        { event: "view", data: JSON.stringify({ document_id: "d1" }) },
        { event: "answer", data: JSON.stringify(answer) },
      ],
    },
  ],
};

/** A static host holding the snapshot and one elements file, recording what was fetched. */
function host() {
  const fetched: string[] = [];
  const files: Record<string, unknown> = {
    "/demo/snapshot.json": snapshot,
    "/demo/documents/d1/elements-0.json": [{ id: "e1" }],
    "/demo/documents/d1/upscale-0.json": { added: 3, cached: true },
  };
  const load = (url: string) => {
    fetched.push(url);
    const body = files[url];
    return Promise.resolve(
      body === undefined
        ? new Response("not found", { status: 404 })
        : new Response(JSON.stringify(body)),
    );
  };
  return { api: createDemoApi("/demo/", load, () => Promise.resolve()), fetched };
}

function collect() {
  const seen = { steps: [] as AskStep[], views: [] as PlanView[], answers: [] as Answer[] };
  const errors: ApiErrorBody[] = [];
  return {
    seen,
    errors,
    handlers: {
      onStep: (s: AskStep) => seen.steps.push(s),
      onView: (v: PlanView) => seen.views.push(v),
      onAnswer: (a: Answer) => seen.answers.push(a),
      onError: (e: ApiErrorBody) => errors.push(e),
    },
  };
}

describe("createDemoApi", () => {
  it("serves the recorded documents and needs no login", async () => {
    const { api, fetched } = host();
    expect(await api.session()).toEqual({ required: false, authenticated: true });
    expect(await api.listDocuments()).toEqual([doc]);
    expect(await api.getDocument("d1")).toEqual(doc);
    expect(await api.elements("d1", 0)).toEqual([{ id: "e1" }]);
    // The snapshot is read once and kept.
    expect(fetched.filter((u) => u.endsWith("snapshot.json"))).toHaveLength(1);
  });

  it("points images and the IFC at the recorded files", () => {
    const { api } = host();
    expect(api.pageImageUrl("d1", 3)).toBe("/demo/documents/d1/page-3.png");
    expect(api.modelIfcUrl("d1")).toBe("/demo/documents/d1/model.ifc");
  });

  it("says a document that was not recorded is not found", async () => {
    const { api } = host();
    await expect(api.getDocument("nope")).rejects.toMatchObject({ code: "not_found" });
  });

  it("refuses writes with a message that this is a recording", async () => {
    const { api } = host();
    const refused = api.uploadDocument(new File(["x"], "a.png"));
    await expect(refused).rejects.toBeInstanceOf(ApiError);
    await expect(refused).rejects.toMatchObject({ code: "demo_read_only" });
    await expect(api.deleteDocument("d1")).rejects.toMatchObject({ code: "demo_read_only" });
    await expect(api.login("pw")).rejects.toMatchObject({ code: "demo_read_only" });
  });

  it("replays a recorded answer's events in order", async () => {
    const { api } = host();
    const { seen, errors, handlers } = collect();
    await api.ask("how many rooms", ["d1"], handlers);
    expect(seen.steps).toEqual([{ tool: "find_elements", input: {} }]);
    expect(seen.views).toEqual([{ document_id: "d1" }]);
    expect(seen.answers).toEqual([answer]);
    expect(errors).toEqual([]);
  });

  it("answers an unrecorded question with the questions it can replay", async () => {
    const { api } = host();
    const { seen, errors, handlers } = collect();
    await api.ask("Where is the sauna?", ["d1"], handlers);
    expect(seen.answers).toEqual([]);
    expect(errors).toHaveLength(1);
    expect(errors[0].code).toBe("demo_not_recorded");
    expect(errors[0].message).toContain("How many rooms?");
  });

  it("serves a recorded upscale and refuses one that was not recorded", async () => {
    const { api } = host();
    expect(await api.upscale("d1", 0)).toEqual({ added: 3, cached: true });
    await expect(api.upscale("d1", 1)).rejects.toMatchObject({ code: "demo_read_only" });
  });
});
