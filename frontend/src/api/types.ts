/** Mirrors backend/app/schemas.py and the SSE payloads in backend/app/qa/service.py. */

import type { BBox } from "../lib/camera";

export type DocumentKind = "ifc" | "dxf" | "dwg" | "pdf" | "svg" | "image";
export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

/** GET /api/health. `ingest_workers` is null when Valkey can't be reached. */
export interface HealthInfo {
  postgres: boolean;
  valkey: boolean;
  ingest_workers?: number | null; // missing on servers older than this field
}

/** What the user looks at while asking: the agent reads "this room" and "here" from it. */
export interface AskContext {
  document_id: string | null;
  page_index: number | null;
  element_id: string | null; // one clicked element (older form)
  element_ids: string[]; // every element selected on the plan (Shift+click), in click order
}

export interface ApiErrorBody {
  code: string;
  message: string;
}

export interface Envelope<T> {
  ok: boolean;
  data: T | null;
  error: ApiErrorBody | null;
}

export interface PageInfo {
  id: string;
  index: number;
  width_px: number;
  height_px: number;
  dpi: number | null;
  mm_per_px: number | null;
  label: string | null; // e.g. the storey of an IFC floor plan
  /** Set once the page had its upscale vision pass (#82); missing on older servers. */
  upscale?: UpscaleInfo | null;
}

/**
 * What the page's Redrawn view was made by: "sketch" when a model redrew a raster image
 * page in `rounds` draw-and-check rounds, "fill" for the gap-filling pass. `mode` and
 * `rounds` are missing on older servers.
 */
export interface UpscaleInfo {
  added: number;
  model: string;
  mode?: "sketch" | "fill";
  rounds?: number | null;
}

/** POST /api/documents/{id}/pages/{index}/upscale */
export interface UpscaleResult {
  added: number;
  cached: boolean;
  mode?: "sketch" | "fill";
  rounds?: number;
  page: PageInfo;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  kind: DocumentKind;
  status: DocumentStatus;
  page_count: number;
  has_model: boolean;
  size_bytes: number;
  error_code: string | null;
  error_message: string | null; // why processing failed, written for users
  has_ifc: boolean; // an IFC model can be downloaded (uploaded or built from the drawing)
  created_at: string;
  meta: Record<string, unknown>;
}

export interface DocumentDetail extends DocumentInfo {
  pages: PageInfo[];
}

export interface ElementInfo {
  id: string;
  document_id: string;
  page_id: string | null;
  kind: string;
  text: string | null;
  label: string | null;
  name: string | null;
  value_mm: number | null;
  bbox: BBox | null;
  ifc_guid: string | null;
  properties: Record<string, unknown>;
  source: string;
  confidence: number;
}

export interface Citation {
  element_id: string | null;
  document_id: string | null;
  page_id: string | null;
  page_index: number | null;
  bbox: BBox | null;
  ifc_guid: string | null;
  /** The element's outline in page px (rooms), when the reader found one. */
  polygon: number[][] | null;
  /** The printed name's box; `bbox` is the whole element when `target` is "element". */
  label_bbox: BBox | null;
  /** What `bbox` shows: the element, only its label (outline unknown), or a viewed region. */
  target: "element" | "label" | "region" | null;
  note: string;
  verified: boolean;
}

export interface Answer {
  answer: string;
  value: number | null; // the answer as one number, for counts and measures
  unit: string | null;
  confidence: "high" | "medium" | "low";
  caveats: string;
  verified: boolean;
  citations: Citation[];
  table?: AnswerTable; // absent in older answers
  views?: PlanView[]; // what the agent showed on the plan, in order
  cached: boolean;
  method?: "server" | "agent"; // "server": counted or added up without the agent loop
}

export interface AnswerTable {
  columns: string[];
  rows: { cells: string[]; citation: number }[]; // 1-based citation number; 0 for totals
}

/** Text written on the plan at a point, e.g. an apartment's area over the apartment. */
export interface PlanLabel {
  at: [number, number];
  text: string;
}

/** A walked route: its corners in page px and its length. */
export interface PlanPath {
  points: [number, number][];
  label: string;
}

/** An agent instruction for the plan: light up elements, draw a measured line or a route,
 * write labels. `labels` and `path` are missing from answers cached before they existed. */
export interface PlanView {
  document_id: string;
  page_id: string;
  page_index: number;
  element_ids: string[];
  line: { from: [number, number]; to: [number, number]; label: string } | null;
  caption: string | null;
  labels?: PlanLabel[];
  path?: PlanPath | null;
}

export interface AskStep {
  tool: string;
  input: Record<string, unknown>;
}

export interface DocumentEvent {
  type: "document";
  document_id: string;
  status: DocumentStatus | "deleted";
  stage?: string;
  progress?: number;
}

export interface MeshData {
  meshes: {
    guid: string;
    ifc_class: string;
    name: string | null;
    positions: number[];
    indices: number[];
  }[];
}
