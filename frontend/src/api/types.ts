/** Mirrors backend/app/schemas.py and the SSE payloads in backend/app/qa/service.py. */

import type { BBox } from "../lib/viewport";

export type DocumentKind = "ifc" | "dxf" | "dwg" | "pdf" | "svg" | "image";
export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

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
  note: string;
  verified: boolean;
}

export interface Answer {
  answer: string;
  confidence: "high" | "medium" | "low";
  caveats: string;
  verified: boolean;
  citations: Citation[];
  views?: PlanView[]; // what the agent showed on the plan, in order
  cached: boolean;
}

/** An agent instruction for the plan: light up elements, maybe draw a measured line. */
export interface PlanView {
  document_id: string;
  page_id: string;
  page_index: number;
  element_ids: string[];
  line: { from: [number, number]; to: [number, number]; label: string } | null;
  caption: string | null;
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
