import type { Citation, PlanView } from "../api/types";
import type { Turn } from "../hooks/useAsk";
import { describeStep } from "../lib/steps";

interface Props {
  turn: Turn;
  latest: boolean;
  onCitation: (citation: Citation) => void;
  onShowView: (view: PlanView) => void;
}

/** One question and its answer. Every answer stays readable; the latest has an accent rule. */
export function AnswerCard({ turn, latest, onCitation, onShowView }: Props) {
  const { answer, error, steps, pending } = turn;
  return (
    <article className={`turn${latest ? " is-latest" : ""}`}>
      <div className="question">
        {turn.about && <span className="question-about">About {turn.about}</span>}
        {turn.question}
      </div>

      <div className="answer-card">
        {pending && !answer && !error && (
          <ul className="steps" aria-live="polite">
            {steps.length === 0 && <li>Thinking</li>}
            {steps.map((s, i) => (
              <li key={i}>{describeStep(s.tool, s.input)}</li>
            ))}
          </ul>
        )}

        {error && <p className="error-text">{error.message}</p>}

        {answer && (
          <>
            <p className="answer-text">{answer.answer}</p>
            <div className="chip-row">
              <span className={`badge ${answer.verified ? "badge-ok" : "badge-warn"}`}>
                {answer.verified ? "✓ Verified sources" : "! Not verified"}
              </span>
              <span className="badge badge-plain">{answer.confidence} confidence</span>
              {answer.method === "server" && (
                <span
                  className="badge badge-plain"
                  title="Counted or added up by the server from the cited elements, not by the language model"
                >
                  computed by the server
                </span>
              )}
              {answer.cached && <span className="badge badge-plain">cached</span>}
            </div>
            {turn.views.length > 0 && (
              <div className="answer-section">
                <span className="section-label">On the plan</span>
                <div className="chip-row">
                  {turn.views.map((v, i) => (
                    <button
                      key={i}
                      type="button"
                      className="view-chip"
                      onClick={() => onShowView(v)}
                    >
                      ⌖ {v.caption ?? v.line?.label ?? `${v.element_ids.length} elements`}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {answer.citations.length > 0 && (
              <div className="answer-section">
                <span className="section-label">Sources</span>
                <div className="chip-row">
                  {answer.citations.map((c, i) => (
                    <button
                      key={i}
                      type="button"
                      className={`citation${c.verified ? "" : " is-unverified"}`}
                      onClick={() => onCitation(c)}
                      title={
                        c.verified ? "Show on the drawing" : "This citation could not be verified"
                      }
                    >
                      <span className="citation-num">{i + 1}</span>
                      {c.note || "source"}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {answer.caveats && <p className="caveats">{answer.caveats}</p>}
          </>
        )}
      </div>
    </article>
  );
}
