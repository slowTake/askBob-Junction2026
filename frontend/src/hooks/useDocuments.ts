import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { DocumentEvent, DocumentInfo } from "../api/types";
import { isBusy, type IngestProgress } from "../lib/ingest";

const POLL_MS = 4000;

/**
 * Document list, uploads, and live ingest progress from /api/events (Valkey pub/sub).
 * Events can be missed (the server restarted, the connection dropped), so the list is
 * fetched again whenever the event stream (re)connects, and polled while any document
 * is queued or processing. A status shown here is never older than a few seconds.
 */
export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [progress, setProgress] = useState<Record<string, IngestProgress>>({});
  const [workers, setWorkers] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const mounted = useRef(true);

  // State changes only in promise callbacks, never synchronously in an effect body.
  const refresh = useCallback(
    () =>
      api.listDocuments().then(
        (docs) => {
          if (!mounted.current) return;
          setDocuments(docs);
          setError(null);
          setLoaded(true);
        },
        (e: unknown) => {
          if (!mounted.current) return;
          setError(e instanceof ApiError ? e.message : "Could not load documents.");
          setLoaded(true);
        },
      ),
    [],
  );

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const source = new EventSource("/api/events");
    // Fires on the first connection and after every reconnect: catch up on missed events.
    source.addEventListener("open", () => void refresh());
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
      mounted.current = false;
      source.close();
    };
  }, [refresh]);

  const waiting = documents.some(isBusy);
  useEffect(() => {
    if (!waiting) return;
    const check = () => {
      void refresh();
      api.health().then(
        (h) => mounted.current && setWorkers(h.ingest_workers ?? null),
        () => mounted.current && setWorkers(null),
      );
    };
    check();
    const timer = window.setInterval(check, POLL_MS);
    return () => window.clearInterval(timer);
  }, [waiting, refresh]);

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

  /** True when the document was deleted. */
  const remove = useCallback(async (id: string): Promise<boolean> => {
    try {
      await api.deleteDocument(id);
      setDocuments((docs) => docs.filter((d) => d.id !== id));
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
      return false;
    }
  }, []);

  const reingest = useCallback(async (id: string) => {
    try {
      const doc = await api.reingest(id);
      setDocuments((docs) => docs.map((d) => (d.id === id ? doc : d)));
      setProgress((p) => ({ ...p, [id]: {} })); // forget the last run's stage
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start processing again.");
    }
  }, []);

  const dismissError = useCallback(() => setError(null), []);

  return { documents, progress, workers, error, loaded, upload, remove, reingest, dismissError };
}
