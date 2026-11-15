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
  SessionInfo,
  UpscaleResult,
} from "./types";

export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
  parse: (response: Response) => Promise<T> = unwrap<T>,
  timeoutMs = 30_000,
): Promise<T> {
  const controller = new AbortController();
  const timer = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, { ...init, signal: controller.signal });
    return await parse(response);
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiError("timeout", "The server took too long to respond. Please try again.");
    }
    if (error instanceof ApiError) throw error;
    throw new ApiError("network", "Cannot reach the server.");
  } finally {
    globalThis.clearTimeout(timer);
  }
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
  session: () => request<SessionInfo>("/api/session"),
  login: (password: string) =>
    request<{ authenticated: boolean }>("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    }),
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
    return request<DocumentInfo>(
      "/api/documents",
      { method: "POST", body: form },
      undefined,
      120_000,
    );
  },

  upscale: (id: string, index: number) =>
    // Sketch redraws use main's bounded multi-round model loop, rather than a normal
    // document request. Match the default server claim budget (600 + 3 * 300 s).
    request<UpscaleResult>(
      `/api/documents/${id}/pages/${index}/upscale`,
      { method: "POST" },
      undefined,
      1_500_000,
    ),

  pageImageUrl: (id: string, index: number) => `/api/documents/${id}/pages/${index}/image`,
  modelIfcUrl: (id: string) => `/api/documents/${id}/model.ifc`,

  async mesh(id: string): Promise<MeshData> {
    return request(`/api/documents/${id}/mesh`, undefined, async (response) => {
      if (!response.ok) await unwrap(response); // throws the envelope's error
      return (await response.json()) as MeshData;
    });
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
