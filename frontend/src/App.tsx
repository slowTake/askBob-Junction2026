import { lazy, Suspense, useState } from "react";
import { api } from "./api/client";
import type { Citation } from "./api/types";
import { AskPanel } from "./components/AskPanel";
import { DocumentList } from "./components/DocumentList";
import { DrawingViewer } from "./components/DrawingViewer";
import { EmptyState } from "./components/EmptyState";
import { NavBar } from "./components/NavBar";
import { useAsk } from "./hooks/useAsk";
import { useDocuments } from "./hooks/useDocuments";

// three.js is large: load the 3D viewer only when the 3D tab opens.
const ModelViewer = lazy(() =>
  import("./components/ModelViewer").then((m) => ({ default: m.ModelViewer })),
);

type View = "drawing" | "model";

export function App() {
  const docs = useDocuments();
  const asker = useAsk();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("drawing");
  const [pageIndex, setPageIndex] = useState(0);
  const [focus, setFocus] = useState<Citation | null>(null);

  const selected = docs.documents.find((d) => d.id === selectedId) ?? docs.documents[0] ?? null;
  const ready = docs.documents.filter((d) => d.status === "ready");
  const activeView: View = selected?.kind === "ifc" ? "model" : view;

  const upload = (files: File[]) => {
    files.forEach(
      (file) =>
        void docs.upload(file).then((doc) => {
          if (doc) setSelectedId(doc.id);
        }),
    );
  };

  const select = (id: string) => {
    setSelectedId(id);
    setPageIndex(0);
    setFocus(null);
  };

  const showCitation = (c: Citation) => {
    if (c.document_id && c.document_id !== selected?.id) setSelectedId(c.document_id);
    setFocus(c);
    if (c.page_index !== null && c.bbox) {
      setPageIndex(c.page_index);
      setView("drawing");
    } else if (c.ifc_guid) {
      setView("model");
    }
  };

  const ask = (question: string, onlySelected: boolean) =>
    void asker.ask(question, onlySelected && selected ? [selected.id] : []);

  if (docs.loaded && docs.documents.length === 0) {
    return (
      <>
        <NavBar onFiles={upload} />
        {docs.error && <p className="toast">{docs.error}</p>}
        <EmptyState onFiles={upload} />
      </>
    );
  }

  return (
    <>
      <NavBar onFiles={upload} />
      {docs.error && <p className="toast">{docs.error}</p>}
      <main className="workspace">
        <DocumentList
          documents={docs.documents}
          progress={docs.progress}
          selectedId={selected?.id ?? null}
          onSelect={select}
          onDelete={(id) => void docs.remove(id)}
        />
        <section className="stage">
          {selected && (
            <>
              <div className="stage-header">
                <div className="tabs" role="tablist">
                  {selected.kind !== "ifc" && (
                    <button
                      type="button"
                      role="tab"
                      aria-selected={activeView === "drawing"}
                      className={`tab${activeView === "drawing" ? " is-active" : ""}`}
                      onClick={() => setView("drawing")}
                    >
                      Drawing
                    </button>
                  )}
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeView === "model"}
                    className={`tab${activeView === "model" ? " is-active" : ""}`}
                    onClick={() => setView("model")}
                  >
                    3D model
                  </button>
                </div>
                {selected.has_model && (
                  <a className="btn btn-secondary btn-sm" href={api.modelIfcUrl(selected.id)}>
                    Download IFC
                  </a>
                )}
              </div>
              {selected.status !== "ready" ? (
                <div className="viewer-empty">
                  {selected.status === "failed"
                    ? "Processing failed. Delete and upload again, or check the worker logs."
                    : "Processing… the drawing appears here when it is ready."}
                </div>
              ) : activeView === "drawing" ? (
                <DrawingViewer
                  key={selected.id}
                  documentId={selected.id}
                  pageIndex={pageIndex}
                  onPageChange={setPageIndex}
                  focus={focus?.document_id === selected.id ? focus : null}
                  onClearFocus={() => setFocus(null)}
                />
              ) : (
                <Suspense fallback={<div className="viewer-empty">Loading 3D viewer…</div>}>
                  <ModelViewer
                    key={selected.id}
                    documentId={selected.id}
                    highlightGuid={focus?.ifc_guid ?? null}
                  />
                </Suspense>
              )}
            </>
          )}
        </section>
        <AskPanel
          turns={asker.turns}
          busy={asker.busy}
          canAsk={ready.length > 0}
          scopeLabel={selected?.status === "ready" ? selected.filename : null}
          onAsk={ask}
          onCitation={showCitation}
        />
      </main>
    </>
  );
}
