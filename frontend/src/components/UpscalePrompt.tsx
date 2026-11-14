interface Props {
  busy: boolean;
  error: string | null;
  sketch: boolean; // a raster image: the model redraws the whole page
  onUpscale: () => void;
}

/** The Redrawn view of a page that has not been redrawn yet: one button, in the middle. */
export function UpscalePrompt({ busy, error, sketch, onUpscale }: Props) {
  return (
    <div className="upscale-prompt" data-no-pan>
      <div className="upscale-card">
        {sketch ? (
          <p className="body-sm">
            Redraw this sketch as a clean floor plan. A vision model draws the plan, checks its
            drawing against the photo and corrects it. Nothing is measured: only what is written on
            the sketch appears.
          </p>
        ) : (
          <p className="body-sm">
            Redraw this page with uniform lines and one font. One vision pass first checks the page
            for walls, doors, windows and room names that were missed; what it adds is marked and
            dashed.
          </p>
        )}
        <button type="button" className="btn btn-primary" disabled={busy} onClick={onUpscale}>
          {busy ? (sketch ? "Redrawing…" : "Upscaling…") : sketch ? "Redraw" : "Upscale"}
        </button>
        {busy && sketch && (
          <p className="body-sm muted" role="status">
            Drawing and checking the plan. This takes a few minutes.
          </p>
        )}
        {error && (
          <p className="body-sm upscale-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
