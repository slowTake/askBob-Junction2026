/** What to say about a document while it is processed, and why it might be waiting. */

export interface IngestProgress {
  stage?: string;
  progress?: number;
}

export interface StatusLine {
  label: string;
  detail: string | null;
  percent: number | null;
  tone: "busy" | "ok" | "warn" | "danger";
}

interface DocStatus {
  status: string;
  error_message: string | null;
  meta?: Record<string, unknown>;
}

const STAGES: Record<string, string> = {
  reading: "Reading the file",
  converted: "Converted",
  rendering: "Rendering pages",
  ocr: "Reading text (OCR)",
  vision: "Reading drawing geometry",
  annotating: "Finding rooms and labels",
  aligning: "Aligning CAD room boundaries",
  modelling: "Building the model",
  indexing: "Indexing elements",
  meshing: "Building the 3D view",
  "drawing plans": "Drawing floor plans",
  saving: "Saving",
};

export function isBusy(doc: { status: string }): boolean {
  return doc.status === "queued" || doc.status === "processing";
}

/** `workers`: ingest workers listening (null when unknown). */
export function statusLine(
  doc: DocStatus,
  progress: IngestProgress | undefined,
  workers: number | null,
): StatusLine {
  if (doc.status === "ready") {
    const matched = doc.meta?.companion_status === "matched";
    return {
      label: matched ? "Ready · CAD rooms" : "Ready",
      detail: matched ? "Room boundaries from the matching DXF drawing." : null,
      percent: null,
      tone: "ok",
    };
  }
  if (doc.status === "failed") {
    const detail = doc.error_message ?? "Processing failed.";
    return { label: "Failed", detail, percent: null, tone: "danger" };
  }
  if (doc.status === "queued") {
    return workers === 0
      ? {
          label: "Waiting",
          detail: "No ingest worker is running. Processing starts as soon as one is up.",
          percent: null,
          tone: "warn",
        }
      : {
          label: "Queued",
          detail: "Waiting for the ingest worker to pick it up.",
          percent: null,
          tone: "busy",
        };
  }
  const stage = progress?.stage;
  return {
    label: stage ? (STAGES[stage] ?? capitalize(stage)) : "Processing",
    detail: null,
    percent: stage && progress?.progress !== undefined ? Math.round(progress.progress * 100) : null,
    tone: "busy",
  };
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
