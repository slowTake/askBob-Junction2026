import { lazy, Suspense, useCallback, useState } from "react";
import { api } from "./api/client";
import type { Citation, ElementInfo, PlanView } from "./api/types";
import { AskPanel } from "./components/AskPanel";
import { DocumentList } from "./components/DocumentList";
import { DocumentStatus } from "./components/DocumentStatus";
import { DrawingViewer } from "./components/DrawingViewer";
import { EmptyState } from "./components/EmptyState";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { NavBar } from "./components/NavBar";
import { useAsk } from "./hooks/useAsk";
import { useDocuments } from "./hooks/useDocuments";
import { useStoredFlag } from "./hooks/useStoredFlag";
import { useTheme } from "./hooks/useTheme";
import { pageIndexFor, type PageRef } from "./lib/pages";
import { describe } from "./lib/planLayer";
import type { PlanTarget } from "./lib/target";
import { availableViews, pickView, type View } from "./lib/views";
import { viewerErrorMessage } from "./lib/webgl";

// three.js is large: load the 3D viewer only when the 3D tab opens.
const ModelViewer = lazy(() =>
  import("./components/ModelViewer").then((m) => ({ default: m.ModelViewer })),
);

export function App() {
  const docs = useDocuments();
  const { theme, toggle: toggleTheme } = useTheme();
  const [sidebarOpen, setSidebarOpen] = useStoredFlag("bob.sidebar", true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("drawing");
  const [page, setPage] = useState<PageRef | null>(null);
  const [target, setTarget] = useState<PlanTarget | null>(null);
  const [about, setAbout] = useState<ElementInfo | null>(null);
  const [focusSignal, setFocusSignal] = useState(0);

  // The agent drives the plan: open its document and page, then frame what it shows.
  const showView = useCallback((v: PlanView) => {
    setSelectedId(v.document_id);
    setPage({ documentId: v.document_id, index: v.page_index });
    setView("drawing");
    setTarget({ kind: "view", view: v });
  }, []);
  const asker = useAsk(showView);

  const selected = docs.documents.find((d) => d.id === selectedId) ?? docs.documents[0] ?? null;
  const ready = docs.documents.filter((d) => d.status === "ready");
  const views = selected ? availableViews(selected) : [];
  const activeView = pickView(view, views);
  const pageIndex = pageIndexFor(page, selected?.id ?? null);

  // Picking another document starts a fresh conversation: the old answers are about
  // a different drawing. When the agent or a citation opens a document, it's the same
  // conversation, so showView and showCitation keep it.
  const select = (id: string) => {
    if (id !== selected?.id) asker.clear();
    setSelectedId(id);
    setPage(null);
    setTarget(null);
    setAbout(null);
  };

  const upload = (files: File[]) => {
    files.forEach(
      (file) =>
        void docs.upload(file).then((doc) => {
          if (doc) select(doc.id);
        }),
    );
  };

  const showCitation = (c: Citation) => {
    const documentId = c.document_id ?? selected?.id ?? null;
    if (c.document_id && c.document_id !== selected?.id) setSelectedId(c.document_id);
    setTarget({ kind: "citation", citation: c });
    if (c.page_index !== null && c.bbox) {
      setPage(documentId ? { documentId, index: c.page_index } : null);
      setView("drawing");
    } else if (c.ifc_guid) {
      setView("model");
    }
  };

  const askAbout = (el: ElementInfo) => {
    setAbout(el);
    setFocusSignal((n) => n + 1);
  };

  const ask = (question: string, onlySelected: boolean) => {
    const onPlan = selected?.status === "ready" && activeView === "drawing";
    void asker.ask(question, {
      documentIds: onlySelected && selected ? [selected.id] : [],
      context: selected
        ? {
            document_id: selected.id,
            page_index: onPlan ? pageIndex : null,
            element_id: about?.document_id === selected.id ? about.id : null,
          }
        : null,
      about: about ? `${about.kind.replaceAll("_", " ")} ${describe(about).title}` : null,
    });
    setAbout(null);
  };

  const toast = docs.error && (
    <p className="toast" role="alert">
      {docs.error}
      <button type="button" className="icon-btn" aria-label="Dismiss" onClick={docs.dismissError}>
        ×
      </button>
    </p>
  );

  if (docs.loaded && docs.documents.length === 0) {
    return (
      <>
        <NavBar onFiles={upload} context={null} theme={theme} onToggleTheme={toggleTheme} />
        {toast}
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
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />
      {toast}
      <main className={`workspace${sidebarOpen ? "" : " is-sidebar-closed"}`}>
        {sidebarOpen && (
          <DocumentList
            documents={docs.documents}
            progress={docs.progress}
            workers={docs.workers}
            selectedId={selected?.id ?? null}
            onSelect={select}
            onDelete={(id) => void docs.remove(id)}
          />
        )}
        <section className="stage">
          {selected && (
            <>
              {(views.length > 1 || selected.has_ifc) && (
                <div className="stage-header">
                  <div className="tabs" role="tablist">
                    {views.length > 1 &&
                      views.map((v) => (
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
                  {selected.has_ifc && (
                    <a className="btn btn-secondary btn-sm" href={api.modelIfcUrl(selected.id)}>
                      Download IFC
                    </a>
                  )}
                </div>
              )}
              {selected.status !== "ready" ? (
                <DocumentStatus
                  doc={selected}
                  progress={docs.progress[selected.id]}
                  workers={docs.workers}
                  onReingest={() => void docs.reingest(selected.id)}
                />
              ) : activeView === "drawing" ? (
                <DrawingViewer
                  key={selected.id}
                  documentId={selected.id}
                  pageIndex={pageIndex}
                  onPageChange={(index) => setPage({ documentId: selected.id, index })}
                  target={target}
                  onClearTarget={() => setTarget(null)}
                  onAskAbout={askAbout}
                />
              ) : (
                <ErrorBoundary
                  key={selected.id}
                  fallback={(error) => (
                    <div className="viewer-note">{viewerErrorMessage(error)}</div>
                  )}
                >
                  <Suspense fallback={<div className="viewer-note">Loading 3D viewer…</div>}>
                    <ModelViewer
                      documentId={selected.id}
                      highlightGuid={target?.kind === "citation" ? target.citation.ifc_guid : null}
                      omitted={Number(selected.meta.meshes_omitted ?? 0)}
                    />
                  </Suspense>
                </ErrorBoundary>
              )}
            </>
          )}
        </section>
        <AskPanel
          turns={asker.turns}
          busy={asker.busy}
          canAsk={ready.length > 0}
          scopeLabel={selected?.status === "ready" ? selected.filename : null}
          about={about ? `${about.kind.replaceAll("_", " ")} ${describe(about).title}` : null}
          focusSignal={focusSignal}
          onClearAbout={() => setAbout(null)}
          onAsk={ask}
          onClear={() => {
            asker.clear();
            setTarget(null);
          }}
          onCitation={showCitation}
          onShowView={showView}
        />
      </main>
    </>
  );
}
