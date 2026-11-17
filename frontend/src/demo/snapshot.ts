/**
 * The recorded demo (D-059): what `scripts/demo_snapshot.py` saved from a real local run,
 * and how a question asked in the demo finds its recorded answer.
 */

import type { DocumentDetail, HealthInfo } from "../api/types";

/** One server-sent event as /api/ask sent it: `step`, `view`, `answer` or `error`. */
export interface RecordedEvent {
  event: string;
  data: string;
}

/** A question asked against a running stack and every event its answer streamed. */
export interface Recording {
  question: string;
  document_ids: string[];
  events: RecordedEvent[];
}

/** `snapshot.json`, at the root of the demo build. */
export interface Snapshot {
  recorded_at: string; // ISO date of the run
  health: HealthInfo;
  documents: DocumentDetail[];
  /** Page indexes with a recorded upscale result, per document id. */
  upscales: Record<string, number[]>;
  recordings: Recording[];
}

export type Asset = { page: number } | { elements: number } | { upscale: number } | "mesh" | "ifc";

/** Where a recorded file lives, relative to the demo root. The recorder writes the same. */
export function assetPath(documentId: string, asset: Asset): string {
  const dir = `documents/${documentId}`;
  if (asset === "mesh") return `${dir}/mesh.json`;
  if (asset === "ifc") return `${dir}/model.ifc`;
  if ("page" in asset) return `${dir}/page-${asset.page}.png`;
  if ("elements" in asset) return `${dir}/elements-${asset.elements}.json`;
  return `${dir}/upscale-${asset.upscale}.json`;
}

/** Case, spacing and closing punctuation don't make a different question. */
export function normalizeQuestion(question: string): string {
  return question
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[?!.\s]+$/, "");
}

const sameSet = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && a.every((id) => b.includes(id));

/**
 * The recording that answers `question`: one asked about the same documents, else one
 * about the document on screen, else the first of that question. Null when the question
 * was never recorded.
 */
export function findRecording(
  recordings: readonly Recording[],
  question: string,
  documentIds: readonly string[],
  onScreen: string | null,
): Recording | null {
  const wanted = normalizeQuestion(question);
  const matches = recordings.filter((r) => normalizeQuestion(r.question) === wanted);
  return (
    matches.find((r) => sameSet(r.document_ids, documentIds)) ??
    matches.find((r) => onScreen !== null && r.document_ids.includes(onScreen)) ??
    matches[0] ??
    null
  );
}
