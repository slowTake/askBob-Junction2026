import type { DocumentInfo } from "../api/types";
import type { IngestProgress } from "../hooks/useDocuments";

interface Props {
  documents: DocumentInfo[];
  progress: Record<string, IngestProgress>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

const STATUS_LABEL: Record<DocumentInfo["status"], string> = {
  queued: "Queued",
  processing: "Reading",
  ready: "Ready",
  failed: "Failed",
};

export function DocumentList({ documents, progress, selectedId, onSelect, onDelete }: Props) {
  return (
    <nav className="sidebar" aria-label="Documents">
      <h2 className="eyebrow">Documents</h2>
      <ul className="doc-list">
        {documents.map((doc) => {
          const p = progress[doc.id];
          const busy = doc.status === "queued" || doc.status === "processing";
          return (
            <li key={doc.id}>
              <button
                type="button"
                className={`doc-row${doc.id === selectedId ? " is-active" : ""}`}
                onClick={() => onSelect(doc.id)}
                title={doc.error_message ?? undefined}
              >
                <span className="doc-name">{doc.filename}</span>
                <span className="doc-meta">
                  <span className="kind-tag">{doc.kind.toUpperCase()}</span>
                  <span className={`status status-${doc.status}`}>
                    {busy && p?.stage ? p.stage : STATUS_LABEL[doc.status]}
                  </span>
                </span>
                {busy && (
                  <span className="progress" aria-hidden>
                    <span style={{ width: `${Math.round((p?.progress ?? 0) * 100)}%` }} />
                  </span>
                )}
              </button>
              <button
                type="button"
                className="icon-btn"
                aria-label={`Delete ${doc.filename}`}
                onClick={() => onDelete(doc.id)}
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
