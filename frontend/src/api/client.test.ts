import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("API requests", () => {
  it("allows main's bounded sketch redraw to run longer than a normal document request", async () => {
    vi.useFakeTimers();
    let finish!: (response: Response) => void;
    const response = new Promise<Response>((resolve) => {
      finish = resolve;
    });
    const fetch = vi.fn().mockReturnValue(response);
    vi.stubGlobal("fetch", fetch);
    const work = api.upscale("doc", 0);
    await vi.advanceTimersByTimeAsync(31_000);
    expect((fetch.mock.calls[0][1] as RequestInit).signal?.aborted).toBe(false);
    finish(Response.json({ ok: true, data: { added: 0, cached: true } }));
    await expect(work).resolves.toMatchObject({ added: 0, cached: true });
    expect(vi.getTimerCount()).toBe(0);
  });
  it("unwraps successful responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ok: true, data: [] })));
    await expect(api.listDocuments()).resolves.toEqual([]);
  });

  it("keeps safe API errors and handles malformed or unreachable responses", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    fetch.mockResolvedValueOnce(
      Response.json({ ok: false, data: null, error: { code: "not_found", message: "Missing" } }),
    );
    await expect(api.getDocument("missing")).rejects.toMatchObject({ code: "not_found" });
    fetch.mockResolvedValueOnce(new Response("bad gateway", { status: 502 }));
    await expect(api.listDocuments()).rejects.toMatchObject({ code: "bad_response" });
    fetch.mockRejectedValueOnce(new Error("private network detail"));
    await expect(api.listDocuments()).rejects.toMatchObject({
      code: "network",
      message: "Cannot reach the server.",
    });
  });

  it("ends a stalled request instead of leaving the page loading", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_path: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("", "AbortError")),
            );
          }),
      ),
    );
    const result = expect(api.listDocuments()).rejects.toMatchObject({ code: "timeout" });
    await vi.advanceTimersByTimeAsync(30_000);
    await result;
    expect(vi.getTimerCount()).toBe(0);
  });

  it("also bounds a response body that never finishes downloading", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_path: string, init: RequestInit) =>
        Promise.resolve({
          json: () =>
            new Promise((_resolve, reject) => {
              init.signal?.addEventListener("abort", () =>
                reject(new DOMException("", "AbortError")),
              );
            }),
        }),
      ),
    );
    const result = expect(api.listDocuments()).rejects.toMatchObject({ code: "timeout" });
    await vi.advanceTimersByTimeAsync(30_000);
    await result;
  });

  it("loads raw mesh JSON and keeps errors in the normal envelope", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(Response.json({ meshes: [] }));
    vi.stubGlobal("fetch", fetch);
    await expect(api.mesh("doc")).resolves.toEqual({ meshes: [] });
    fetch.mockResolvedValueOnce(
      Response.json(
        { ok: false, data: null, error: { code: "not_found", message: "Missing" } },
        { status: 404 },
      ),
    );
    await expect(api.mesh("doc")).rejects.toMatchObject({ code: "not_found" });
  });
});
