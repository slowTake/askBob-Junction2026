import type { DocumentInfo } from "../api/types";
import { isBusy, statusLine, type IngestProgress } from "../lib/ingest";
import { ExportMenu, type Exports } from "./ExportMenu";

interface Props {
  documents: DocumentInfo[];
  progress: Record<string, IngestProgress>;
  workers: number | null;
  selectedId: string | null;
  exports: Exports | null; // the Export menu for the selected document
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function DocumentList(props: Props) {
  const { documents, progress, workers, selectedId, exports, onSelect, onDelete } = props;
  return (
    <nav className="sidebar" aria-label="Documents">
      <h2 className="eyebrow">Documents</h2>
      <ul className="doc-list">
        {documents.map((doc) => {
          const line = statusLine(doc, progress[doc.id], workers);
          return (
            <li key={doc.id}>
              <button
                type="button"
                className={`doc-row${doc.id === selectedId ? " is-active" : ""}`}
                onClick={() => onSelect(doc.id)}
                title={line.detail ?? doc.filename}
              >
                <span className="doc-name">{doc.filename}</span>
                <span className="doc-meta">
                  <span className="kind-tag">{doc.kind.toUpperCase()}</span>
                  <span className={`status status-${line.tone}`}>
                    {line.label}
                    {line.percent !== null && ` ${line.percent}%`}
                  </span>
                </span>
                {isBusy(doc) && (
                  <span
                    className={`progress${line.percent === null ? " is-waiting" : ""}`}
                    aria-hidden
                  >
                    <span style={{ width: `${line.percent ?? 30}%` }} />
                  </span>
                )}
              </button>
              <button
                type="button"
                className="icon-btn"
                aria-label={`Delete ${doc.filename}`}
                title="Delete"
                onClick={() => {
                  if (window.confirm(`Delete ${doc.filename}? This cannot be undone.`))
                    onDelete(doc.id);
                }}
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
      {exports && (
        <div className="sidebar-footer">
          <ExportMenu exports={exports} variant="panel" />
        </div>
      )}
    </nav>
  );
}
