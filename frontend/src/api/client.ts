/** Every call to the backend goes through here. Responses use one envelope shape. */

import { readSSE } from "./sse";
import type {
  Answer,
  ApiErrorBody,
  AskContext,
  AskStep,
  DocumentDetail,
  DocumentInfo,
  ElementInfo,
  Envelope,
  HealthInfo,
  MeshData,
  PlanView,
  UpscaleResult,
} from "./types";

export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("network", "Cannot reach the server.");
  }
  return unwrap<T>(response);
}

async function unwrap<T>(response: Response): Promise<T> {
  let body: Envelope<T>;
  try {
    body = (await response.json()) as Envelope<T>;
  } catch {
    throw new ApiError("bad_response", "The server sent an unexpected response.");
  }
  if (!body.ok || body.data === null) {
    throw new ApiError(body.error?.code ?? "unknown", body.error?.message ?? "Request failed.");
  }
  return body.data;
}

export interface AskHandlers {
  onStep: (step: AskStep) => void;
  onAnswer: (answer: Answer) => void;
  onError: (error: ApiErrorBody) => void;
  onView: (view: PlanView) => void;
}

export const api = {
  health: () => request<HealthInfo>("/api/health"),
  listDocuments: () => request<DocumentInfo[]>("/api/documents"),
  getDocument: (id: string) => request<DocumentDetail>(`/api/documents/${id}`),
  elements: (id: string, page: number) =>
    request<ElementInfo[]>(`/api/documents/${id}/elements?page=${page}`),
  deleteDocument: (id: string) =>
    request<{ id: string }>(`/api/documents/${id}`, { method: "DELETE" }),
  reingest: (id: string) =>
    request<DocumentInfo>(`/api/documents/${id}/reingest`, { method: "POST" }),

  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentInfo>("/api/documents", { method: "POST", body: form });
  },

  upscale: (id: string, index: number) =>
    request<UpscaleResult>(`/api/documents/${id}/pages/${index}/upscale`, { method: "POST" }),

  pageImageUrl: (id: string, index: number) => `/api/documents/${id}/pages/${index}/image`,
  modelIfcUrl: (id: string) => `/api/documents/${id}/model.ifc`,

  async mesh(id: string): Promise<MeshData> {
    const response = await fetch(`/api/documents/${id}/mesh`);
    if (!response.ok) await unwrap(response); // throws the envelope's error
    return (await response.json()) as MeshData;
  },

  async ask(
    question: string,
    documentIds: string[],
    handlers: AskHandlers,
    signal?: AbortSignal,
    context?: AskContext,
  ): Promise<void> {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, document_ids: documentIds, context: context ?? null }),
      signal,
    });
    if (!response.ok || !response.body) {
      await unwrap(response);
      return;
    }
    await readSSE(response.body, ({ event, data }) => {
      if (event === "step") handlers.onStep(JSON.parse(data) as AskStep);
      else if (event === "answer") handlers.onAnswer(JSON.parse(data) as Answer);
      else if (event === "error") handlers.onError(JSON.parse(data) as ApiErrorBody);
      else if (event === "view") handlers.onView(JSON.parse(data) as PlanView);
    });
  },
};
