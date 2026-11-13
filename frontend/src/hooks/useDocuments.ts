import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { DocumentEvent, DocumentInfo } from "../api/types";

export interface IngestProgress {
  stage?: string;
  progress?: number;
}

/** Document list, uploads, and live ingest progress from /api/events (Valkey pub/sub). */
export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [progress, setProgress] = useState<Record<string, IngestProgress>>({});
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    // State changes only in promise callbacks, never synchronously in the effect body.
    const refresh = () =>
      api.listDocuments().then(
        (docs) => {
          if (!live) return;
          setDocuments(docs);
          setError(null);
          setLoaded(true);
        },
        (e: unknown) => {
          if (!live) return;
          setError(e instanceof ApiError ? e.message : "Could not load documents.");
          setLoaded(true);
        },
      );
    void refresh();
    const source = new EventSource("/api/events");
    source.addEventListener("document", (message) => {
      const event = JSON.parse((message as MessageEvent<string>).data) as DocumentEvent;
      setProgress((p) => ({ ...p, [event.document_id]: event }));
      if (event.status === "processing") {
        setDocuments((docs) =>
          docs.map((d) => (d.id === event.document_id ? { ...d, status: "processing" } : d)),
        );
      } else {
        void refresh(); // queued, ready, failed, deleted: fetch the authoritative state
      }
    });
    return () => {
      live = false;
      source.close();
    };
  }, []);

  const upload = useCallback(async (file: File) => {
    try {
      const doc = await api.uploadDocument(file);
      setDocuments((docs) => [doc, ...docs.filter((d) => d.id !== doc.id)]);
      setError(null);
      return doc;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed.");
      return null;
    }
  }, []);

  const remove = useCallback(async (id: string) => {
    try {
      await api.deleteDocument(id);
      setDocuments((docs) => docs.filter((d) => d.id !== id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
    }
  }, []);

  return { documents, progress, error, loaded, upload, remove };
}
