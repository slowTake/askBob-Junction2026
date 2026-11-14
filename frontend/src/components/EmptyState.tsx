import { useState } from "react";
import { UploadButton } from "./UploadButton";

interface Props {
  onFiles: (files: File[]) => void;
}

/** First visit: hero band with a drop zone card. */
export function EmptyState({ onFiles }: Props) {
  const [dragging, setDragging] = useState(false);
  return (
    <section className="hero-band">
      <div className="hero-copy">
        <h1 className="display-lg">Ask your drawings anything.</h1>
        <p className="body-lg muted">
          Upload floor plans, PDFs or IFC models. Every answer points to the exact spot on the
          drawing it came from, so you can check it in seconds.
        </p>
      </div>
      <div
        className={`dropzone${dragging ? " is-dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          onFiles(Array.from(e.dataTransfer.files));
        }}
      >
        <p className="heading">Drop drawings here</p>
        <div className="chip-row">
          {["IFC", "DXF", "DWG", "PDF", "SVG", "PNG", "JPEG", "TIFF"].map((f) => (
            <span key={f} className="chip">
              {f}
            </span>
          ))}
        </div>
        <UploadButton onFiles={onFiles} label="Choose files" />
        <p className="body-sm muted">
          Have a matching DXF? Upload it with the PNG using the same filename to get exact room
          boundaries.
        </p>
      </div>
    </section>
  );
}
