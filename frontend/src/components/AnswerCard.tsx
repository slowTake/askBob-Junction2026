import type { Citation, PlanView } from "../api/types";
import type { Turn } from "../hooks/useAsk";
import { answerBlocks } from "../lib/answerText";
import { currentStatus } from "../lib/steps";
import { AnswerTable } from "./AnswerTable";
import { answerActions } from "../lib/answerActions";

interface Props {
  turn: Turn;
  latest: boolean;
  onCitation: (citation: Citation) => void;
  onShowView: (view: PlanView) => void;
}

/** One question and its answer. Every answer stays readable; the latest has an accent rule. */
export function AnswerCard({ turn, latest, onCitation, onShowView }: Props) {
  const { answer, error, steps, pending } = turn;
  const actions = answerActions(answer?.table, answer?.citations ?? [], turn.views);
  return (
    <article className={`turn${latest ? " is-latest" : ""}`}>
      <div className="question">
        {turn.about && <span className="question-about">About {turn.about}</span>}
        {turn.question}
      </div>

      <div className="answer-card">
        {pending && !answer && !error && (
          // One line: what the agent is doing right now, replaced by each new step.
          <ul className="steps" aria-live="polite">
            <li>{currentStatus(steps)}</li>
          </ul>
        )}

        {error && <p className="error-text">{error.message}</p>}

        {answer && (
          <>
            <div className="answer-text">
              {answerBlocks(answer.answer).map((block, i) =>
                block.type === "list" ? (
                  <ul key={i}>
                    {block.items.map((item, j) => (
                      <li key={j}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p key={i} className={block.type === "heading" ? "answer-heading" : undefined}>
                    {block.text}
                  </p>
                ),
              )}
            </div>
            {!!answer.table?.rows.length && (
              <AnswerTable
                table={answer.table}
                citations={answer.citations}
                onCitation={onCitation}
              />
            )}
            {(answer.method === "server" || answer.cached) && (
              <div className="chip-row">
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
            )}
            {actions.views.length > 0 && (
              <div className="answer-section">
                <span className="section-label">On the plan</span>
                <div className="chip-row">
                  {actions.views.map((v, i) => (
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
            {actions.sources.length > 0 && (
              <details className="answer-section answer-sources">
                <summary>
                  {actions.sources.length} source{actions.sources.length === 1 ? "" : "s"}
                </summary>
                <div className="chip-row">
                  {actions.sources.map(({ citation: c, index: i }) => (
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
              </details>
            )}
            {answer.caveats && <p className="caveats">{answer.caveats}</p>}
          </>
        )}
      </div>
    </article>
  );
}
