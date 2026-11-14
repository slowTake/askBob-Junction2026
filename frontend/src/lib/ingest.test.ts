import { describe, expect, it } from "vitest";
import { isBusy, statusLine } from "./ingest";

const doc = (status: string, error_message: string | null = null) => ({ status, error_message });

describe("statusLine", () => {
  it("says a queued document waits for the worker", () => {
    expect(statusLine(doc("queued"), undefined, 1)).toMatchObject({
      label: "Queued",
      tone: "busy",
    });
    expect(statusLine(doc("queued"), undefined, null).label).toBe("Queued"); // count unknown
  });

  it("says so when no worker is running, instead of a silent 'Queued'", () => {
    const line = statusLine(doc("queued"), undefined, 0);
    expect(line.tone).toBe("warn");
    expect(line.detail).toContain("No ingest worker is running");
  });

  it("names the stage and progress while processing", () => {
    expect(statusLine(doc("processing"), { stage: "ocr", progress: 0.4 }, 1)).toMatchObject({
      label: "Reading text (OCR)",
      percent: 40,
    });
    expect(statusLine(doc("processing"), { stage: "vectorizing" }, 1).label).toBe("Vectorizing");
  });

  it("does not invent a stage it has not heard about", () => {
    // e.g. the page was reloaded mid-job: the list says processing, no event arrived yet
    expect(statusLine(doc("processing"), undefined, 1)).toMatchObject({
      label: "Processing",
      percent: null,
    });
  });

  it("ignores a progress event left over from an earlier run", () => {
    // reingest: the last event was "ready/done", the list now says queued
    expect(statusLine(doc("queued"), { stage: "done", progress: 1 }, 1).label).toBe("Queued");
  });

  it("shows why processing failed", () => {
    expect(statusLine(doc("failed", "The PDF is password-protected."), undefined, 1)).toMatchObject(
      { label: "Failed", detail: "The PDF is password-protected.", tone: "danger" },
    );
  });
});

describe("isBusy", () => {
  it("is true while a job is due or running", () => {
    expect(["queued", "processing", "ready", "failed"].map((s) => isBusy(doc(s)))).toEqual([
      true,
      true,
      false,
      false,
    ]);
  });
});
