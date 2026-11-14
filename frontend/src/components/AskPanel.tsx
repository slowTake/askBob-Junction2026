import { useEffect, useRef, useState } from "react";
import type { Citation, PlanView } from "../api/types";
import type { Turn } from "../hooks/useAsk";
import { chatMilestone } from "../lib/conversations";
import { AnswerCard } from "./AnswerCard";

// Questions that work on any plan and show what the assistant can do with it.
const EXAMPLES = [
  "How many rooms are on this plan? Show them.",
  "Show all the doors and windows.",
  "What is the total area of each apartment?",
  "How far is the kitchen from the bathroom?",
];

interface Props {
  turns: readonly Turn[];
  busy: boolean;
  canAsk: boolean;
  scopeLabel: string | null; // selected document name, if it can be asked about alone
  about: string | null; // the element the next question is about
  focusSignal: number; // changes when the input should take focus
  onClearAbout: () => void;
  onAsk: (question: string, onlySelected: boolean) => void;
  onCitation: (citation: Citation) => void;
  onShowView: (view: PlanView) => void;
}

export function AskPanel(props: Props) {
  const { turns, busy, canAsk, scopeLabel, about, focusSignal } = props;
  const [question, setQuestion] = useState("");
  const [onlySelected, setOnlySelected] = useState(true);
  const list = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  // Was the reader at the end before the last update? Measured on scroll, not after the
  // update: an answer can add more than a screen at once.
  const atEnd = useRef(true);
  const milestone = chatMilestone(turns);
  const seen = useRef(milestone);

  useEffect(() => {
    const el = list.current;
    if (!el) return;
    // Asked, answered, or another document's conversation: always show the end.
    const jump = seen.current !== milestone;
    seen.current = milestone;
    if (jump || atEnd.current) {
      // Instant: a smooth scroll fires scroll events on its way down, which read as the
      // reader leaving the end and switched following off (PR #92 review).
      el.scrollTop = el.scrollHeight;
      atEnd.current = true;
    }
  }, [turns, milestone]);

  useEffect(() => {
    if (focusSignal > 0) input.current?.focus();
  }, [focusSignal]);

  const submit = (text: string) => {
    const q = text.trim();
    if (q.length < 2 || busy || !canAsk) return;
    props.onAsk(q, onlySelected && scopeLabel !== null);
    setQuestion("");
  };

  return (
    <aside className="ask-panel" aria-label="Ask the drawings">
      <div className="ask-header">
        <h2 className="eyebrow">Ask the drawings</h2>
      </div>
      <div
        className="turns"
        ref={list}
        onScroll={(e) => {
          const el = e.currentTarget;
          atEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
        }}
      >
        {turns.length === 0 && (
          <div className="ask-intro">
            <p className="body-sm muted">
              Ask about rooms, areas, doors or distances. Answers cite the drawing, and the
              assistant shows what it found on the plan. Click a room on the plan to ask about it.
            </p>
            <div className="example-list">
              {EXAMPLES.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="chip"
                  disabled={!canAsk || busy}
                  onClick={() => submit(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <AnswerCard
            key={t.id}
            turn={t}
            latest={i === turns.length - 1}
            onCitation={props.onCitation}
            onShowView={props.onShowView}
          />
        ))}
      </div>
      <form
        className="ask-form"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        {(about || scopeLabel) && (
          <div className="chip-row ask-scope">
            {about && (
              <span className="context-chip">
                About: <b>{about}</b>
                <button
                  type="button"
                  aria-label="Stop asking about this"
                  onClick={props.onClearAbout}
                >
                  ×
                </button>
              </span>
            )}
            {scopeLabel && (
              <label className="scope-toggle">
                <input
                  type="checkbox"
                  checked={onlySelected}
                  onChange={(e) => setOnlySelected(e.target.checked)}
                />
                Only this document
              </label>
            )}
          </div>
        )}
        <div className="ask-input-row">
          <textarea
            ref={input}
            className="text-input"
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(question);
              }
            }}
            placeholder={
              !canAsk
                ? "Waiting for a processed drawing…"
                : about
                  ? `Ask about ${about}…`
                  : "Ask a question (Enter to send)"
            }
            aria-label="Question"
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !canAsk}>
            {busy ? "Asking…" : "Ask"}
          </button>
        </div>
      </form>
    </aside>
  );
}
