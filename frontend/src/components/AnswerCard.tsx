import type { Citation, PlanView } from "../api/types";
import type { Turn } from "../hooks/useAsk";
import { describeStep } from "../lib/steps";

interface Props {
  turn: Turn;
  latest: boolean;
  onCitation: (citation: Citation) => void;
  onShowView: (view: PlanView) => void;
}

/** The latest answer is a card with an accent rule; older turns fall back to plain text. */
export function AnswerCard({ turn, latest, onCitation, onShowView }: Props) {
  const { answer, error, steps, pending } = turn;
  return (
    <article className={`answer-card${latest ? " is-latest" : ""}`}>
      <p className="question">{turn.question}</p>

      {pending && !answer && (
        <ul className="steps">
          {steps.length === 0 && <li>Thinking…</li>}
          {steps.map((s, i) => (
            <li key={i}>{describeStep(s.tool, s.input)}</li>
          ))}
        </ul>
      )}

      {error && <p className="error-text">{error.message}</p>}

      {answer && (
        <>
          <div className="chip-row">
            <span className={`badge ${answer.verified ? "badge-ok" : "badge-warn"}`}>
              {answer.verified ? "✓ Verified sources" : "! Not verified"}
            </span>
            <span className="badge badge-plain">{answer.confidence} confidence</span>
            {answer.cached && <span className="badge badge-plain">cached</span>}
          </div>
          <p className="answer-text">{answer.answer}</p>
          {answer.citations.length > 0 && (
            <div className="chip-row">
              {answer.citations.map((c, i) => (
                <button
                  key={i}
                  type="button"
                  className={`citation${c.verified ? "" : " is-unverified"}`}
                  onClick={() => onCitation(c)}
                  title={c.verified ? "Show on drawing" : "This citation could not be verified"}
                >
                  <span className="citation-num">{i + 1}</span>
                  {c.note || "source"}
                </button>
              ))}
            </div>
          )}
          {turn.views.length > 0 && (
            <button
              type="button"
              className="citation"
              onClick={() => onShowView(turn.views[turn.views.length - 1])}
            >
              Show on plan
            </button>
          )}
          {answer.caveats && <p className="caveats">{answer.caveats}</p>}
        </>
      )}
    </article>
  );
}
