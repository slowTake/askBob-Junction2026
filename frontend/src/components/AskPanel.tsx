import { useEffect, useRef, useState } from "react";
import type { Citation } from "../api/types";
import type { Turn } from "../hooks/useAsk";
import { AnswerCard } from "./AnswerCard";

const EXAMPLES = [
  "How many bedrooms are there?",
  "How wide is the bathroom door?",
  "What is the area of the living room?",
  "Where is the sauna?",
];

interface Props {
  turns: Turn[];
  busy: boolean;
  canAsk: boolean;
  scopeLabel: string | null; // selected document name, if any
  onAsk: (question: string, onlySelected: boolean) => void;
  onCitation: (citation: Citation) => void;
}

export function AskPanel({ turns, busy, canAsk, scopeLabel, onAsk, onCitation }: Props) {
  const [question, setQuestion] = useState("");
  const [onlySelected, setOnlySelected] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Braces matter: newer browsers return a Promise from scrollIntoView, and React
    // would call a returned value as the effect's cleanup and crash.
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const submit = (text: string) => {
    const q = text.trim();
    if (q.length < 2 || busy || !canAsk) return;
    onAsk(q, onlySelected);
    setQuestion("");
  };

  return (
    <aside className="ask-panel">
      <h2 className="display-sm">Ask the drawings</h2>
      <div className="turns">
        {turns.length === 0 && (
          <div className="chip-row">
            {EXAMPLES.map((q) => (
              <button
                key={q}
                type="button"
                className="chip"
                disabled={!canAsk}
                onClick={() => submit(q)}
              >
                {q}
              </button>
            ))}
          </div>
        )}
        {turns.map((t, i) => (
          <AnswerCard key={t.id} turn={t} latest={i === turns.length - 1} onCitation={onCitation} />
        ))}
        <div ref={end} />
      </div>
      <form
        className="ask-form"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        {scopeLabel && (
          <div className="chip-row">
            <button
              type="button"
              className={`chip chip-toggle${onlySelected ? "" : " is-on"}`}
              onClick={() => setOnlySelected(false)}
            >
              All documents
            </button>
            <button
              type="button"
              className={`chip chip-toggle${onlySelected ? " is-on" : ""}`}
              onClick={() => setOnlySelected(true)}
            >
              Only {scopeLabel}
            </button>
          </div>
        )}
        <div className="ask-input-row">
          <input
            className="text-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={canAsk ? "e.g. How wide is the hall?" : "Waiting for a processed drawing…"}
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
