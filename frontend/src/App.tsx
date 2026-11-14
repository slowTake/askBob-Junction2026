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
import { useTheme } from "./hooks/useTheme";
import { availableViews, pickView, type View } from "./lib/views";
import { pageIndexFor, type PageRef } from "./lib/pages";

// three.js is large: load the 3D viewer only when the 3D tab opens.
const ModelViewer = lazy(() =>
  import("./components/ModelViewer").then((m) => ({ default: m.ModelViewer })),
);

export function App() {
  const docs = useDocuments();
  const asker = useAsk();
  const { theme, toggle: toggleTheme } = useTheme();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("drawing");
  const [page, setPage] = useState<PageRef | null>(null);
  const [focus, setFocus] = useState<Citation | null>(null);

  const selected = docs.documents.find((d) => d.id === selectedId) ?? docs.documents[0] ?? null;
  const ready = docs.documents.filter((d) => d.status === "ready");
  const views = selected ? availableViews(selected) : [];
  const activeView = pickView(view, views);
  const pageIndex = pageIndexFor(page, selected?.id ?? null);

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
    setPage(null);
    setFocus(null);
  };

  const showCitation = (c: Citation) => {
    const documentId = c.document_id ?? selected?.id ?? null;
    if (c.document_id && c.document_id !== selected?.id) setSelectedId(c.document_id);
    setFocus(c);
    if (c.page_index !== null && c.bbox) {
      setPage(documentId ? { documentId, index: c.page_index } : null);
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
        <NavBar onFiles={upload} context={null} theme={theme} onToggleTheme={toggleTheme} />
        {docs.error && <p className="toast">{docs.error}</p>}
        <EmptyState onFiles={upload} />
      </>
    );
  }

  return (
    <>
      <NavBar
        onFiles={upload}
        context={selected?.filename ?? null}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
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
                {views.length > 1 ? (
                  <div className="tabs" role="tablist">
                    {views.map((v) => (
                      <button
                        key={v}
                        type="button"
                        role="tab"
                        aria-selected={activeView === v}
                        className={`tab${activeView === v ? " is-active" : ""}`}
                        onClick={() => setView(v)}
                      >
                        {v === "drawing" ? "Plan" : "3D model"}
                      </button>
                    ))}
                  </div>
                ) : (
                  <span className="body-sm muted">{selected.filename}</span>
                )}
                {selected.has_ifc && (
                  <a className="btn btn-secondary btn-sm" href={api.modelIfcUrl(selected.id)}>
                    Download IFC
                  </a>
                )}
              </div>
              {selected.status !== "ready" ? (
                <div className="viewer-empty">
                  {selected.status === "failed"
                    ? (selected.error_message ?? "Processing failed.")
                    : "Processing… the drawing appears here when it is ready."}
                </div>
              ) : activeView === "drawing" ? (
                <DrawingViewer
                  key={selected.id}
                  documentId={selected.id}
                  pageIndex={pageIndex}
                  onPageChange={(index) => setPage({ documentId: selected.id, index })}
                  focus={focus?.document_id === selected.id ? focus : null}
                  onClearFocus={() => setFocus(null)}
                  highlightIds={focus?.element_id ? [focus.element_id] : []}
                />
              ) : (
                <Suspense fallback={<div className="viewer-empty">Loading 3D viewer…</div>}>
                  <ModelViewer
                    key={selected.id}
                    documentId={selected.id}
                    highlightGuid={focus?.ifc_guid ?? null}
                    omitted={Number(selected.meta.meshes_omitted ?? 0)}
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
