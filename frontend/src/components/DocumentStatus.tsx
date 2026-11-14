import type { DocumentInfo } from "../api/types";
import { statusLine, type IngestProgress } from "../lib/ingest";

interface Props {
  doc: DocumentInfo;
  progress: IngestProgress | undefined;
  workers: number | null;
  onReingest: () => void;
}

/** Shown instead of the plan while a document is waiting, processing or failed. */
export function DocumentStatus({ doc, progress, workers, onReingest }: Props) {
  const line = statusLine(doc, progress, workers);
  return (
    <div className={`doc-status tone-${line.tone}`}>
      <p className="heading">
        {line.label}
        {line.percent !== null && ` · ${line.percent}%`}
      </p>
      {line.detail && <p className="body-sm">{line.detail}</p>}
      {doc.status !== "failed" && (
        <span className={`progress${line.percent === null ? " is-waiting" : ""}`} aria-hidden>
          <span style={{ width: `${line.percent ?? 30}%` }} />
        </span>
      )}
      {doc.status === "failed" && (
        <button type="button" className="btn btn-primary" onClick={onReingest}>
          Process again
        </button>
      )}
    </div>
  );
}
