import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api/client";
import type { Citation, ElementInfo, PlanView } from "./api/types";
import { AskPanel } from "./components/AskPanel";
import { DocumentList } from "./components/DocumentList";
import { DocumentStatus } from "./components/DocumentStatus";
import { DrawingViewer } from "./components/DrawingViewer";
import { EmptyState } from "./components/EmptyState";
import type { Exports, SheetExport } from "./components/ExportMenu";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { NavBar } from "./components/NavBar";
import { useAsk } from "./hooks/useAsk";
import { useDocuments } from "./hooks/useDocuments";
import { useStoredFlag } from "./hooks/useStoredFlag";
import { useTheme } from "./hooks/useTheme";
import { conversationShown } from "./lib/conversations";
import { pageIndexFor, type PageRef } from "./lib/pages";
import { questionContext } from "./lib/question";
import { aboutLabel } from "./lib/selection";
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
  const [about, setAbout] = useState<ElementInfo[]>([]); // selected on the plan to ask about
  const [focusSignal, setFocusSignal] = useState(0);
  const [sheetExport, setSheetExport] = useState<SheetExport | null>(null); // set by the plan

  // The agent drives the plan: open its document and page, then frame what it shows.
  const showView = useCallback((v: PlanView) => {
    setSelectedId(v.document_id);
    setPage({ documentId: v.document_id, index: v.page_index });
    setView("drawing");
    setTarget({ kind: "view", view: v });
  }, []);
  // An answer's views move the plan only while its conversation is on screen: an answer
  // still running for another document must not take over the plan (PR #92 review).
  // Its views stay as buttons on the answer.
  const chatKeyRef = useRef<string | null>(null);
  const showAnswerView = useCallback(
    (v: PlanView, key: string) => {
      if (key === chatKeyRef.current) showView(v);
    },
    [showView],
  );
  const asker = useAsk(showAnswerView);

  const selected = docs.documents.find((d) => d.id === selectedId) ?? docs.documents[0] ?? null;
  // The conversation on screen: the one picked in the list or last asked in, else the open
  // document's (see conversationShown).
  const [chatFor, setChatFor] = useState<string | null>(null);
  const chatKey = conversationShown(
    chatFor,
    selected?.id ?? null,
    docs.documents.map((d) => d.id),
  );
  useEffect(() => {
    chatKeyRef.current = chatKey;
  }, [chatKey]);
  const chatDoc = docs.documents.find((d) => d.id === chatKey) ?? null;
  const ready = docs.documents.filter((d) => d.status === "ready");
  const views = selected ? availableViews(selected) : [];
  const activeView = pickView(view, views);
  const pageIndex = pageIndexFor(page, selected?.id ?? null);

  // Each document has its own conversation. Picking one in the list (or uploading one)
  // shows its conversation; a new upload starts empty. When the agent or a citation opens
  // another document, the conversation stays: showView and showCitation don't change it.
  const select = (id: string) => {
    setChatFor(id);
    setSelectedId(id);
    setPage(null);
    setTarget(null);
    setAbout([]);
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

  // Asking about elements selected on a plan is a question about that plan's document.
  const askAbout = (elements: ElementInfo[]) => {
    if (elements.length > 0) setChatFor(elements[0].document_id);
    setAbout(elements);
    setFocusSignal((n) => n + 1);
  };

  const ask = (question: string, onlySelected: boolean) => {
    if (!chatKey) return;
    // Pin it: the agent's views and clicked sources may open another document meanwhile.
    setChatFor(chatKey);
    const onPlan = selected?.status === "ready" && activeView === "drawing";
    const { documentIds, context } = questionContext({
      chatDocId: chatKey,
      openDocId: selected?.id ?? null,
      pageOnScreen: onPlan ? pageIndex : null,
      about,
      onlyThisDocument: onlySelected,
    });
    void asker.ask(chatKey, question, {
      documentIds,
      context,
      about: aboutLabel(about.filter((e) => e.document_id === chatKey)),
    });
    setAbout([]);
  };

  // One Export menu: in the documents panel's footer, or in the app bar while it's hidden.
  const exports: Exports | null = selected
    ? { ifcUrl: selected.has_ifc ? api.modelIfcUrl(selected.id) : null, sheet: sheetExport }
    : null;

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
        <NavBar onFiles={upload} theme={theme} onToggleTheme={toggleTheme} />
        {toast}
        <EmptyState onFiles={upload} />
      </>
    );
  }

  return (
    <>
      <NavBar
        onFiles={upload}
        theme={theme}
        onToggleTheme={toggleTheme}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        exports={sidebarOpen ? undefined : (exports ?? undefined)}
      />
      {toast}
      <main className={`workspace${sidebarOpen ? "" : " is-sidebar-closed"}`}>
        {sidebarOpen && (
          <DocumentList
            documents={docs.documents}
            progress={docs.progress}
            workers={docs.workers}
            selectedId={selected?.id ?? null}
            exports={exports}
            onSelect={select}
            onDelete={(id) => void docs.remove(id).then((removed) => removed && asker.clear(id))}
          />
        )}
        <section className="stage">
          {selected && (
            <>
              {views.length > 1 && (
                <div className="stage-header">
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
                  onSheetExport={setSheetExport}
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
          turns={asker.turnsFor(chatKey)}
          busy={asker.busyFor(chatKey)}
          canAsk={ready.length > 0}
          scopeLabel={chatDoc?.status === "ready" ? chatDoc.filename : null}
          about={aboutLabel(about)}
          focusSignal={focusSignal}
          onClearAbout={() => setAbout([])}
          onAsk={ask}
          onCitation={showCitation}
          onShowView={showView}
        />
      </main>
    </>
  );
}
